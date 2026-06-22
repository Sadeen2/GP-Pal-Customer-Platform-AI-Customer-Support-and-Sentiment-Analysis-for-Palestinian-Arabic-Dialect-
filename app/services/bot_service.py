from app.services.faq_service import find_best_faq
from app.services.session_service import (
    get_session,
    set_pending,
    update_session_data,
    clear_session
)

try:
    from app.services.llm_service import generate_faq_reply, generate_general_reply
except Exception:
    generate_faq_reply = None
    generate_general_reply = None

try:
    from app.services.ai_router_service import route_with_openai
except Exception:
    route_with_openai = None

try:
    from app.model.infer import predict
except Exception:
    predict = None


HIGH_FAQ_SCORE = 0.78
MEDIUM_FAQ_SCORE = 0.62
PENDING_OVERRIDE_SCORE = 0.55


ACTION_ALIASES = {
    "escalate": "escalation",
    "handoff_or_contact": "human_handoff",
}


def normalize_action(action: str) -> str:
    if not action:
        return "general_reply"
    return ACTION_ALIASES.get(action, action)

# ----------------------------
# FAQ ID normalization
# ----------------------------

BUILTIN_FAQ_ID_MAP = {
    "greeting_builtin": "greeting_001",
    "small_talk_builtin": "how_are_you_001",
    "acknowledgement_builtin": "ok_understood_001",
    "acknowledgement": "ok_understood_001",

    "service_complaint_builtin": "complaint_general_001",
    "order_cancel_builtin": "order_cancel_001",
    "order_status_builtin": "order_status_001",
    "product_catalog_builtin": "ask_specific_model_001",
    "order_request_builtin": "order_reservation_001",
    "delivery_request_builtin": "delivery_general_001",

    "bot_wrong_reply_builtin": "bot_wrong_reply_001",
    "store_location_builtin": "store_location_001",

    # These are internal routing/context markers, not real FAQ rows in faq_items.
    # So they must NOT be saved as matched_faq_id foreign keys.
    "openai_router": None,
    "cancel_context": None,
    "delivery_location_followup": None,
    "order_details_followup": None,
    "product_info_followup": None,
}


def normalize_faq_id(faq_id):
    """
    Make sure any FAQ id saved in messages.matched_faq_id either:
    1) exists in faq_items, or
    2) becomes None.

    This prevents PostgreSQL ForeignKeyViolation errors such as:
    greeting_builtin / small_talk_builtin not existing in faq_items.
    """
    if not faq_id:
        return None

    faq_id = str(faq_id).strip()

    if faq_id in BUILTIN_FAQ_ID_MAP:
        return BUILTIN_FAQ_ID_MAP[faq_id]

    return faq_id




# ----------------------------
# Basic text helpers
# ----------------------------

def normalize_basic(text: str) -> str:
    if not text:
        return ""

    text = text.strip().lower()

    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ة", "ه")
    text = text.replace("ى", "ي")
    text = text.replace("ؤ", "و")
    text = text.replace("ئ", "ي")
    text = text.replace("ـ", "")

    return " ".join(text.split())


def is_greeting(message: str) -> bool:
    text = normalize_basic(message)

    greetings = [
        "مرحبا",
        "رحبا",
        "مراحب",
        "مرحبتين",
        "هلا",
        "اهلا",
        "اهلين",
        "السلام عليكم",
        "سلام عليكم",
        "صباح الخير",
        "مسا الخير",
        "مساء الخير",
        "هاي",
        "hi",
        "hii",
        "hiii",
        "hiiii",
        "hiiiii",
        "hello",
        "helloo",
        "hey",
        "heyy",
        "helo"
    ]

    if text in greetings:
        return True

    # English hi with repeated i: hiiiiii
    if text.startswith("h") and len(text) >= 2:
        if text[0] == "h" and set(text[1:]) == {"i"}:
            return True

    return False


def is_how_are_you(message: str) -> bool:
    text = normalize_basic(message)

    patterns = [
        "كيفك",
        "كيفكم",
        "كيف الحال",
        "كيف اموركم",
        "كيف الوضع",
        "شو الاخبار",
        "شو اخباركم",
        "طمني عنكم"
    ]

    return any(p in text for p in patterns)


def is_acknowledgement(message: str) -> bool:
    text = normalize_basic(message)

    acknowledgements = [
        "تمام",
        "اوكي",
        "اوك",
        "ok",
        "okay",
        "ماشي",
        "يسلمو",
        "شكرا",
        "شكرا كتير",
        "يعطيك العافيه",
        "الله يعطيك العافيه",
        "اه تمام",
        "خلص تمام"
    ]

    return text in acknowledgements


def is_cancel_message(message: str) -> bool:
    text = normalize_basic(message)

    cancel_words = [
        "الغاء",
        "الغي",
        "الغى",
        "لغي",
        "cancel",
        "انس",
        "انسى",
        "بلاش",
        "مش هسا"
    ]

    return text in cancel_words or any(word in text for word in cancel_words)


def looks_like_store_location_question(message: str) -> bool:
    text = normalize_basic(message)

    keywords = [
        "وين محلكم",
        "وين مكانكم",
        "وين موقعكم",
        "المحل وين",
        "العنوان وين",
        "وين بلاقيكم",
        "وين مكان المحل",
        "عندكم محل",
        "في محل",
        "وين الاستلام",
        "مكان الاستلام"
    ]

    return any(k in text for k in keywords)


def contains_any(text: str, patterns: list[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def looks_like_order_cancel_request(message: str) -> bool:
    text = normalize_basic(message)

    cancel_patterns = [
        "الغاء الطلب",
        "الغاء طلبي",
        "الغاء الطلبية",
        "الغي الطلب",
        "الغي طلبي",
        "الغي الطلبية",
        "بدي الغي",
        "حاب الغي",
        "كيف الغي",
        "الغيت الطلب",
        "cancel order",
    ]

    order_words = ["طلب", "طلبي", "طلبيتي", "الطلبيه", "الطلبية", "اوردر", "order"]

    has_cancel = contains_any(text, cancel_patterns) or contains_any(text, ["الغي", "الغاء", "cancel"])
    has_order = contains_any(text, order_words)

    return has_cancel and has_order


def looks_like_order_status_question(message: str) -> bool:
    text = normalize_basic(message)

    patterns = [
        "وين طلبي",
        "وين طلبيتي",
        "وين الطلب",
        "وصل طلبي",
        "وصلت طلبيتي",
        "شو صار بالطلب",
        "شو صار بطلبي",
        "حاله الطلب",
        "حالة الطلب",
        "تتبع الطلب",
        "order status",
    ]

    return contains_any(text, patterns)


def looks_like_product_catalog_question(message: str) -> bool:
    text = normalize_basic(message)

    patterns = [
        "شو عندكم",
        "شو عندك",
        "ايش عندكم",
        "ايش عندك",
        "شو بتبيعو",
        "شو بتبيعوا",
        "شو البضاعه",
        "شو البضاعة",
        "عندكم بضائع",
        "عندكم بضاعه",
        "عندكم بضاعة",
        "شو المنتجات",
        "اي منتجات",
        "شو المتوفر",
    ]

    return contains_any(text, patterns)


def looks_like_order_request(message: str) -> bool:
    text = normalize_basic(message)

    order_patterns = [
        "بدي اطلب",
        "بدي اطلب",
        "بدي اشتري",
        "حاب اطلب",
        "حابب اطلب",
        "حاب اشتري",
        "حابب اشتري",
        "اريد اطلب",
        "عايز اطلب",
        "بدي اثبت",
        "بدي اثبت الطلب",
        "بدي اثبت الطلبية",
        "ثبتلي",
        "احجزلي",
        "احجز لي",
        "order",
    ]

    product_words = [
        "ساعه",
        "ساعة",
        "جيشوك",
        "gshock",
        "g shock",
        "g-shock",
        "اساور",
        "اسواره",
        "إسوارة",
        "حلق",
        "حلقه",
        "خاتم",
        "اكسسوار",
        "اكسسوارات",
        "منتج",
        "موديل",
    ]

    has_order_phrase = contains_any(text, order_patterns)
    has_product_word = contains_any(text, product_words)

    # Example: "بدي ساعة جيشوك" does not always contain "اطلب", but it is clearly an order/request.
    soft_request_words = ["بدي", "حاب", "حابب", "عايز", "اريد"]
    has_soft_request = contains_any(text, soft_request_words) and has_product_word

    return has_order_phrase or has_soft_request


def looks_like_delivery_request(message: str) -> bool:
    text = normalize_basic(message)

    patterns = [
        "في توصيل",
        "في توصل",
        "بتوصلوا",
        "بتوصلو",
        "توصيل",
        "بدي توصيل",
        "بدي توصلولي",
        "وصلولي",
        "delivery",
    ]

    return contains_any(text, patterns)


def looks_like_service_complaint(message: str) -> bool:
    """
    Detect service/delivery complaints before the normal delivery request rule.
    Example:
    "ليش الخدمة مش منيحة والتوصيل بطيء" should be complaint/escalation,
    not "في توصيل؟".
    """
    text = normalize_basic(message)

    complaint_patterns = [
        "الخدمه مش منيحه",
        "الخدمة مش منيحة",
        "خدمتكم مش منيحه",
        "خدمتكم مش منيحة",
        "الخدمه سيئه",
        "الخدمة سيئة",
        "الخدمه سيئة",
        "الخدمة سيئه",
        "خدمتكم سيئه",
        "خدمتكم سيئة",
        "التوصيل بطيء",
        "التوصيل بطئ",
        "التوصيل بطيئ",
        "التوصيل بطي",
        "التوصيل سيء",
        "التوصيل سيئ",
        "التوصيل سيئه",
        "التوصيل سيئة",
        "توصيلكم بطيء",
        "توصيلكم بطئ",
        "توصيلكم بطيئ",
        "توصيلكم سيء",
        "توصيلكم سيئ",
        "تاخير",
        "تأخير",
        "تاخرتوا",
        "تأخرتوا",
        "بطيتوا",
        "مش راضي",
        "مش عاجبني",
        "تعاملكم سيء",
        "تعاملكم سيئ",
        "تعاملكم مش منيح",
        "تعاملكم مش منيحه",
        "ليش الخدمه مش منيحه",
        "ليش الخدمة مش منيحة",
        "ليش التوصيل بطيء",
        "ليش التوصيل بطيئ",
        "اسوأ خدمة",
        "اسوء خدمة",
        "خدمة زفت",
        "زفت",
    ]

    return contains_any(text, complaint_patterns)


def is_real_bot_identity_question(message: str) -> bool:
    text = normalize_basic(message)

    patterns = [
        "انت بوت",
        "انتا بوت",
        "انتي بوت",
        "انت روبوت",
        "مساعد الي",
        "مساعد آلي",
        "انت انسان",
        "انتا انسان",
        "مين انت",
        "مين انتي",
        "مين انتو",
        "شو انت",
        "شو انتي",
        "بوت",
        "bot",
        "robot",
    ]

    return contains_any(text, patterns)


def is_real_origin_question(message: str) -> bool:
    text = normalize_basic(message)

    patterns = [
        "من وين",
        "صناعه",
        "صناعة",
        "بلد",
        "منشا",
        "منشأ",
        "اصلي",
        "اصلية",
        "اورجينال",
        "original",
    ]

    return contains_any(text, patterns)


def is_real_phone_call_request(message: str) -> bool:
    text = normalize_basic(message)

    patterns = [
        "تلفون",
        "رقمكم",
        "رقم المحل",
        "بدي اكلم",
        "بدي احكي",
        "اتصل",
        "رن",
        "مكالمة",
        "واتساب",
        "call",
        "phone",
    ]

    return contains_any(text, patterns)


def faq_intent_guard_failed(message: str, intent: str, match_type: str, faq_score: float) -> bool:
    """
    Blocks wrong semantic FAQ matches.
    Example: "بدي الغي الطلبية" must not match "إنت بوت؟" just because the score is 0.48.
    """
    if match_type != "semantic":
        return False

    # Low semantic scores are not reliable for sensitive/general intents.
    if faq_score < 0.60:
        risky_low_score_intents = {
            "ask_bot_identity",
            "ask_phone_call",
            "acknowledgment",
            "acknowledgement",
            "affirmative_yes",
            "negative_no",
            "ask_earrings",
            "care_color_fading",
        }
        if intent in risky_low_score_intents:
            return True

    if intent == "ask_bot_identity" and not is_real_bot_identity_question(message):
        return True

    if intent == "ask_origin" and not is_real_origin_question(message):
        return True

    if intent == "ask_phone_call" and not is_real_phone_call_request(message):
        return True

    return False


def looks_like_bot_wrong_reply(message: str) -> bool:
    text = normalize_basic(message)

    patterns = [
        "ليش هيك بتردوا",
        "ليش بترد هيك",
        "مش هيك قصدي",
        "الرد غلط",
        "ردك غلط",
        "مش فاهم علي",
        "انت مش فاهم",
        "ما فهمت علي",
        "شو هالرد",
        "ليش هيك الرد",
        "مش جواب سؤالي",
        "بتردوا غلط",
        "البوت غبي",
        "مش هيك السؤال",
        "انا بسال عن اشي ثاني",
        "انا بسأل عن اشي ثاني"
    ]

    return any(p in text for p in patterns)


def looks_like_new_question(message: str) -> bool:
    """
    Detects if user is asking a new question while we have pending context.
    If yes, we should NOT consume the message as pending slot.
    """
    text = normalize_basic(message)

    question_keywords = [
        "وين",
        "كم",
        "قديش",
        "اديش",
        "شو",
        "ايش",
        "ليش",
        "كيف",
        "متى",
        "في",
        "عندكم",
        "متوفر",
        "محلكم",
        "مكانكم",
        "موقعكم",
        "السعر",
        "توصيل",
        "بتوصلوا",
        "اصلي",
        "اصلية",
        "اورجينال",
        "الوان",
        "ألوان",
        "ضمان",
        "تبديل",
        "ارجاع",
        "بكم",
        "حقها"
    ]

    return any(word in text for word in question_keywords)


def normalize_location(location: str) -> str:
    text = normalize_basic(location)

    fixes = {
        "عرام الله": "رام الله",
        "رام اللة": "رام الله",
        "رامالله": "رام الله",
        "بر زيت": "بيرزيت",
        "بير زيت": "بيرزيت",
        "الجامعه": "الجامعة",
        "جامعة بير زيت": "جامعة بيرزيت",
        "جامعة برزيت": "جامعة بيرزيت",
        "بزيت": "بيرزيت"
    }

    return fixes.get(text, location.strip())


# ----------------------------
# Sentiment
# ----------------------------

def get_sentiment(message: str, prediction_result: dict | None = None):
    if prediction_result is not None:
        result = prediction_result
    elif predict is None:
        return {
            "label": "neutral",
            "confidence": 0.0,
            "scores": {}
        }
    else:
        try:
            result = predict(message)
        except Exception as e:
            print("Sentiment error:", e)
            return {
                "label": "neutral",
                "confidence": 0.0,
                "scores": {}
            }

    try:

        if isinstance(result, dict) and isinstance(result.get("sentiment"), dict):
            sentiment_obj = result.get("sentiment", {})
            label = sentiment_obj.get("label", "neutral")
            scores = sentiment_obj.get("scores", {})
            confidence = scores.get(label, 0.0)

            return {
                "label": str(label).lower(),
                "confidence": float(confidence),
                "scores": scores
            }

        if isinstance(result, dict):
            label = result.get("label") or result.get("sentiment") or "neutral"
            confidence = result.get("confidence") or result.get("score") or 0.0
            scores = result.get("scores", {})

            return {
                "label": str(label).lower(),
                "confidence": float(confidence),
                "scores": scores
            }

        return {
            "label": str(result).lower(),
            "confidence": 0.0,
            "scores": {}
        }

    except Exception as e:
        print("Sentiment error:", e)
        return {
            "label": "neutral",
            "confidence": 0.0,
            "scores": {}
        }


# ----------------------------
# LLM helpers
# ----------------------------

def rewrite_with_openai(
    message: str,
    faq_question: str,
    faq_answer: str,
    sentiment: str
):
    if not faq_answer:
        return "مش واضح عندي جواب مناسب، ممكن توضحلي أكثر؟ 😊"

    if generate_faq_reply is None:
        return faq_answer

    try:
        return generate_faq_reply(
            user_message=message,
            faq_question=faq_question,
            faq_answer=faq_answer,
            sentiment=sentiment
        )
    except Exception as e:
        print("LLM FAQ rewrite error:", e)
        return faq_answer


def general_reply(message: str, sentiment: str):
    if generate_general_reply is None:
        return "مش واضح عندي طلبك بالضبط، ممكن توضحلي أكثر؟ 😊"

    try:
        return generate_general_reply(message, sentiment)
    except Exception as e:
        print("LLM general reply error:", e)
        return "مش واضح عندي طلبك بالضبط، ممكن توضحلي أكثر؟ 😊"


# ----------------------------
# Response builder
# ----------------------------

def build_response(
    action: str,
    reply: str,
    sentiment: str,
    confidence: float,
    faq_score: float,
    matched_faq,
    intent=None,
    needs_human=False,
    faq_id=None,
    category=None,
    session=None
):
    action = normalize_action(action)

    # IMPORTANT:
    # Only return FAQ ids that exist in faq_items, otherwise return None.
    # This protects WhatsApp/message saving from ForeignKeyViolation.
    faq_id = normalize_faq_id(faq_id)

    # Some code paths use matched_faq as an internal id instead of a question.
    # Normalize only known internal ids; normal FAQ questions stay unchanged.
    if matched_faq in BUILTIN_FAQ_ID_MAP:
        matched_faq = normalize_faq_id(matched_faq)

    return {
        "action": action,
        "reply": reply,
        "sentiment": sentiment,
        "sentiment_confidence": confidence,
        "faq_score": faq_score,
        "matched_faq": matched_faq,
        "intent": intent,
        "needs_human": needs_human,
        "faq_id": faq_id,
        "category": category,
        "session": session
    }


def openai_support_route(
    message: str,
    session_id: str,
    sentiment: str,
    confidence: float,
    faq_score: float = 0.0,
    faq_question: str | None = None,
):
    """
    Controlled OpenAI support layer.

    OpenAI does NOT become the final uncontrolled decision maker.
    It only chooses an allowed intent/action from a fixed list and writes a safe reply.
    The code still validates the result and applies business constraints.
    """
    if route_with_openai is None:
        return None

    try:
        ai = route_with_openai(
            message=message,
            sentiment=sentiment,
            sentiment_confidence=confidence,
            faq_score=faq_score,
            faq_question=faq_question,
        )
    except Exception as e:
        print("OpenAI router error:", e)
        return None

    if not isinstance(ai, dict):
        return None

    allowed_actions = {
        "auto_reply",
        "general_reply",
        "clarify",
        "collect_order_info",
        "human_handoff",
        "escalation",
        "acknowledgement",
    }

    allowed_intents = {
        "greeting",
        "small_talk_how_are_you",
        "product_catalog",
        "gift_recommendation",
        "order_request",
        "ask_price",
        "ask_delivery",
        "ask_order_status",
        "cancel_order",
        "complaint_general",
        "ask_origin",
        "ask_store_location",
        "ask_bot_identity",
        "out_of_scope",
        "thanks",
        "human_agent_request",
        "other",
    }

    action = normalize_action(str(ai.get("action") or "general_reply"))
    intent = str(ai.get("intent") or "other")
    reply = str(ai.get("reply") or "").strip()
    category = str(ai.get("category") or "general")
    needs_human = bool(ai.get("needs_human", False))

    if action not in allowed_actions:
        action = "general_reply"

    if intent not in allowed_intents:
        intent = "other"

    if intent == "out_of_scope":
         clear_session(session_id)

         return build_response(
        action="clarify",
        reply="أنا مخصص لمساعدتك بخصوص المنتجات، الطلبات، الأسعار، التوصيل، أو الشكاوى 😊 كيف بقدر أساعدك بهالموضوع؟",
        sentiment=sentiment,
        confidence=confidence,
        faq_score=faq_score,
        matched_faq="openai_router",
        intent="out_of_scope",
        needs_human=False,
        faq_id="openai_router",
        category="general",
        session=get_session(session_id)
    )    

    if not reply:
        return None

    # Business safety: these intents must not be handled as normal automatic replies.
    forced_handoff_intents = {
        "cancel_order",
        "ask_order_status",
        "complaint_general",
        "human_agent_request",
    }

    if intent in forced_handoff_intents:
        # IMPORTANT:
        # OpenAI/rules must NOT override the sentiment model.
        # If the model says the message is positive, do not convert it into a complaint/escalation.
        if intent == "complaint_general" and sentiment == "positive":
            action = "auto_reply"
            intent = "positive_feedback"
            needs_human = False
            category = "feedback"
        else:
            needs_human = True

            if intent == "complaint_general":
                action = "escalation"
                sentiment = "negative"
                confidence = max(confidence, 0.85)
            else:
                action = "human_handoff"

    # Optional context setup for follow-up messages.
    if intent == "order_request" and not needs_human:
        set_pending(
            session_id=session_id,
            topic="order",
            pending_slot="order_details"
        )

    elif intent == "ask_delivery" and not needs_human:
        set_pending(
            session_id=session_id,
            topic="delivery",
            pending_slot="delivery_location"
        )

    elif intent in ["ask_price", "product_catalog", "gift_recommendation"] and not needs_human:
        set_pending(
            session_id=session_id,
            topic="product",
            pending_slot="product_info"
        )

    else:
        # Avoid keeping old pending contexts after complaints/handoff/unknown general cases.
        if needs_human or intent in ["other", "complaint_general", "cancel_order"]:
            clear_session(session_id)

    return build_response(
        action=action,
        reply=reply,
        sentiment=sentiment,
        confidence=confidence,
        faq_score=faq_score,
        matched_faq="openai_router",
        intent=intent,
        needs_human=needs_human,
        faq_id="openai_router",
        category=category,
        session=get_session(session_id)
    )


# ----------------------------
# Pending context logic
# ----------------------------

def handle_pending_context(
    message: str,
    session_id: str,
    sentiment: str,
    confidence: float
):
    session = get_session(session_id)
    pending_slot = session.get("pending_slot")

    if not pending_slot:
        return None

    clean_message = message.strip()

    if is_cancel_message(clean_message):
        clear_session(session_id)
        return build_response(
            action="cancel_context",
            reply="تمام، ألغيت المتابعة السابقة 😊 كيف بقدر أساعدك؟",
            sentiment=sentiment,
            confidence=confidence,
            faq_score=1.0,
            matched_faq="cancel_context",
            intent="cancel_context",
            needs_human=False,
            faq_id=None,
            category="general",
            session=get_session(session_id)
        )

    if pending_slot == "delivery_location":
        location = normalize_location(clean_message)

        update_session_data(session_id, {
            "delivery_location": location
        })

        clear_session(session_id)

        return build_response(
            action="collect_delivery_location",
            reply=f"تمام، التوصيل لـ {location} 😊 بنأكدلك التكلفة والموعد قبل تثبيت الطلب.",
            sentiment=sentiment,
            confidence=confidence,
            faq_score=1.0,
            matched_faq="delivery_location_followup",
            intent="provide_delivery_location",
            needs_human=False,
            faq_id=None,
            category="delivery",
            session=get_session(session_id)
        )

    if pending_slot == "order_details":
        update_session_data(session_id, {
            "order_details": clean_message
        })

        set_pending(
            session_id=session_id,
            topic="order",
            pending_slot="delivery_location"
        )

        return build_response(
            action="collect_order_info",
            reply="تمام، سجلت تفاصيل الطلب 😊 وين بتحب يكون التوصيل أو الاستلام؟",
            sentiment=sentiment,
            confidence=confidence,
            faq_score=1.0,
            matched_faq="order_details_followup",
            intent="provide_order_details",
            needs_human=False,
            faq_id=None,
            category="orders",
            session=get_session(session_id)
        )

    if pending_slot == "product_info":
        update_session_data(session_id, {
            "product_info": clean_message
        })

        clear_session(session_id)

        return build_response(
            action="collect_product_info",
            reply="تمام 😊 بنراجع المنتج اللي قصدك عليه وبنأكدلك السعر أو التوفر.",
            sentiment=sentiment,
            confidence=confidence,
            faq_score=1.0,
            matched_faq="product_info_followup",
            intent="provide_product_info",
            needs_human=True,
            faq_id=None,
            category="products",
            session=get_session(session_id)
        )

    return None


def set_context_from_intent(
    session_id: str,
    intent: str,
    action: str,
    faq_answer: str
):
    if not intent:
        return

    if intent in [
        "ask_delivery_general",
        "ask_delivery_bzu",
        "ask_delivery_hebron",
        "ask_delivery_inside"
    ]:
        set_pending(
            session_id=session_id,
            topic="delivery",
            pending_slot="delivery_location"
        )

    elif intent in [
        "reserve_order",
        "collect_order_info",
        "order_bracelets"
    ]:
        set_pending(
            session_id=session_id,
            topic="order",
            pending_slot="order_details"
        )

    elif intent in [
        "ask_price_general",
        "ask_price_premium_watch",
        "ask_price_specific_watch_135",
        "availability_general",
        "request_photos"
    ]:
        set_pending(
            session_id=session_id,
            topic="product",
            pending_slot="product_info"
        )


def unsafe_semantic_fallback(
    intent: str,
    match_type: str,
    faq_score: float,
    sentiment: str,
    confidence: float,
    session_id: str
):
    """
    Prevent bad semantic matches for short/general intents.
    Example:
    Hiiii -> should not become affirmative_yes
    ليش هيك بتردوا -> should not become acknowledgement
    """

    unsafe_intents = [
        "acknowledgement",
        "affirmative_yes",
        "negative_no"
    ]

    if intent in unsafe_intents and match_type == "semantic" and faq_score < 0.80:
        return build_response(
            action="general_reply",
            reply="أهلًا وسهلًا 😊 كيف بقدر أساعدك؟",
            sentiment=sentiment,
            confidence=confidence,
            faq_score=faq_score,
            matched_faq=None,
            intent=None,
            needs_human=False,
            session=get_session(session_id)
        )

    return None


# ----------------------------
# Main bot function
# ----------------------------

def handle_bot_message(message: str, session_id: str = "default", prediction_result: dict | None = None):
    if not message or not message.strip():
        return build_response(
            action="general_reply",
            reply="أهلًا وسهلًا 😊 كيف بقدر أساعدك؟",
            sentiment="neutral",
            confidence=0.0,
            faq_score=0.0,
            matched_faq=None,
            session=get_session(session_id)
        )

    # 1) Sentiment analysis
    sentiment_result = get_sentiment(message, prediction_result=prediction_result)
    sentiment = sentiment_result["label"]
    confidence = sentiment_result["confidence"]

    # 2) Built-in business rules before FAQ matching
    # These rules prevent weak semantic FAQ matches from giving irrelevant answers.

    # Critical safety rule: complaints must be handled before delivery/product rules.
    # But do NOT let this rule override a strong positive model prediction.
    # Example: "الموظف كان متعاون وفهم المشكلة مباشرة" should stay positive feedback,
    # not escalation just because it contains the word "مشكلة".
    strong_positive = sentiment == "positive" and confidence >= 0.80
    strong_negative = sentiment == "negative" and confidence >= 0.80
    explicit_complaint = looks_like_service_complaint(message)

    # IMPORTANT:
    # The sentiment model is the source of truth.
    # Complaint rules are allowed to help only when the model did NOT classify the message as positive.
    if sentiment != "positive" and (explicit_complaint or strong_negative):
        clear_session(session_id)

        return build_response(
            action="escalation",
            reply=(
                "آسفين جدًا على التجربة السيئة 🙏 "
                "رح نحولك لموظف يتابع معك المشكلة مباشرة ويحاول يحلها بأسرع وقت."
            ),
            sentiment="negative",
            confidence=max(confidence, 0.85),
            faq_score=1.0,
            matched_faq="service_complaint_builtin",
            intent="complaint_general",
            needs_human=True,
            faq_id="service_complaint_builtin",
            category="support",
            session=get_session(session_id)
        )

    if looks_like_order_cancel_request(message):
        clear_session(session_id)

        return build_response(
            action="human_handoff",
            reply=(
                "تمام، بنقدر نساعدك بإلغاء الطلبية. "
                "ابعتلنا رقم الطلب أو الاسم/رقم الهاتف اللي تم تثبيت الطلب عليه، "
                "ورح يتابع معك موظف مباشرة."
            ),
            sentiment=sentiment,
            confidence=confidence,
            faq_score=1.0,
            matched_faq="order_cancel_builtin",
            intent="cancel_order",
            needs_human=True,
            faq_id="order_cancel_builtin",
            category="orders",
            session=get_session(session_id)
        )

    if looks_like_order_status_question(message):
        clear_session(session_id)

        return build_response(
            action="human_handoff",
            reply=(
                "أكيد، ابعتلنا رقم الطلب أو الاسم/رقم الهاتف اللي تم تثبيت الطلب عليه، "
                "وبنراجعلك حالة الطلبية بأسرع وقت 😊"
            ),
            sentiment=sentiment,
            confidence=confidence,
            faq_score=1.0,
            matched_faq="order_status_builtin",
            intent="ask_order_status",
            needs_human=True,
            faq_id="order_status_builtin",
            category="orders",
            session=get_session(session_id)
        )

    if looks_like_product_catalog_question(message):
        clear_session(session_id)

        return build_response(
            action="clarify",
            reply=(
                "عندنا ساعات وإكسسوارات وموديلات مختلفة 😊 "
                "احكيلنا شو النوع اللي بتدور عليه أو ابعت صورة/اسم المنتج، "
                "وبنأكدلك السعر والتوفر."
            ),
            sentiment=sentiment,
            confidence=confidence,
            faq_score=1.0,
            matched_faq="product_catalog_builtin",
            intent="product_catalog",
            needs_human=False,
            faq_id="product_catalog_builtin",
            category="products",
            session=get_session(session_id)
        )

    if looks_like_order_request(message):
        set_pending(
            session_id=session_id,
            topic="order",
            pending_slot="order_details"
        )

        return build_response(
            action="collect_order_info",
            reply=(
                "أكيد 😊 ابعتلنا صورة أو موديل المنتج، ومعه اللون والكمية إذا موجودين، "
                "وبنأكدلك السعر والتوفر قبل تثبيت الطلب."
            ),
            sentiment=sentiment,
            confidence=confidence,
            faq_score=1.0,
            matched_faq="order_request_builtin",
            intent="order_request",
            needs_human=False,
            faq_id="order_request_builtin",
            category="orders",
            session=get_session(session_id)
        )

    if looks_like_delivery_request(message):
        set_pending(
            session_id=session_id,
            topic="delivery",
            pending_slot="delivery_location"
        )

        return build_response(
            action="clarify",
            reply="آه في توصيل حسب المنطقة 😊 وين مكانك عشان نأكدلك التكلفة والوقت؟",
            sentiment=sentiment,
            confidence=confidence,
            faq_score=1.0,
            matched_faq="delivery_request_builtin",
            intent="ask_delivery_general",
            needs_human=False,
            faq_id="delivery_request_builtin",
            category="delivery",
            session=get_session(session_id)
        )

    # 3) Built-in greeting
    if is_greeting(message):
        clear_session(session_id)

        return build_response(
            action="auto_reply",
            reply="أهلًا وسهلًا 😊 كيف بقدر أساعدك؟",
            sentiment=sentiment,
            confidence=confidence,
            faq_score=1.0,
            matched_faq="greeting_001",
            intent="greeting",
            needs_human=False,
            faq_id="greeting_001",
            category="general",
            session=get_session(session_id)
        )

    # 3) Built-in small talk
    if is_how_are_you(message):
        clear_session(session_id)

        return build_response(
            action="auto_reply",
            reply="الحمدلله تمام 😊 احكيلنا كيف بنقدر نساعدك؟",
            sentiment=sentiment,
            confidence=confidence,
            faq_score=1.0,
            matched_faq="small_talk_builtin",
            intent="small_talk_how_are_you",
            needs_human=False,
            faq_id="small_talk_builtin",
            category="general",
            session=get_session(session_id)
        )

    # 4) Natural acknowledgement
    if is_acknowledgement(message):
        clear_session(session_id)

        return build_response(
            action="acknowledgement",
            reply="تمام 😊 أي خدمة ثانية؟",
            sentiment=sentiment,
            confidence=confidence,
            faq_score=1.0,
            matched_faq="acknowledgement",
            intent="acknowledgement",
            needs_human=False,
            faq_id="acknowledgement_builtin",
            category="general",
            session=get_session(session_id)
        )

    # 5) User says bot reply was wrong
    if looks_like_bot_wrong_reply(message):
        clear_session(session_id)

        return build_response(
            action="human_handoff",
            reply="آسفين إذا الرد ما كان مناسب 🙏 احكيلنا قصدك بشكل أبسط أو ابعت سؤالك مرة ثانية، وإذا احتاج الموضوع موظف رح نتابع معك مباشرة.",
            sentiment=sentiment,
            confidence=confidence,
            faq_score=1.0,
            matched_faq="bot_wrong_reply_builtin",
            intent="bot_wrong_reply",
            needs_human=True,
            faq_id="bot_wrong_reply_builtin",
            category="support",
            session=get_session(session_id)
        )

    # 6) Built-in store location answer
    if looks_like_store_location_question(message):
        clear_session(session_id)

        return build_response(
            action="auto_reply",
            reply=(
                "حاليًا بنرتب التسليم حسب الاتفاق، خصوصًا داخل جامعة بيرزيت أو حسب المنطقة 😊 "
                "إذا بدك تثبت طلب، ابعتلنا المنتج/الصورة، اللون، الكمية، ومكان الاستلام المناسب."
            ),
            sentiment=sentiment,
            confidence=confidence,
            faq_score=1.0,
            matched_faq="store_location_builtin",
            intent="ask_store_location",
            needs_human=False,
            faq_id="store_location_builtin",
            category="store_info",
            session=get_session(session_id)
        )

    # 7) Check pending context only if message does NOT look like a new question
    session = get_session(session_id)
    has_pending = session.get("pending_slot") is not None

    if has_pending and not looks_like_new_question(message):
        pending_response = handle_pending_context(
            message=message,
            session_id=session_id,
            sentiment=sentiment,
            confidence=confidence
        )

        if pending_response:
            return pending_response

    # If user asked a new question while old context exists, clear old context.
    if has_pending and looks_like_new_question(message):
        clear_session(session_id)

    # 8) FAQ matching from app/data/faqs.json
    faq = find_best_faq(message)

    if not faq:
        ai_response = openai_support_route(
            message=message,
            session_id=session_id,
            sentiment=sentiment,
            confidence=confidence,
            faq_score=0.0,
            faq_question=None
        )

        if ai_response:
            return ai_response

        reply = general_reply(message, sentiment)

        return build_response(
            action="general_reply",
            reply=reply,
            sentiment=sentiment,
            confidence=confidence,
            faq_score=0.0,
            matched_faq=None,
            session=get_session(session_id)
        )

    faq_score = float(faq.get("score", 0.0))
    faq_question = faq.get("question", "")
    faq_answer = faq.get("answer", "")

    faq_action = faq.get("action", "auto_reply")
    needs_human = bool(faq.get("needs_human", False))
    intent = faq.get("intent")
    faq_id = faq.get("id")
    category = faq.get("category")
    match_type = faq.get("match_type")

    # ------------------------------------------------------------
    # Model-first protection:
    # If the model says Positive, FAQ/rules must not turn the message into
    # complaint_general/escalation just because words like "مشكلة" appear.
    # Example: "شكراً الكم، المشكلة انحلت بسرعة".
    # ------------------------------------------------------------
    complaint_faq_ids = {"service_complaint_builtin", "complaint_general_001"}
    complaint_intents = {"complaint_general"}
    complaint_actions = {"escalate", "escalation"}

    faq_looks_like_complaint = (
        faq_id in complaint_faq_ids
        or intent in complaint_intents
        or faq_action in complaint_actions
    )

    if sentiment == "positive" and faq_looks_like_complaint:
        clear_session(session_id)

        return build_response(
            action="auto_reply",
            reply="العفو 🙏 سعيدين إن المشكلة انحلت بسرعة. إذا احتجت أي مساعدة ثانية إحنا جاهزين.",
            sentiment=sentiment,
            confidence=confidence,
            faq_score=0.0,
            matched_faq=None,
            intent="positive_feedback",
            needs_human=False,
            faq_id=None,
            category="feedback",
            session=get_session(session_id)
        )

    if faq_intent_guard_failed(
        message=message,
        intent=intent,
        match_type=match_type,
        faq_score=faq_score
    ):
        ai_response = openai_support_route(
            message=message,
            session_id=session_id,
            sentiment=sentiment,
            confidence=confidence,
            faq_score=faq_score,
            faq_question=faq_question
        )

        if ai_response:
            return ai_response

        reply = general_reply(message, sentiment)

        return build_response(
            action="general_reply",
            reply=reply,
            sentiment=sentiment,
            confidence=confidence,
            faq_score=faq_score,
            matched_faq=None,
            intent=None,
            needs_human=False,
            faq_id=None,
            category=None,
            session=get_session(session_id)
        )

    fallback_response = unsafe_semantic_fallback(
        intent=intent,
        match_type=match_type,
        faq_score=faq_score,
        sentiment=sentiment,
        confidence=confidence,
        session_id=session_id
    )

    if fallback_response:
        return fallback_response

    # 9) Strong negative sentiment
    if sentiment == "negative" and confidence >= 0.80:
        reply = rewrite_with_openai(
            message=message,
            faq_question=faq_question,
            faq_answer=faq_answer,
            sentiment=sentiment
        )

        clear_session(session_id)

        return build_response(
            action="escalate",
            reply=reply + "\n\nرح نحولك لموظف يتابع معك بأسرع وقت.",
            sentiment=sentiment,
            confidence=confidence,
            faq_score=faq_score,
            matched_faq=faq_question,
            intent=intent,
            needs_human=True,
            faq_id=faq_id,
            category=category,
            session=get_session(session_id)
        )

    # 10) Strong FAQ match
    if faq_score >= HIGH_FAQ_SCORE:
        reply = rewrite_with_openai(
            message=message,
            faq_question=faq_question,
            faq_answer=faq_answer,
            sentiment=sentiment
        )

        final_reply = reply

        if faq_action in ["human_handoff", "handoff_or_contact"] or needs_human:
            final_reply = reply + "\n\nرح يتابع معك موظف إذا احتجنا تفاصيل أكثر."

        if faq_action == "escalate":
            final_reply = reply + "\n\nرح نحولك لموظف يتابع معك بأسرع وقت."

        set_context_from_intent(
            session_id=session_id,
            intent=intent,
            action=faq_action,
            faq_answer=faq_answer
        )

        return build_response(
            action=faq_action,
            reply=final_reply,
            sentiment=sentiment,
            confidence=confidence,
            faq_score=faq_score,
            matched_faq=faq_question,
            intent=intent,
            needs_human=needs_human,
            faq_id=faq_id,
            category=category,
            session=get_session(session_id)
        )

    # 11) Medium FAQ match
    if faq_score >= MEDIUM_FAQ_SCORE:
        # Medium semantic matches are useful, but not reliable enough to be the only decision.
        # Ask OpenAI router to classify the intent from a fixed allowed list.
        ai_response = openai_support_route(
            message=message,
            session_id=session_id,
            sentiment=sentiment,
            confidence=confidence,
            faq_score=faq_score,
            faq_question=faq_question
        )

        if ai_response:
            return ai_response

        reply = rewrite_with_openai(
            message=message,
            faq_question=faq_question,
            faq_answer=faq_answer,
            sentiment=sentiment
        )

        set_context_from_intent(
            session_id=session_id,
            intent=intent,
            action="clarify",
            faq_answer=faq_answer
        )

        return build_response(
            action="clarify",
            reply=reply + "\n\nإذا قصدك إشي ثاني، وضّحلي أكثر.",
            sentiment=sentiment,
            confidence=confidence,
            faq_score=faq_score,
            matched_faq=faq_question,
            intent=intent,
            needs_human=needs_human,
            faq_id=faq_id,
            category=category,
            session=get_session(session_id)
        )

    # 12) Weak FAQ match
    reply = general_reply(message, sentiment)

    return build_response(
        action="general_reply",
        reply=reply,
        sentiment=sentiment,
        confidence=confidence,
        faq_score=faq_score,
        matched_faq=None,
        intent=None,
        needs_human=False,
        session=get_session(session_id)
    )