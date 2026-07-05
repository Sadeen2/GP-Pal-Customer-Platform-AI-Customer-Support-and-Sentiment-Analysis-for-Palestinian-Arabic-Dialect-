"""Shared urgency normalization rules used by all message channels.

The ML model normally returns three backend labels:
    normal -> Low in the UI
    urgent -> Medium in the UI
    critical -> High in the UI

This module keeps WhatsApp, Instagram, and web/manual prediction consistent.
"""

from __future__ import annotations

from typing import Any


def _label(result: dict[str, Any], section: str, default: str = "") -> str:
    try:
        return str(result.get(section, {}).get("label", default) or default).strip().lower()
    except Exception:
        return default


def _ensure_urgency_dict(result: dict[str, Any]) -> dict[str, Any]:
    urgency = result.setdefault("urgency", {})
    if not isinstance(urgency, dict):
        urgency = {"label": "normal", "scores": {"normal": 0.0}}
        result["urgency"] = urgency
    urgency.setdefault("scores", {})
    if not isinstance(urgency["scores"], dict):
        urgency["scores"] = {}
    return urgency


def _set_urgency(result: dict[str, Any], label: str, confidence: float) -> dict[str, Any]:
    urgency = _ensure_urgency_dict(result)
    urgency["label"] = label
    urgency["scores"][label] = max(float(urgency["scores"].get(label, 0.0) or 0.0), confidence)
    return result


def apply_critical_urgency_rule(text: str, result: dict[str, Any]) -> dict[str, Any]:
    """Promote obvious urgent/critical customer-service messages.

    The trained model can be conservative and keep severe complaints as normal/urgent.
    Without this post-processing, the dashboard's High bucket barely moves. These rules
    only promote clear cases and preserve the model output for normal messages.
    """
    if not isinstance(result, dict):
        return result

    msg = (text or "").strip().lower()
    sentiment = _label(result, "sentiment")
    category = _label(result, "category")
    current = _label(result, "urgency", "normal")

    # Preserve already-critical outputs, including older models that emit "high".
    if current in {"critical", "high"}:
        return _set_urgency(result, "critical", 0.95)

    negative_context = sentiment in {"negative", "neg"} or category in {
        "complaint",
        "problem",
        "issue",
        "refund",
        "cancel",
        "cancellation",
    }

    critical_always = [
        "شكوى", "اشتك", "بشتكي", "اشكي", "نصب", "احتيال", "سرقة", "خطر",
        "كارثة", "مصيبة", "المدير", "مدير", "مسؤول", "إدارة", "ادارة",
        "بلاغ", "بلغ", "emergency", "complaint", "manager", "fraud", "scam",
        "danger", "terrible", "worst",
    ]

    critical_when_negative = [
        "فورا", "فوراً", "حالاً", "حالا", "هسا", "الان", "الآن", "عاجل",
        "مستعجل", "ضروري", "سيء جدا", "سيئة جدا", "أسوأ", "اسوأ",
        "ما بقبل", "مش مقبول", "مش معقول", "بدي الغي", "ألغي", "الغاء", "إلغاء",
        "cancel", "urgent", "immediately", "right now", "asap",
    ]

    urgent_markers = [
        "وين الطلب", "ما وصل", "ما اجا", "تأخير", "تاخير", "متأخر", "متاخر",
        "مشكلة", "خربان", "غلط", "بسرعة", "ضروري", "عاجل", "مستعجل",
        "late", "delayed", "problem", "issue", "wrong", "quick", "asap",
    ]

    has_critical_always = any(term in msg for term in critical_always)
    has_critical_negative = negative_context and any(term in msg for term in critical_when_negative)
    has_urgent_marker = any(term in msg for term in urgent_markers)

    if has_critical_always or has_critical_negative:
        return _set_urgency(result, "critical", 0.95)

    # Upgrade clearly time-sensitive non-critical cases to Medium/urgent.
    if current in {"normal", "low", ""} and has_urgent_marker:
        return _set_urgency(result, "urgent", 0.90)

    return result
