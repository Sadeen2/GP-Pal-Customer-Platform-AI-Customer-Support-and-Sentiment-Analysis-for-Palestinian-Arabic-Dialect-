from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.model.infer import predict
from app.services.routing import decide_route
from app.services.urgency import apply_critical_urgency_rule as normalize_urgency_result
from app.services.assignment_service import auto_assign_conversation, should_auto_assign
from app.database.db import get_db
from app.database.models import Message, Conversation, User, Customer, CustomerChannel
from app.schemas.message import (
    MessageRequest,
    PredictionResponse,
    ConversationStatusUpdate,
    MessageFeedbackUpdate,
    ConversationNoteUpdate,
    ConversationAssignUpdate,
    ConversationReplyRequest,
    ConversationBotToggleUpdate,
)
from app.security import get_current_user, require_roles
from app.realtime import broadcast_dashboard_event

router = APIRouter()


def top_score(item: dict) -> float:
    label = item.get("label")
    return item.get("scores", {}).get(label, 0.0)


def apply_critical_urgency_rule(text: str, result: dict) -> dict:
    """Backward-compatible wrapper around the shared urgency rules."""
    return normalize_urgency_result(text, result)


def is_manager_or_admin(user: User) -> bool:
    return user.role in ["manager", "super_admin"]


def get_agent_assigned_conversation_ids(db: Session, user: User):
    rows = (
        db.query(Conversation.id)
        .filter(Conversation.assigned_agent == user.email)
        .all()
    )
    return [row[0] for row in rows]


def check_conversation_access(conversation_id: int, db: Session, user: User):
    if is_manager_or_admin(user):
        return

    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if conversation is None or conversation.assigned_agent != user.email:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this conversation"
        )


def check_message_access(message: Message, db: Session, user: User):
    if is_manager_or_admin(user):
        return

    if message.conversation_id is None:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this message"
        )

    check_conversation_access(message.conversation_id, db, user)


def message_to_dict(msg: Message):
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "customer_id": msg.customer_id,
        "customer_db_id": getattr(msg, "customer_db_id", None),
        "text": msg.text,
        "sender_type": getattr(msg, "sender_type", "customer"),
        "channel": msg.channel,
        "message_type": getattr(msg, "message_type", "text"),
        "external_message_id": getattr(msg, "external_message_id", None),
        "whatsapp_media_id": getattr(msg, "whatsapp_media_id", None),
        "sentiment": msg.sentiment,
        "sentiment_confidence": msg.sentiment_confidence,
        "category": msg.category,
        "category_confidence": msg.category_confidence,
        "urgency": msg.urgency,
        "urgency_confidence": msg.urgency_confidence,
        "routing_action": msg.routing_action,
        "routing_reason": msg.routing_reason,
        "matched_faq_id": getattr(msg, "matched_faq_id", None),
        "needs_human": bool(getattr(msg, "needs_human", False)),
        "assigned_agent": msg.conversation.assigned_agent if getattr(msg, "conversation", None) else None,
        "created_at": msg.created_at
    }


def get_or_create_customer_for_channel(db: Session, channel: str, external_id: str | None):
    """Useful for web tests and for keeping the schema normalized."""
    if not external_id:
        return None

    link = (
        db.query(CustomerChannel)
        .filter(CustomerChannel.channel == channel, CustomerChannel.external_id == external_id)
        .first()
    )

    if link:
        return db.query(Customer).filter(Customer.id == link.customer_id).first()

    customer = Customer(phone=external_id if channel == "whatsapp" else None)
    db.add(customer)
    db.commit()
    db.refresh(customer)

    db.add(CustomerChannel(customer_id=customer.id, channel=channel, external_id=external_id))
    db.commit()

    return customer


@router.post("/predict", response_model=PredictionResponse)
def predict_message(
    request: MessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = predict(request.text)
    result = apply_critical_urgency_rule(request.text, result)
    routing = decide_route(result)

    customer = get_or_create_customer_for_channel(db, request.channel or "web", request.customer_id)

    conversation = None
    conversation_id = request.conversation_id

    if conversation_id is not None:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if conversation is None and request.customer_id:
        conversation = (
            db.query(Conversation)
            .filter(Conversation.customer_id == request.customer_id, Conversation.channel == (request.channel or "web"))
            .first()
        )

    if conversation is None and request.customer_id:
        conversation = Conversation(
            customer_id=request.customer_id,
            customer_db_id=customer.id if customer else None,
            channel=request.channel or "web",
            status="active",
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    if conversation is not None:
        conversation_id = conversation.id

    needs_human = should_auto_assign(
        action=routing.get("action"),
        needs_human=False,
        urgency=result["urgency"]["label"],
        sentiment=result["sentiment"]["label"],
        category=result["category"]["label"],
    )

    assignment = None
    if conversation is not None and needs_human:
        assignment_status = "escalated" if routing.get("action") in ["escalation", "escalate"] or result["urgency"]["label"] == "critical" else "pending_human"
        assignment = auto_assign_conversation(
            db=db,
            conversation=conversation,
            reason=f"predict_route_action={routing.get('action')}; urgency={result['urgency']['label']}; category={result['category']['label']}",
            status=assignment_status,
            disable_bot=False,
        )
        db.commit()
        db.refresh(conversation)

    routing_reason = routing["reason"]
    if assignment:
        routing_reason += f"; auto_assignment={assignment}"

    message = Message(
        conversation_id=conversation_id,
        customer_id=request.customer_id,
        customer_db_id=customer.id if customer else None,
        text=request.text,
        sender_type="customer",
        message_type="text",
        sentiment=result["sentiment"]["label"],
        sentiment_confidence=top_score(result["sentiment"]),
        category=result["category"]["label"],
        category_confidence=top_score(result["category"]),
        urgency=result["urgency"]["label"],
        urgency_confidence=top_score(result["urgency"]),
        routing_action=routing["action"],
        routing_reason=routing_reason,
        needs_human=needs_human,
        channel=request.channel or "web",
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    result["routing"] = routing
    return result


# Hard cap so a single request can never pull the entire table into memory.
# This is a stopgap, not real pagination — the frontend still expects a
# plain array back. Real pagination needs a frontend change too.
MAX_RESULTS_LIMIT = 2000
DEFAULT_RESULTS_LIMIT = 500


@router.get("/messages")
def get_messages(
    sentiment: Optional[str] = None,
    category: Optional[str] = None,
    urgency: Optional[str] = None,
    channel: Optional[str] = None,
    customer_id: Optional[str] = None,
    conversation_id: Optional[int] = None,
    limit: int = DEFAULT_RESULTS_LIMIT,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Message)

    # Agents can only see messages from their assigned conversations
    if current_user.role == "agent":
        assigned_ids = get_agent_assigned_conversation_ids(db, current_user)
        query = query.filter(Message.conversation_id.in_(assigned_ids))

    if sentiment:
        query = query.filter(Message.sentiment == sentiment)
    if category:
        query = query.filter(Message.category == category)
    if urgency:
        query = query.filter(Message.urgency == urgency)
    if channel:
        query = query.filter(Message.channel == channel)
    if customer_id:
        query = query.filter(Message.customer_id == customer_id)
    if conversation_id:
        query = query.filter(Message.conversation_id == conversation_id)

    capped_limit = max(1, min(limit, MAX_RESULTS_LIMIT))
    messages = query.order_by(Message.created_at.desc()).limit(capped_limit).all()
    return [message_to_dict(msg) for msg in messages]



@router.get("/messages/search")
def search_messages(
    q: str,
    limit: int = DEFAULT_RESULTS_LIMIT,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Message).filter(Message.text.contains(q))

    if current_user.role == "agent":
        assigned_ids = get_agent_assigned_conversation_ids(db, current_user)
        query = query.filter(Message.conversation_id.in_(assigned_ids))

    capped_limit = max(1, min(limit, MAX_RESULTS_LIMIT))
    messages = query.order_by(Message.created_at.desc()).limit(capped_limit).all()
    return [message_to_dict(msg) for msg in messages]


@router.get("/messages/low-confidence")
def get_low_confidence_messages(
    threshold: float = 0.6,
    limit: int = DEFAULT_RESULTS_LIMIT,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Message).filter(
        (Message.sentiment_confidence < threshold) |
        (Message.category_confidence < threshold) |
        (Message.urgency_confidence < threshold)
    )

    if current_user.role == "agent":
        assigned_ids = get_agent_assigned_conversation_ids(db, current_user)
        query = query.filter(Message.conversation_id.in_(assigned_ids))

    capped_limit = max(1, min(limit, MAX_RESULTS_LIMIT))
    messages = query.order_by(Message.created_at.desc()).limit(capped_limit).all()
    return [message_to_dict(msg) for msg in messages]


@router.get("/messages/{message_id}")
def get_message_by_id(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    msg = db.query(Message).filter(Message.id == message_id).first()

    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")

    check_message_access(msg, db, current_user)
    return message_to_dict(msg)


@router.get("/conversations/{conversation_id}")
def get_conversation_detail(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_conversation_access(conversation_id, db, current_user)

    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    return {
        "conversation": {
            "id": conversation.id,
            "customer_id": conversation.customer_id,
            "channel": conversation.channel,
            "status": conversation.status,
            "assigned_agent": conversation.assigned_agent,
            "agent_note": conversation.agent_note,
            "bot_enabled": bool(getattr(conversation, "bot_enabled", True)),
            "created_at": conversation.created_at
        },
        "messages": [message_to_dict(msg) for msg in messages]
    }


@router.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_conversation_access(conversation_id, db, current_user)

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    return [message_to_dict(msg) for msg in messages]


@router.get("/conversations")
def get_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Message.conversation_id).filter(
        Message.conversation_id.isnot(None)
    )

    if current_user.role == "agent":
        assigned_ids = get_agent_assigned_conversation_ids(db, current_user)
        query = query.filter(Message.conversation_id.in_(assigned_ids))

    conversations = query.distinct().all()
    result = []

    for conv in conversations:
        conversation_id = conv[0]

        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )

        last_message = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .first()
        )

        message_count = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .count()
        )

        result.append({
            "conversation_id": conversation_id,
            "customer_id": last_message.customer_id,
            "customer_db_id": getattr(last_message, "customer_db_id", None),
            "channel": last_message.channel,
            "message_type": getattr(last_message, "message_type", "text"),
            "last_message": last_message.text,
            "last_message_sender_type": getattr(last_message, "sender_type", "customer"),
            "last_sentiment": last_message.sentiment,
            "last_category": last_message.category,
            "last_urgency": last_message.urgency,
            "message_count": message_count,
            "assigned_agent": conversation.assigned_agent if conversation else None,
            "status": conversation.status if conversation else None,
            "bot_enabled": bool(getattr(conversation, "bot_enabled", True)) if conversation else True,
            "needs_human": bool(getattr(last_message, "needs_human", False)),
            "matched_faq_id": getattr(last_message, "matched_faq_id", None),
            "last_updated": last_message.created_at
        })

    return result


@router.get("/analytics/summary")
def analytics_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["manager", "super_admin"]))
):
    # Analytics should count customer messages only, not bot replies.
    customer_messages_query = db.query(Message).filter(Message.sender_type == "customer")
    total_messages = customer_messages_query.count()

    negative_messages = customer_messages_query.filter(Message.sentiment == "negative").count()
    neutral_messages = customer_messages_query.filter(Message.sentiment == "neutral").count()
    positive_messages = customer_messages_query.filter(Message.sentiment == "positive").count()

    complaints = customer_messages_query.filter(Message.category == "complaint").count()
    inquiries = customer_messages_query.filter(Message.category == "inquiry").count()
    requests = customer_messages_query.filter(Message.category == "request").count()
    feedback = customer_messages_query.filter(Message.category == "feedback").count()
    other = customer_messages_query.filter(Message.category == "other").count()

    # Normalize urgency exactly like the frontend cards:
    #   normal/low -> Low, urgent/medium or human_handoff -> Medium,
    #   critical/high or escalation -> High.
    # This prevents the Analytics page from showing a fixed High percentage while
    # the message list is already displaying those rows as High.
    from sqlalchemy import func, case, or_

    final_urgency = func.lower(func.trim(func.coalesce(Message.corrected_urgency, Message.urgency, "normal")))
    final_action = func.lower(func.trim(func.coalesce(Message.routing_action, "")))

    urgency_bucket = case(
        (or_(
            final_urgency.in_(["critical", "high", "escalation", "escalated"]),
            final_action.in_(["escalation", "escalate"]),
        ), "critical"),
        (or_(
            final_urgency.in_(["urgent", "medium"]),
            final_action.in_(["human_handoff", "handoff", "pending_human"]),
        ), "urgent"),
        else_="normal",
    )

    bucket_counts = {"normal": 0, "urgent": 0, "critical": 0}
    for bucket, count in (
        db.query(urgency_bucket.label("bucket"), func.count(Message.id))
        .filter(Message.sender_type == "customer")
        .group_by(urgency_bucket)
        .all()
    ):
        bucket_counts[str(bucket or "normal")] = int(count or 0)

    normal_messages = bucket_counts["normal"]
    urgent_messages = bucket_counts["urgent"]
    critical_messages = bucket_counts["critical"]

    total_conversations = (
        db.query(Message.conversation_id)
        .filter(Message.conversation_id.isnot(None))
        .distinct()
        .count()
    )

    return {
        "total_messages": total_messages,
        "total_conversations": total_conversations,
        "sentiment": {
            "negative": negative_messages,
            "neutral": neutral_messages,
            "positive": positive_messages
        },
        "category": {
            "complaint": complaints,
            "inquiry": inquiries,
            "request": requests,
            "feedback": feedback,
            "other": other
        },
        "urgency": {
            "normal": normal_messages,
            "urgent": urgent_messages,
            "critical": critical_messages
        }
    }


@router.patch("/conversations/{conversation_id}/status")
def update_conversation_status(
    conversation_id: int,
    request: ConversationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_conversation_access(conversation_id, db, current_user)

    allowed_statuses = ["active", "pending_human", "escalated", "resolved", "closed"]

    if request.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")

    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if conversation is None:
        if current_user.role == "agent":
            raise HTTPException(status_code=403, detail="Agent cannot create conversation records")
        conversation = Conversation(id=conversation_id, status=request.status)
        db.add(conversation)
    else:
        conversation.status = request.status

    db.commit()
    db.refresh(conversation)

    return {
        "conversation_id": conversation.id,
        "status": conversation.status,
        "message": "Conversation status updated successfully"
    }


@router.delete("/messages/{message_id}")
def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin"]))
):
    msg = db.query(Message).filter(Message.id == message_id).first()

    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")

    db.delete(msg)
    db.commit()

    return {
        "message": "Message deleted successfully",
        "deleted_message_id": message_id
    }


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin"]))
):
    messages = db.query(Message).filter(Message.conversation_id == conversation_id).all()

    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found")

    for msg in messages:
        db.delete(msg)

    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation:
        db.delete(conversation)

    db.commit()

    return {
        "message": "Conversation deleted successfully",
        "deleted_conversation_id": conversation_id,
        "deleted_messages_count": len(messages)
    }


@router.patch("/messages/{message_id}/feedback")
def update_message_feedback(
    message_id: int,
    request: MessageFeedbackUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    msg = db.query(Message).filter(Message.id == message_id).first()

    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")

    check_message_access(msg, db, current_user)

    if request.corrected_sentiment is not None:
        msg.corrected_sentiment = request.corrected_sentiment

    if request.corrected_category is not None:
        msg.corrected_category = request.corrected_category

    if request.corrected_urgency is not None:
        msg.corrected_urgency = request.corrected_urgency

    if request.feedback_note is not None:
        msg.feedback_note = request.feedback_note

    db.commit()
    db.refresh(msg)

    return {
        "message": "Feedback updated successfully",
        "message_id": msg.id,
        "original": {
            "sentiment": msg.sentiment,
            "category": msg.category,
            "urgency": msg.urgency
        },
        "corrected": {
            "sentiment": msg.corrected_sentiment,
            "category": msg.corrected_category,
            "urgency": msg.corrected_urgency
        },
        "feedback_note": msg.feedback_note
    }


@router.patch("/conversations/{conversation_id}/note")
def update_conversation_note(
    conversation_id: int,
    request: ConversationNoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_conversation_access(conversation_id, db, current_user)

    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if conversation is None:
        if current_user.role == "agent":
            raise HTTPException(status_code=403, detail="Agent cannot create conversation records")
        conversation = Conversation(id=conversation_id)

    conversation.agent_note = request.note

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return {
        "message": "Conversation note updated successfully",
        "conversation_id": conversation.id,
        "agent_note": conversation.agent_note
    }


@router.patch("/conversations/{conversation_id}/assign")
def assign_conversation_agent(
    conversation_id: int,
    request: ConversationAssignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["manager", "super_admin"]))
):
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if conversation is None:
        conversation = Conversation(id=conversation_id)

    conversation.assigned_agent = request.assigned_agent

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return {
        "message": "Conversation assigned successfully",
        "conversation_id": conversation.id,
        "assigned_agent": conversation.assigned_agent
    }


@router.post("/conversations/{conversation_id}/reply")
async def reply_to_conversation(
    conversation_id: int,
    request: ConversationReplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lets an agent send a manual reply to the customer from the dashboard.
    Sending a manual reply automatically pauses the bot for this
    conversation, since a human has taken over.
    """
    check_conversation_access(conversation_id, db, current_user)

    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    text = request.text.strip()

    if not text:
        raise HTTPException(status_code=400, detail="Reply text is required")

    whatsapp_send = None
    instagram_send = None

    if conversation.channel == "whatsapp" and conversation.customer_id:
        from app.routes.whatsapp import send_whatsapp_message
        whatsapp_send = await send_whatsapp_message(conversation.customer_id, text)

    if conversation.channel == "instagram" and conversation.customer_id:
        from app.routes.instagram import send_instagram_message
        instagram_send = await send_instagram_message(conversation.customer_id, text)

    message = Message(
        conversation_id=conversation.id,
        customer_id=conversation.customer_id,
        customer_db_id=conversation.customer_db_id,
        text=text,
        sender_type="agent",
        message_type="text",
        channel=conversation.channel,
        sentiment="neutral",
        category="other",
        urgency="normal",
        routing_action="agent_reply",
        routing_reason=f"manual_reply_by={current_user.email}",
        needs_human=False,
    )

    db.add(message)

    # A human just replied, so stop the bot from auto-replying on top of it.
    conversation.bot_enabled = False
    db.add(conversation)

    db.commit()
    db.refresh(message)
    await broadcast_dashboard_event({
        "type": "new_message",
        "channel": conversation.channel,
        "conversation_id": conversation.id,
        "message_id": message.id,
        "sender_type": "agent",
    })

    return {
        "message": "Reply sent successfully",
        "sent_message": message_to_dict(message),
        "whatsapp_send": whatsapp_send,
        "instagram_send": instagram_send,
        "bot_enabled": conversation.bot_enabled,
    }


@router.patch("/conversations/{conversation_id}/bot")
def toggle_conversation_bot(
    conversation_id: int,
    request: ConversationBotToggleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Turn the bot on/off for a single conversation (human takeover toggle)."""
    check_conversation_access(conversation_id, db, current_user)

    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if conversation is None:
        if current_user.role == "agent":
            raise HTTPException(status_code=403, detail="Agent cannot create conversation records")
        conversation = Conversation(id=conversation_id)

    conversation.bot_enabled = request.enabled

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return {
        "message": "Bot status updated successfully",
        "conversation_id": conversation.id,
        "bot_enabled": conversation.bot_enabled,
    }