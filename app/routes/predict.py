from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.model.infer import predict
from app.services.routing import decide_route
from app.database.db import get_db
from app.database.models import Message, Conversation, User, Customer, CustomerChannel
from app.schemas.message import (
    MessageRequest,
    PredictionResponse,
    ConversationStatusUpdate,
    MessageFeedbackUpdate,
    ConversationNoteUpdate,
    ConversationAssignUpdate
)
from app.security import get_current_user, require_roles

router = APIRouter()


def top_score(item: dict) -> float:
    label = item["label"]
    return item["scores"].get(label)


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
    routing = decide_route(result)

    customer = get_or_create_customer_for_channel(db, request.channel or "web", request.customer_id)

    conversation_id = request.conversation_id
    if conversation_id is None and request.customer_id:
        conversation = (
            db.query(Conversation)
            .filter(Conversation.customer_id == request.customer_id, Conversation.channel == (request.channel or "web"))
            .first()
        )
        if conversation is None:
            conversation = Conversation(
                customer_id=request.customer_id,
                customer_db_id=customer.id if customer else None,
                channel=request.channel or "web",
                status="active",
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
        conversation_id = conversation.id

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
        routing_reason=routing["reason"],
        channel=request.channel or "web",
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    result["routing"] = routing
    return result


@router.get("/messages")
def get_messages(
    sentiment: Optional[str] = None,
    category: Optional[str] = None,
    urgency: Optional[str] = None,
    channel: Optional[str] = None,
    customer_id: Optional[str] = None,
    conversation_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Message)

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

    messages = query.order_by(Message.created_at.desc()).all()
    return [message_to_dict(msg) for msg in messages]


@router.get("/messages/search")
def search_messages(
    q: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Message).filter(Message.text.contains(q))

    if current_user.role == "agent":
        assigned_ids = get_agent_assigned_conversation_ids(db, current_user)
        query = query.filter(Message.conversation_id.in_(assigned_ids))

    messages = query.order_by(Message.created_at.desc()).all()
    return [message_to_dict(msg) for msg in messages]


@router.get("/messages/low-confidence")
def get_low_confidence_messages(
    threshold: float = 0.6,
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

    messages = query.order_by(Message.created_at.desc()).all()
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

    urgent_messages = customer_messages_query.filter(Message.urgency == "urgent").count()
    critical_messages = customer_messages_query.filter(Message.urgency == "critical").count()
    normal_messages = customer_messages_query.filter(Message.urgency == "normal").count()

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