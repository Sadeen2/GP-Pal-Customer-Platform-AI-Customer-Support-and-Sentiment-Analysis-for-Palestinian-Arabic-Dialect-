"""Customer identity helpers for multi-channel support.

A real customer can talk through WhatsApp, Instagram, Messenger, or the web.
Each platform gives us a different external id, so this service keeps those ids
linked to one internal Customer row whenever we have reliable evidence.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.database.models import Customer, CustomerChannel


_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
# Accepts +97059..., 0097059..., 059..., 97259..., etc.
PHONE_RE = re.compile(r"(?:\+|00)?(?:970|972)?[\s\-()]?0?5[0-9\s\-()]{7,12}")


def _digits(value: str | None) -> str:
    if not value:
        return ""
    value = str(value).translate(_ARABIC_DIGITS)
    return re.sub(r"\D+", "", value)


def phone_candidates(value: str | None) -> set[str]:
    """Return comparable phone variants for Palestinian mobile numbers."""
    digits = _digits(value)
    if not digits:
        return set()

    if digits.startswith("00"):
        digits = digits[2:]

    candidates = {digits}

    # Local mobile: 059xxxxxxx -> 97059xxxxxxx / 97259xxxxxxx.
    if digits.startswith("0") and len(digits) >= 9:
        local_without_zero = digits[1:]
        candidates.add("970" + local_without_zero)
        candidates.add("972" + local_without_zero)

    # International mobile: 97059xxxxxxx or 97259xxxxxxx -> 059xxxxxxx.
    if digits.startswith("970") and len(digits) >= 11:
        rest = digits[3:]
        candidates.add("0" + rest)
        candidates.add("972" + rest)
    if digits.startswith("972") and len(digits) >= 11:
        rest = digits[3:]
        candidates.add("0" + rest)
        candidates.add("970" + rest)

    return {c for c in candidates if len(c) >= 9}


def normalize_phone(value: str | None) -> Optional[str]:
    """Prefer +970-style digits without plus, while still matching 972/local."""
    candidates = phone_candidates(value)
    if not candidates:
        return None
    for candidate in sorted(candidates):
        if candidate.startswith("970"):
            return candidate
    # Fallback to the longest stable representation.
    return sorted(candidates, key=lambda x: (-len(x), x))[0]


def extract_phone(text: str | None) -> Optional[str]:
    if not text:
        return None
    normalized_text = str(text).translate(_ARABIC_DIGITS)
    match = PHONE_RE.search(normalized_text)
    return normalize_phone(match.group(0)) if match else None


def extract_email(text: str | None) -> Optional[str]:
    if not text:
        return None
    match = EMAIL_RE.search(str(text))
    return match.group(0).lower() if match else None


def find_customer_by_phone(db: Session, phone: str | None) -> Customer | None:
    candidates = phone_candidates(phone)
    if not candidates:
        return None

    # Fast exact match first.
    customer = db.query(Customer).filter(Customer.phone.in_(list(candidates))).first()
    if customer:
        return customer

    # Older rows may contain unnormalized phone strings. Compare variants safely.
    for existing in db.query(Customer).filter(Customer.phone.isnot(None)).all():
        if phone_candidates(existing.phone) & candidates:
            return existing

    return None


def find_customer_by_email(db: Session, email: str | None) -> Customer | None:
    if not email:
        return None
    return db.query(Customer).filter(Customer.email == email.lower()).first()


def update_missing_customer_fields(customer: Customer, phone: str | None = None, email: str | None = None):
    changed = False
    normalized_phone = normalize_phone(phone)
    normalized_email = email.lower() if email else None

    if normalized_phone and not customer.phone:
        customer.phone = normalized_phone
        changed = True

    if normalized_email and not customer.email:
        customer.email = normalized_email
        changed = True

    if changed:
        customer.updated_at = datetime.utcnow()

    return changed


def get_or_create_customer_channel(
    db: Session,
    channel: str,
    external_id: str,
    display_name: str | None = None,
    evidence_text: str | None = None,
    phone_hint: str | None = None,
    email_hint: str | None = None,
) -> tuple[Customer, CustomerChannel, dict]:
    """
    Resolve one platform identity to an internal Customer.

    Exact same platform identity always maps to the same customer.
    Cross-channel identity is linked only when we have evidence: phone/email in
    the message or an explicit phone/email hint.
    """
    channel = (channel or "web").strip().lower()
    external_id = str(external_id).strip()

    link = (
        db.query(CustomerChannel)
        .filter(CustomerChannel.channel == channel, CustomerChannel.external_id == external_id)
        .first()
    )

    phone = normalize_phone(phone_hint) or extract_phone(evidence_text)
    email = (email_hint.lower() if email_hint else None) or extract_email(evidence_text)

    if link:
        customer = db.query(Customer).filter(Customer.id == link.customer_id).first()
        meta = {"identity_status": "known_channel", "linked_by": "channel_external_id"}

        if display_name and link.display_name != display_name:
            link.display_name = display_name
            link.updated_at = datetime.utcnow()
            db.add(link)

        if customer and update_missing_customer_fields(customer, phone=phone, email=email):
            db.add(customer)

        db.commit()
        if customer:
            db.refresh(customer)
            db.refresh(link)
            return customer, link, meta

    customer = find_customer_by_phone(db, phone) or find_customer_by_email(db, email)

    if customer:
        meta = {
            "identity_status": "linked_existing_customer",
            "linked_by": "phone" if phone else "email",
            "phone_detected": bool(phone),
            "email_detected": bool(email),
        }
        update_missing_customer_fields(customer, phone=phone, email=email)
    else:
        customer = Customer(
            phone=phone if channel == "whatsapp" or phone else None,
            email=email,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        meta = {
            "identity_status": "new_customer",
            "linked_by": "new_channel_identity",
            "phone_detected": bool(phone),
            "email_detected": bool(email),
        }

    link = CustomerChannel(
        customer_id=customer.id,
        channel=channel,
        external_id=external_id,
        display_name=display_name or external_id,
    )
    db.add(customer)
    db.add(link)
    db.commit()
    db.refresh(customer)
    db.refresh(link)

    return customer, link, meta
