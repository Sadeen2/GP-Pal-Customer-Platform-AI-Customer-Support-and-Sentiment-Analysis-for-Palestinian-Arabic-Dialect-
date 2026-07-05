import hmac
import hashlib
import json
import os
import time
import asyncio
import httpx

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.realtime import broadcast_dashboard_event

from app.database.db import get_db
from app.database.models import Message, Conversation, MessageAttachment
from app.services.bot_service import handle_bot_message
from app.services.assignment_service import auto_assign_conversation, should_auto_assign
from app.services.customer_identity_service import get_or_create_customer_channel

# Reuse the safe helpers already proven in the WhatsApp integration.
from app.routes.whatsapp import (
    safe_predict,
    top_score,
    safe_faq_id,
    short_text,
    is_duplicate_message,
    is_duplicate_message_in_db,
)


load_dotenv()

router = APIRouter(tags=["Instagram"])

VERIFY_TOKEN = os.getenv("INSTAGRAM_VERIFY_TOKEN") or os.getenv("WHATSAPP_VERIFY_TOKEN", "pal_customer_verify")
META_APP_SECRET = (os.getenv("META_APP_SECRET") or os.getenv("WHATSAPP_APP_SECRET") or "").strip()
DEBUG_INSTAGRAM_BODY = os.getenv("INSTAGRAM_DEBUG_BODY", "false").lower() == "true"
VERBOSE_INSTAGRAM_SEND = os.getenv("INSTAGRAM_VERBOSE_SEND", "false").lower() == "true"
# During local development Meta test/echo requests sometimes arrive with no/invalid signature.
# Keep strict mode off to prevent endless retries; set true in production after the App Secret is confirmed.
STRICT_INSTAGRAM_SIGNATURE = os.getenv("INSTAGRAM_SIGNATURE_STRICT", "false").lower() == "true"


def log(message: str):
    print(f"[instagram] {message}")


def get_instagram_credentials():
    return {
        "token": os.getenv("INSTAGRAM_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN"),
        "ig_business_account_id": os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID"),
        "graph_version": os.getenv("INSTAGRAM_GRAPH_VERSION") or os.getenv("WHATSAPP_GRAPH_VERSION", "v21.0"),
    }


def _clean_env_value(value: str | None) -> str:
    return (value or "").strip().strip('"').strip("'")


def get_own_instagram_ids() -> set[str]:
    """IDs that represent the connected business account/page, not a customer.

    Meta may send echo/delivery/seen events for messages sent by the page/business.
    If we process those as customer messages, the bot replies to itself and creates
    a loop.
    """
    ids = {
        _clean_env_value(os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")),
        _clean_env_value(os.getenv("INSTAGRAM_PAGE_ID")),
        _clean_env_value(os.getenv("FACEBOOK_PAGE_ID")),
    }
    # Optional comma-separated list for any extra IDs you see in logs.
    extra = _clean_env_value(os.getenv("INSTAGRAM_OWN_IDS"))
    if extra:
        ids.update(x.strip() for x in extra.split(",") if x.strip())
    return {x for x in ids if x}


def is_own_instagram_sender(sender_id: str | None) -> bool:
    return str(sender_id or "").strip() in get_own_instagram_ids()


_signature_warning_logged = False


def verify_meta_signature(request: Request, raw_body: bytes) -> bool:
    """Verify Meta's X-Hub-Signature-256 header when META_APP_SECRET is set."""
    global _signature_warning_logged

    if not META_APP_SECRET:
        if not _signature_warning_logged:
            log("META_APP_SECRET is not set — Instagram webhook signature verification is disabled.")
            _signature_warning_logged = True
        return True

    signature_header = request.headers.get("x-hub-signature-256", "")
    if not signature_header.startswith("sha256="):
        return False

    expected_signature = signature_header.split("sha256=", 1)[1].strip()
    computed_signature = hmac.new(
        META_APP_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed_signature, expected_signature)


async def send_instagram_message(recipient_id: str, text: str):
    """Send a text reply through the Instagram Messaging API."""
    creds = get_instagram_credentials()
    token = creds["token"]
    ig_business_account_id = creds["ig_business_account_id"]
    graph_version = creds["graph_version"]

    if not token or not ig_business_account_id:
        log(
            "credentials missing | "
            f"token_exists={bool(token)} | ig_business_account_id_exists={bool(ig_business_account_id)}"
        )
        return {"sent": False, "reason": "credentials_missing"}

    url = f"https://graph.instagram.com/{graph_version}/me/messages"
    payload = {
        "recipient": {"id": str(recipient_id)},
        "message": {"text": text[:1000]},
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    last_result = None
    for attempt in range(1, 4):
        try:
            log(f"sending reply attempt={attempt} to={recipient_id}")
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, json=payload, headers=headers)

            sent = response.status_code in [200, 201]
            last_result = {
                "sent": sent,
                "status_code": response.status_code,
                "response": response.text,
                "attempt": attempt,
            }

            if sent:
                log(f"reply sent ok | status={response.status_code}")
                if VERBOSE_INSTAGRAM_SEND:
                    log(f"send response: {short_text(response.text, 800)}")
                return last_result

            log(f"reply send failed | status={response.status_code} | response={short_text(response.text, 800)}")
            if response.status_code in [500, 502, 503, 504]:
                await asyncio.sleep(2 * attempt)
                continue
            return last_result

        except Exception as e:
            log(f"send error attempt={attempt}: {short_text(str(e), 800)}")
            last_result = {"sent": False, "reason": str(e), "attempt": attempt}
            await asyncio.sleep(2 * attempt)

    return last_result or {"sent": False, "reason": "unknown_error"}


def extract_instagram_event(body: dict) -> dict | None:
    """
    Supports the common Instagram Messaging webhook shape:
    { entry: [{ messaging: [{ sender: {id}, message: {mid, text} }]}] }

    Also supports a fallback Meta 'changes' shape for comment-like payloads.
    """
    try:
        for entry in body.get("entry", []):
            for item in entry.get("messaging", []):
                sender_id = str((item.get("sender") or {}).get("id") or "").strip()
                recipient_id = str((item.get("recipient") or {}).get("id") or "").strip()
                message = item.get("message") or {}
                message_id = message.get("mid") or message.get("id")
                text = (message.get("text") or "").strip()
                is_echo = bool(message.get("is_echo"))

                if sender_id and (text or message_id):
                    return {
                        "sender_id": sender_id,
                        "recipient_id": recipient_id,
                        "message_id": f"instagram:{message_id or sender_id + '-' + str(int(time.time()))}",
                        "text": text,
                        "message_type": "text" if text else "unsupported",
                        "is_echo": is_echo,
                        "raw": item,
                    }

            for change in entry.get("changes", []):
                value = change.get("value") or {}
                text = (value.get("text") or value.get("message") or "").strip()
                from_obj = value.get("from") or {}
                sender_id = str(from_obj.get("id") or value.get("from_id") or "").strip()
                message_id = value.get("id") or value.get("comment_id")

                if sender_id and text:
                    return {
                        "sender_id": sender_id,
                        "message_id": f"instagram:{message_id or sender_id + '-' + str(int(time.time()))}",
                        "text": text,
                        "message_type": "comment",
                        "is_echo": False,
                        "raw": change,
                    }
    except Exception:
        return None

    return None


def get_or_create_instagram_conversation(sender_id: str, text: str, db: Session):
    customer, _link, identity_meta = get_or_create_customer_channel(
        db=db,
        channel="instagram",
        external_id=sender_id,
        display_name=sender_id,
        evidence_text=text,
    )

    conversation = db.query(Conversation).filter(
        Conversation.customer_id == sender_id,
        Conversation.channel == "instagram",
    ).first()

    if conversation is None:
        conversation = Conversation(
            customer_id=sender_id,
            customer_db_id=customer.id if customer else None,
            channel="instagram",
            external_conversation_id=sender_id,
            status="open",
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        log(f"created conversation id={conversation.id} sender={sender_id} customer_db_id={conversation.customer_db_id}")
    else:
        changed = False
        if customer and not conversation.customer_db_id:
            conversation.customer_db_id = customer.id
            changed = True
        if not conversation.external_conversation_id:
            conversation.external_conversation_id = sender_id
            changed = True
        if changed:
            db.add(conversation)
            db.commit()
            db.refresh(conversation)

    return conversation, identity_meta


def save_instagram_bot_reply_message(
    db: Session,
    conversation_id: int,
    customer_id: str,
    reply: str,
    bot_result: dict,
    incoming_message_id: int | None = None,
    customer_db_id: int | None = None,
):
    bot_message = Message(
        conversation_id=conversation_id,
        customer_id=customer_id,
        customer_db_id=customer_db_id,
        text=reply,
        sender_type="bot",
        message_type="text",
        sentiment=bot_result.get("sentiment") or "neutral",
        sentiment_confidence=bot_result.get("sentiment_confidence"),
        category=bot_result.get("category") or "other",
        category_confidence=None,
        urgency="normal",
        urgency_confidence=None,
        routing_action="bot_reply",
        routing_reason=f"reply_to_message_id={incoming_message_id}; source=bot_service",
        matched_faq_id=safe_faq_id(db, bot_result.get("faq_id")),
        needs_human=bool(bot_result.get("needs_human", False)),
        channel="instagram",
    )
    db.add(bot_message)
    db.commit()
    db.refresh(bot_message)
    return bot_message


@router.get("/webhooks/instagram/", response_class=PlainTextResponse)
@router.get("/webhooks/instagram", response_class=PlainTextResponse)
@router.get("/api/instagram/webhook", response_class=PlainTextResponse)
@router.get("/api/instagram/webhook/", response_class=PlainTextResponse)
def verify_instagram_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    log(
        "webhook verification request | "
        f"mode={hub_mode} | token_ok={hub_verify_token == VERIFY_TOKEN} | challenge_exists={bool(hub_challenge)}"
    )

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge or "")

    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhooks/instagram/")
@router.post("/webhooks/instagram")
@router.post("/api/instagram/webhook")
@router.post("/api/instagram/webhook/")
async def receive_instagram_message(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        raw_body = await request.body()
    except Exception as e:
        # Meta may disconnect retry/test requests while the local tunnel is restarting.
        log(f"ignored webhook | reason=client_disconnected | detail={short_text(str(e), 200)}")
        return {"status": "ignored", "reason": "client_disconnected"}

    if not verify_meta_signature(request, raw_body):
        log("rejected webhook | reason=invalid_signature")
        if STRICT_INSTAGRAM_SIGNATURE:
            raise HTTPException(status_code=403, detail="Invalid signature")
        return {"status": "ignored", "reason": "invalid_signature"}

    try:
        body = json.loads(raw_body)
    except ValueError:
        log("ignored webhook | reason=invalid_json")
        return {"status": "ignored", "reason": "invalid_json"}

    if DEBUG_INSTAGRAM_BODY:
        log(f"raw body: {short_text(body, 3000)}")

    try:
        event = extract_instagram_event(body)
        if not event:
            log("ignored webhook | reason=no_supported_instagram_message")
            return {"status": "ignored", "reason": "no_supported_instagram_message"}

        sender_id = event["sender_id"]
        recipient_id = event.get("recipient_id")
        external_message_id = event["message_id"]
        text = (event.get("text") or "").strip()
        message_type = event.get("message_type") or "text"

        # Critical: ignore echoes/outgoing messages from our own Instagram business account.
        # Without this, Meta sends the bot's sent reply back to the webhook and the bot
        # stores it as a customer message, then replies to itself forever.
        if event.get("is_echo") or is_own_instagram_sender(sender_id):
            log(
                "ignored webhook | reason=self_echo_or_own_sender | "
                f"sender={sender_id} | recipient={recipient_id} | message_id={short_text(external_message_id, 80)}"
            )
            return {"status": "ignored", "reason": "self_echo_or_own_sender", "sender_id": sender_id}

        if is_duplicate_message(external_message_id) or is_duplicate_message_in_db(db, external_message_id):
            log(f"duplicate message ignored | message_id={short_text(external_message_id, 80)}")
            return {"status": "ignored", "reason": "duplicate_message", "message_id": external_message_id}

        if not text:
            reply = "حاليًا بدعم رسائل إنستغرام النصية فقط. اكتبلي طلبك برسالة 😊"
            send_result = await send_instagram_message(sender_id, reply)
            return {"status": "unsupported_message_ignored", "type": message_type, "reply": reply, "instagram_send": send_result}

        log(f"new message | sender={sender_id} | message_id={short_text(external_message_id, 80)} | text={short_text(text)}")

        conversation, identity_meta = get_or_create_instagram_conversation(sender_id, text, db)

        if not getattr(conversation, "bot_enabled", True):
            result = safe_predict(text)

            assignment = None
            if not conversation.assigned_agent:
                assignment = auto_assign_conversation(
                    db=db,
                    conversation=conversation,
                    reason="bot_already_paused_instagram_followup",
                    status="pending_human",
                    disable_bot=True,
                )

            routing_reason = "bot_paused_for_conversation; a human agent is handling this chat"
            routing_reason += f"; identity={identity_meta}"
            if assignment:
                routing_reason += f"; auto_assignment={assignment}"

            saved_message = Message(
                conversation_id=conversation.id,
                customer_id=sender_id,
                customer_db_id=conversation.customer_db_id,
                text=text,
                sender_type="customer",
                message_type="text",
                external_message_id=external_message_id,
                sentiment=result["sentiment"]["label"],
                sentiment_confidence=top_score(result["sentiment"]),
                category=result["category"]["label"],
                category_confidence=top_score(result["category"]),
                urgency=result["urgency"]["label"],
                urgency_confidence=top_score(result["urgency"]),
                routing_action="awaiting_agent",
                routing_reason=routing_reason,
                needs_human=True,
                channel="instagram",
            )
            db.add(saved_message)
            db.commit()
            db.refresh(saved_message)

            log(f"bot paused for conversation={conversation.id} | saved message id={saved_message.id}")
            await broadcast_dashboard_event({
                "type": "new_message",
                "channel": "instagram",
                "conversation_id": conversation.id,
                "message_id": saved_message.id,
                "sender_type": "customer",
                "routing_action": "awaiting_agent",
            })
            return {
                "status": "received_bot_paused",
                "message_id": saved_message.id,
                "conversation_id": conversation.id,
                "from": sender_id,
                "text": text,
                "identity": identity_meta,
            }

        result = safe_predict(text)
        bot_result = handle_bot_message(
            text,
            session_id=f"instagram:{sender_id}",
            prediction_result=result,
        )

        reply = bot_result.get("reply", "تم استلام رسالتك بنجاح.")
        action = bot_result.get("action", "unknown")
        intent = bot_result.get("intent")
        faq_score = bot_result.get("faq_score")
        matched_faq = bot_result.get("matched_faq")
        faq_id = bot_result.get("faq_id")
        needs_human = bot_result.get("needs_human", False)
        category_from_bot = bot_result.get("category")
        session = bot_result.get("session")

        sentiment_label = result["sentiment"]["label"]
        sentiment_confidence = top_score(result["sentiment"])
        category_label = result["category"]["label"]
        category_confidence = top_score(result["category"])
        urgency_label = result["urgency"]["label"]
        urgency_confidence = top_score(result["urgency"])

        routing_reason = (
            f"source=bot_service; channel=instagram; "
            f"action={action}; intent={intent}; faq_score={faq_score}; "
            f"matched_faq={matched_faq}; faq_id={faq_id}; needs_human={needs_human}; "
            f"bot_category={category_from_bot}; session={session}; identity={identity_meta}"
        )

        must_assign = should_auto_assign(
            action=action,
            needs_human=bool(needs_human),
            urgency=urgency_label,
            sentiment=sentiment_label,
            category=category_label,
        )

        assignment = None
        if must_assign:
            assignment_status = "escalated" if action in ["escalation", "escalate"] or urgency_label == "critical" else "pending_human"
            assignment = auto_assign_conversation(
                db=db,
                conversation=conversation,
                reason=f"instagram_action={action}; urgency={urgency_label}; category={category_label}; needs_human={needs_human}",
                status=assignment_status,
                disable_bot=True,
            )
            routing_reason += f"; auto_assignment={assignment}"

        saved_message = Message(
            conversation_id=conversation.id,
            customer_id=sender_id,
            customer_db_id=conversation.customer_db_id,
            text=text,
            sender_type="customer",
            message_type="text",
            external_message_id=external_message_id,
            sentiment=sentiment_label,
            sentiment_confidence=sentiment_confidence,
            category=category_label,
            category_confidence=category_confidence,
            urgency=urgency_label,
            urgency_confidence=urgency_confidence,
            routing_action=action,
            routing_reason=routing_reason,
            matched_faq_id=safe_faq_id(db, faq_id),
            needs_human=bool(needs_human) or must_assign,
            channel="instagram",
        )
        db.add(saved_message)
        db.commit()
        db.refresh(saved_message)

        log(f"saved customer message | id={saved_message.id} | conversation={conversation.id}")
        log(f"bot decision | action={action} | intent={intent} | faq_score={faq_score} | needs_human={needs_human}")
        await broadcast_dashboard_event({
            "type": "new_message",
            "channel": "instagram",
            "conversation_id": conversation.id,
            "message_id": saved_message.id,
            "sender_type": "customer",
            "routing_action": action,
            "needs_human": bool(needs_human) or must_assign,
        })

        send_result = await send_instagram_message(sender_id, reply)
        saved_bot_message = save_instagram_bot_reply_message(
            db=db,
            conversation_id=conversation.id,
            customer_id=sender_id,
            reply=reply,
            bot_result=bot_result,
            incoming_message_id=saved_message.id,
            customer_db_id=conversation.customer_db_id,
        )
        await broadcast_dashboard_event({
            "type": "new_message",
            "channel": "instagram",
            "conversation_id": conversation.id,
            "message_id": saved_bot_message.id,
            "sender_type": "bot",
        })

        return {
            "status": "received",
            "message_id": saved_message.id,
            "bot_message_id": saved_bot_message.id,
            "instagram_message_id": external_message_id,
            "conversation_id": conversation.id,
            "from": sender_id,
            "text": text,
            "reply": reply,
            "instagram_send": send_result,
            "identity": identity_meta,
            "customer_db_id": conversation.customer_db_id,
            "sentiment": sentiment_label,
            "sentiment_confidence": sentiment_confidence,
            "category": category_label,
            "category_confidence": category_confidence,
            "urgency": urgency_label,
            "urgency_confidence": urgency_confidence,
            "routing_action": action,
            "routing_reason": routing_reason,
            "bot": bot_result,
            "auto_assignment": assignment,
        }

    except Exception as e:
        db.rollback()
        log(f"webhook error: {short_text(str(e), 1000)}")
        return {"status": "error", "detail": str(e)}
