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
from app.database.models import Message, Conversation, Customer, CustomerChannel, MessageAttachment, FAQItem
from app.model.infer import predict
from app.services.bot_service import handle_bot_message
from app.services.voice_service import transcribe_whatsapp_audio
from app.services.assignment_service import auto_assign_conversation, should_auto_assign
from app.services.urgency import apply_critical_urgency_rule
from app.services.customer_identity_service import get_or_create_customer_channel as resolve_customer_channel


load_dotenv()

router = APIRouter(tags=["WhatsApp"])

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "pal_customer_verify")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "").strip()

# Optional debug flags.
# Keep them false by default so the terminal stays clean.
DEBUG_WHATSAPP_BODY = os.getenv("WHATSAPP_DEBUG_BODY", "false").lower() == "true"
VERBOSE_WHATSAPP_SEND = os.getenv("WHATSAPP_VERBOSE_SEND", "false").lower() == "true"

# Prevent duplicate replies when Meta resends the same webhook message.
PROCESSED_MESSAGE_IDS = {}
PROCESSED_TTL_SECONDS = 10 * 60  # 10 minutes

# Backward-compatible mapping for old hardcoded bot ids.
# matched_faq_id has a foreign key to faq_items.id, so only real FAQ ids
# may be saved there. Unknown internal ids become NULL.
BUILTIN_FAQ_ID_MAP = {
    "greeting_builtin": "greeting_001",
    "small_talk_builtin": "how_are_you_001",
    "acknowledgement_builtin": "ok_understood_001",
    "acknowledgement": "ok_understood_001",
    "service_complaint_builtin": "complaint_general_001",
    "order_cancel_builtin": "order_cancel_001",
    "order_status_builtin": "order_status_001",
    "order_request_builtin": "order_reservation_001",
    "delivery_request_builtin": "delivery_general_001",
    "bot_wrong_reply_builtin": "bot_wrong_reply_001",
    "store_location_builtin": "store_location_001",
    "product_catalog_builtin": "ask_specific_model_001",
    "openai_router": None,
    "cancel_context": None,
    "delivery_location_followup": None,
    "order_details_followup": None,
    "product_info_followup": None,
}


def normalize_faq_id(faq_id):
    if not faq_id:
        return None
    faq_id = str(faq_id).strip()
    return BUILTIN_FAQ_ID_MAP.get(faq_id, faq_id)


def safe_faq_id(db: Session, faq_id):
    normalized = normalize_faq_id(faq_id)
    if not normalized:
        return None

    exists = db.query(FAQItem.id).filter(FAQItem.id == normalized).first()
    return normalized if exists else None


def short_text(value, limit: int = 250) -> str:
    """Keep terminal logs readable."""
    value = "" if value is None else str(value)
    value = value.replace("\n", " ").replace("\r", " ").strip()

    if len(value) <= limit:
        return value

    return value[:limit] + "..."


def log(message: str):
    print(f"[whatsapp] {message}")


def is_duplicate_message(message_id: str) -> bool:
    if not message_id:
        return False

    now = time.time()

    # Remove old processed message ids.
    expired_ids = [
        mid for mid, ts in PROCESSED_MESSAGE_IDS.items()
        if now - ts > PROCESSED_TTL_SECONDS
    ]

    for mid in expired_ids:
        PROCESSED_MESSAGE_IDS.pop(mid, None)

    if message_id in PROCESSED_MESSAGE_IDS:
        return True

    PROCESSED_MESSAGE_IDS[message_id] = now
    return False


def get_whatsapp_credentials():
    """
    Read credentials dynamically from .env.
    This helps avoid stale values after editing .env.
    """
    return {
        "token": os.getenv("WHATSAPP_ACCESS_TOKEN"),
        "phone_number_id": os.getenv("WHATSAPP_PHONE_NUMBER_ID"),
        "graph_version": os.getenv("WHATSAPP_GRAPH_VERSION", "v21.0"),
    }


def top_score(item: dict) -> float:
    if not isinstance(item, dict):
        return 0.0

    label = item.get("label")
    scores = item.get("scores", {})

    if not isinstance(scores, dict):
        return 0.0

    try:
        return float(scores.get(label, 0.0))
    except Exception:
        return 0.0


def safe_predict(text: str) -> dict:
    """
    Runs the MARBERT/prediction model safely.
    Used for storing sentiment/category/urgency in the database.
    """
    try:
        result = predict(text)
        return apply_critical_urgency_rule(text, result)
    except Exception as e:
        log(f"prediction error: {short_text(str(e))}")
        return {
            "sentiment": {
                "label": "neutral",
                "scores": {"neutral": 0.0},
            },
            "category": {
                "label": "other",
                "scores": {"other": 0.0},
            },
            "urgency": {
                "label": "normal",
                "scores": {"normal": 0.0},
            },
        }


def get_or_create_customer_channel(db: Session, channel: str, external_id: str):
    """Find/create the real Customer and channel identity row.

    Uses the shared identity resolver so a WhatsApp number can be linked to an
    Instagram identity later when the same phone/email is detected.
    """
    customer, link, identity_meta = resolve_customer_channel(
        db=db,
        channel=channel,
        external_id=external_id,
        display_name=external_id,
        phone_hint=external_id if channel == "whatsapp" else None,
    )

    log(
        f"customer resolved | customer_id={customer.id} | channel={channel} | "
        f"external_id={external_id} | identity={identity_meta}"
    )
    return customer, link


def is_duplicate_message_in_db(db: Session, external_message_id: str | None) -> bool:
    if not external_message_id:
        return False

    existing = (
        db.query(Message.id)
        .filter(Message.external_message_id == external_message_id)
        .first()
    )
    return existing is not None


def get_or_create_whatsapp_conversation(from_number: str, db: Session):
    customer, _link = get_or_create_customer_channel(db, "whatsapp", from_number)

    conversation = db.query(Conversation).filter(
        Conversation.customer_id == from_number,
        Conversation.channel == "whatsapp",
    ).first()

    if conversation is None:
        conversation = Conversation(
            customer_id=from_number,
            customer_db_id=customer.id if customer else None,
            channel="whatsapp",
            status="open",
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        log(f"created conversation id={conversation.id} customer={from_number}")
    else:
        if customer and not conversation.customer_db_id:
            conversation.customer_db_id = customer.id
            db.commit()

    return conversation


async def send_whatsapp_message(to: str, text: str):
    creds = get_whatsapp_credentials()

    whatsapp_token = creds["token"]
    phone_number_id = creds["phone_number_id"]
    graph_version = creds["graph_version"]

    if not whatsapp_token or not phone_number_id:
        log(
            "credentials missing | "
            f"token_exists={bool(whatsapp_token)} | "
            f"phone_id_exists={bool(phone_number_id)}"
        )
        return {
            "sent": False,
            "reason": "credentials_missing",
        }

    url = f"https://graph.facebook.com/{graph_version}/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": text[:4000],
        },
    }

    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
        "Content-Type": "application/json",
    }

    last_result = None

    for attempt in range(1, 4):
        try:
            log(f"sending reply attempt={attempt} to={to}")

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                )

            sent = response.status_code in [200, 201]

            last_result = {
                "sent": sent,
                "status_code": response.status_code,
                "response": response.text,
                "attempt": attempt,
            }

            if sent:
                log(f"reply sent ok | status={response.status_code}")

                if VERBOSE_WHATSAPP_SEND:
                    log(f"send response: {short_text(response.text, 800)}")

                return last_result

            log(
                f"reply send failed | status={response.status_code} | "
                f"response={short_text(response.text, 800)}"
            )

            # Temporary Meta / WhatsApp errors.
            if response.status_code in [500, 502, 503, 504]:
                await asyncio.sleep(2 * attempt)
                continue

            # Auth / permission / bad request errors should not retry.
            return last_result

        except Exception as e:
            log(f"send error attempt={attempt}: {short_text(str(e), 800)}")

            last_result = {
                "sent": False,
                "reason": str(e),
                "attempt": attempt,
            }

            await asyncio.sleep(2 * attempt)

    return last_result or {
        "sent": False,
        "reason": "unknown_error",
    }


def save_bot_reply_message(
    db: Session,
    conversation_id: int,
    customer_id: str,
    reply: str,
    bot_result: dict,
    incoming_message_id: int = None,
    customer_db_id: int | None = None,
):
    """
    Store the bot response as a separate message row so the dashboard can
    display the full conversation timeline: customer -> bot -> customer -> bot.
    """
    sentiment = bot_result.get("sentiment") or "neutral"
    category = bot_result.get("category") or "other"

    safe_matched_faq_id = safe_faq_id(db, bot_result.get("faq_id"))

    bot_message = Message(
        conversation_id=conversation_id,
        customer_id=customer_id,
        customer_db_id=customer_db_id,
        text=reply,
        sender_type="bot",
        message_type="text",
        sentiment=sentiment,
        sentiment_confidence=bot_result.get("sentiment_confidence"),
        category=category,
        category_confidence=None,
        urgency="normal",
        urgency_confidence=None,
        routing_action="bot_reply",
        routing_reason=f"reply_to_message_id={incoming_message_id}; source=bot_service",
        matched_faq_id=safe_matched_faq_id,
        needs_human=bool(bot_result.get("needs_human", False)),
        channel="whatsapp",
    )

    db.add(bot_message)
    db.commit()
    db.refresh(bot_message)

    return bot_message


def extract_first_value(body: dict):
    """
    Safely extracts the first WhatsApp webhook value object.
    Returns None if the payload is not a standard Meta webhook payload.
    """
    try:
        entry = body.get("entry", [])[0]
        change = entry.get("changes", [])[0]
        return change.get("value", {})
    except Exception:
        return None


_signature_warning_logged = False


def verify_whatsapp_signature(request: Request, raw_body: bytes) -> bool:
    """
    Verifies Meta's X-Hub-Signature-256 header so only requests signed with
    our WhatsApp app secret are accepted. Without this, anyone who discovers
    the webhook URL can post fake customer messages.
    """
    global _signature_warning_logged

    if not WHATSAPP_APP_SECRET:
        if not _signature_warning_logged:
            log(
                "WHATSAPP_APP_SECRET is not set — webhook signature verification "
                "is DISABLED. Set it in .env (App Dashboard > Settings > Basic) "
                "to secure this endpoint."
            )
            _signature_warning_logged = True
        return True

    signature_header = request.headers.get("x-hub-signature-256", "")

    if not signature_header.startswith("sha256="):
        return False

    expected_signature = signature_header.split("sha256=", 1)[1].strip()

    computed_signature = hmac.new(
        WHATSAPP_APP_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed_signature, expected_signature)


def log_status_update(value: dict):
    statuses = value.get("statuses", []) if isinstance(value, dict) else []

    if not statuses:
        return

    status_obj = statuses[0]
    status = status_obj.get("status")
    recipient_id = status_obj.get("recipient_id")
    message_id = status_obj.get("id")

    log(
        f"status update | status={status} | "
        f"recipient={recipient_id} | message_id={short_text(message_id, 80)}"
    )


@router.get("/webhooks/whatsapp/", response_class=PlainTextResponse)
@router.get("/webhooks/whatsapp", response_class=PlainTextResponse)
@router.get("/api/whatsapp/webhook", response_class=PlainTextResponse)
@router.get("/api/whatsapp/webhook/", response_class=PlainTextResponse)
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    # Do not print the verify token to the terminal.
    log(
        "webhook verification request | "
        f"mode={hub_mode} | "
        f"token_ok={hub_verify_token == VERIFY_TOKEN} | "
        f"challenge_exists={bool(hub_challenge)}"
    )

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge or "")

    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhooks/whatsapp/")
@router.post("/webhooks/whatsapp")
@router.post("/api/whatsapp/webhook")
@router.post("/api/whatsapp/webhook/")
async def receive_whatsapp_message(
    request: Request,
    db: Session = Depends(get_db),
):
    raw_body = await request.body()

    if not verify_whatsapp_signature(request, raw_body):
        log("rejected webhook | reason=invalid_signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        body = json.loads(raw_body)
    except ValueError:
        log("ignored webhook | reason=invalid_json")
        return {"status": "ignored", "reason": "invalid_json"}

    if DEBUG_WHATSAPP_BODY:
        log(f"raw body: {short_text(body, 3000)}")

    try:
        value = extract_first_value(body)

        if value is None:
            log("ignored invalid webhook payload")
            return {
                "status": "ignored",
                "reason": "invalid_payload",
            }

        messages = value.get("messages", [])
        statuses = value.get("statuses", [])

        # Meta sends statuses: sent / delivered / read.
        # They do not contain new user text messages.
        if statuses and not messages:
            log_status_update(value)
            return {
                "status": "ignored",
                "reason": "status_update",
                "status": statuses[0].get("status"),
                "message_id": statuses[0].get("id"),
            }

        if not messages:
            log("ignored webhook with no messages")
            return {
                "status": "ignored",
                "reason": "no_messages",
            }

        msg = messages[0]

        # Deduplication: ignore the same WhatsApp message if Meta sends it again.
        message_id = msg.get("id")

        if is_duplicate_message(message_id) or is_duplicate_message_in_db(db, message_id):
            log(f"duplicate message ignored | message_id={short_text(message_id, 80)}")
            return {
                "status": "ignored",
                "reason": "duplicate_message",
                "message_id": message_id,
            }

        from_number = msg.get("from")
        message_type = msg.get("type")

        if not from_number:
            log("ignored message with missing sender number")
            return {
                "status": "ignored",
                "reason": "missing_from_number",
            }

        log(
            f"new message | from={from_number} | "
            f"type={message_type} | message_id={short_text(message_id, 80)}"
        )

        conversation = get_or_create_whatsapp_conversation(from_number, db)

        input_type = "text"
        voice_media_id = None
        transcription_result = None

        if message_type == "audio":
            input_type = "voice"
            audio_obj = msg.get("audio", {}) or {}
            voice_media_id = audio_obj.get("id")

            if not voice_media_id:
                reply = "وصلتني رسالة صوتية، بس ما قدرت أقرأ ملف الصوت. ممكن تبعتها مرة ثانية أو تكتبلي طلبك؟ 😊"
                send_result = await send_whatsapp_message(from_number, reply)

                log("audio message ignored | missing media id")

                return {
                    "status": "voice_ignored",
                    "reason": "missing_media_id",
                    "reply": reply,
                    "whatsapp_send": send_result,
                }

            log(f"voice message received | media_id={short_text(voice_media_id, 80)}")

            transcription_result = await transcribe_whatsapp_audio(voice_media_id)

            if not transcription_result.get("ok"):
                reply = "وصلتني رسالة صوتية، بس ما قدرت أحولها لنص حاليًا. ممكن تكتبلي طلبك برسالة؟ 😊"
                send_result = await send_whatsapp_message(from_number, reply)

                log(
                    "voice transcription failed | "
                    f"error={short_text(transcription_result.get('error'), 500)}"
                )

                return {
                    "status": "voice_transcription_failed",
                    "reason": transcription_result.get("error"),
                    "reply": reply,
                    "whatsapp_send": send_result,
                }

            text = transcription_result.get("text", "").strip()

            if not text:
                reply = "وصلتني رسالة صوتية، بس النص طلع فاضي. ممكن تعيد إرسالها أو تكتبلي طلبك؟ 😊"
                send_result = await send_whatsapp_message(from_number, reply)

                log("voice transcription empty")

                return {
                    "status": "voice_transcription_empty",
                    "reply": reply,
                    "whatsapp_send": send_result,
                }

            log(f"voice transcribed text: {short_text(text)}")

        elif message_type == "text":
            text = msg.get("text", {}).get("body", "").strip()

            if not text:
                log("ignored empty text message")
                return {
                    "status": "ignored",
                    "reason": "empty_text",
                }

            log(f"incoming text: {short_text(text)}")

        else:
            reply = "حاليًا بدعم الرسائل النصية والصوتية فقط."
            send_result = await send_whatsapp_message(from_number, reply)

            log(f"unsupported message ignored | type={message_type}")

            return {
                "status": "unsupported_message_ignored",
                "type": message_type,
                "reply": reply,
                "whatsapp_send": send_result,
            }

        # If a human agent has taken over this conversation, save the message
        # for the dashboard but skip the bot entirely (no auto-reply).
        if not getattr(conversation, "bot_enabled", True):
            result = safe_predict(text)

            assignment = None
            if not conversation.assigned_agent:
                assignment = auto_assign_conversation(
                    db=db,
                    conversation=conversation,
                    reason="bot_already_paused_customer_followup",
                    status="pending_human",
                    disable_bot=True,
                )

            paused_routing_reason = "bot_paused_for_conversation; a human agent is handling this chat"
            if assignment:
                paused_routing_reason += f"; auto_assignment={assignment}"

            saved_message = Message(
                conversation_id=conversation.id,
                customer_id=from_number,
                customer_db_id=conversation.customer_db_id,
                text=text,
                sender_type="customer",
                message_type=input_type,
                external_message_id=message_id,
                whatsapp_media_id=voice_media_id,
                sentiment=result["sentiment"]["label"],
                sentiment_confidence=top_score(result["sentiment"]),
                category=result["category"]["label"],
                category_confidence=top_score(result["category"]),
                urgency=result["urgency"]["label"],
                urgency_confidence=top_score(result["urgency"]),
                routing_action="awaiting_agent",
                routing_reason=paused_routing_reason,
                needs_human=True,
                channel="whatsapp",
            )

            db.add(saved_message)
            db.commit()
            db.refresh(saved_message)

            if input_type == "voice":
                db.add(MessageAttachment(
                    message_id=saved_message.id,
                    type="voice",
                    media_id=voice_media_id,
                    transcript=text,
                ))
                db.commit()

            log(f"bot paused for conversation={conversation.id} | saved message id={saved_message.id}")
            await broadcast_dashboard_event({
                "type": "new_message",
                "channel": "whatsapp",
                "conversation_id": conversation.id,
                "message_id": saved_message.id,
                "sender_type": "customer",
                "routing_action": "awaiting_agent",
            })

            return {
                "status": "received_bot_paused",
                "message_id": saved_message.id,
                "conversation_id": conversation.id,
                "from": from_number,
                "text": text,
            }

        # 1) Run prediction for database logging.
        result = safe_predict(text)

        # 2) Run bot logic with session context per WhatsApp number.
        bot_result = handle_bot_message(
            text,
            session_id=from_number,
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
            f"source=bot_service; "
            f"input_type={input_type}; "
            f"voice_media_id={voice_media_id}; "
            f"action={action}; "
            f"intent={intent}; "
            f"faq_score={faq_score}; "
            f"matched_faq={matched_faq}; "
            f"faq_id={faq_id}; "
            f"needs_human={needs_human}; "
            f"bot_category={category_from_bot}; "
            f"session={session}"
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
                reason=f"whatsapp_action={action}; urgency={urgency_label}; category={category_label}; needs_human={needs_human}",
                status=assignment_status,
                disable_bot=True,
            )
            routing_reason += f"; auto_assignment={assignment}"

        saved_message = Message(
            conversation_id=conversation.id,
            customer_id=from_number,
            customer_db_id=conversation.customer_db_id,
            text=text,
            sender_type="customer",
            message_type=input_type,
            external_message_id=message_id,
            whatsapp_media_id=voice_media_id,

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

            channel="whatsapp",
        )

        db.add(saved_message)
        db.commit()
        db.refresh(saved_message)

        if input_type == "voice":
            db.add(MessageAttachment(
                message_id=saved_message.id,
                type="voice",
                media_id=voice_media_id,
                transcript=text,
            ))
            db.commit()

        log(
            f"saved customer message | id={saved_message.id} | "
            f"conversation={conversation.id}"
        )
        await broadcast_dashboard_event({
            "type": "new_message",
            "channel": "whatsapp",
            "conversation_id": conversation.id,
            "message_id": saved_message.id,
            "sender_type": "customer",
            "routing_action": action,
            "needs_human": bool(needs_human) or must_assign,
        })

        log(
            f"analysis | sentiment={sentiment_label}({sentiment_confidence:.4f}) | "
            f"category={category_label}({category_confidence:.4f}) | "
            f"urgency={urgency_label}({urgency_confidence:.4f})"
        )

        log(
            f"bot decision | action={action} | intent={intent} | "
            f"faq_score={faq_score} | needs_human={needs_human}"
        )

        log(f"reply text: {short_text(reply)}")

        send_result = await send_whatsapp_message(from_number, reply)

        saved_bot_message = save_bot_reply_message(
            db=db,
            conversation_id=conversation.id,
            customer_id=from_number,
            reply=reply,
            bot_result=bot_result,
            incoming_message_id=saved_message.id,
            customer_db_id=conversation.customer_db_id,
        )

        log(f"saved bot message | id={saved_bot_message.id}")
        await broadcast_dashboard_event({
            "type": "new_message",
            "channel": "whatsapp",
            "conversation_id": conversation.id,
            "message_id": saved_bot_message.id,
            "sender_type": "bot",
        })

        return {
            "status": "received",
            "message_id": saved_message.id,
            "bot_message_id": saved_bot_message.id,
            "whatsapp_message_id": message_id,
            "conversation_id": conversation.id,
            "from": from_number,
            "text": text,
            "input_type": input_type,
            "voice_media_id": voice_media_id,
            "transcription": transcription_result,
            "reply": reply,
            "whatsapp_send": send_result,

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

        return {
            "status": "error",
            "detail": str(e),
        }
