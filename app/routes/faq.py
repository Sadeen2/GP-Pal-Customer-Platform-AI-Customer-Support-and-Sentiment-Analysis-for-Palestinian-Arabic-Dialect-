import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database.models import FAQItem
from app.services.faq_service import find_best_faq, clear_faq_cache
from app.services.bot_service import handle_bot_message


router = APIRouter(prefix="/api/faqs", tags=["FAQ Management"])

BASE_DIR = Path(__file__).resolve().parents[2]
FAQ_PATH = BASE_DIR / "app" / "data" / "faqs.json"


class FAQCreate(BaseModel):
    id: str = Field(..., example="delivery_general_002")
    category: str = Field(..., example="delivery")
    intent: str = Field(..., example="ask_delivery_general")
    question: str = Field(..., example="في توصيل؟")
    examples: List[str] = Field(default_factory=list)
    answer: str = Field(..., example="نعم، التوصيل متوفر حسب المنطقة.")
    keywords: str = ""
    action: str = Field(default="auto_reply", example="auto_reply")
    needs_human: bool = False
    priority: int = 50
    is_active: bool = True


class FAQUpdate(BaseModel):
    category: Optional[str] = None
    intent: Optional[str] = None
    question: Optional[str] = None
    examples: Optional[List[str]] = None
    answer: Optional[str] = None
    keywords: Optional[str] = None
    action: Optional[str] = None
    needs_human: Optional[bool] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class FAQMatchRequest(BaseModel):
    message: str


class BotReplyRequest(BaseModel):
    message: str
    session_id: str = "api_test_user"


def faq_to_dict(faq: FAQItem) -> Dict[str, Any]:
    return {
        "id": faq.id,
        "category": faq.category,
        "intent": faq.intent,
        "question": faq.question,
        "examples": faq.examples or [],
        "answer": faq.answer,
        "keywords": faq.keywords or "",
        "action": faq.action or "auto_reply",
        "needs_human": bool(faq.needs_human),
        "priority": faq.priority if faq.priority is not None else 50,
        "is_active": bool(faq.is_active),
        "created_at": faq.created_at,
        "updated_at": faq.updated_at,
    }


def read_faq_json() -> List[Dict[str, Any]]:
    if not FAQ_PATH.exists():
        return []

    with open(FAQ_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        data = data.get("faqs", [])

    if not isinstance(data, list):
        raise HTTPException(status_code=500, detail="Invalid faqs.json format")

    return [item for item in data if isinstance(item, dict)]


# ----------------------------
# Static routes first
# ----------------------------

@router.get("/system/health")
def faq_health(db: Session = Depends(get_db)):
    count = db.query(FAQItem).count()
    active_count = db.query(FAQItem).filter(FAQItem.is_active == True).count()

    return {
        "status": "ok",
        "mode": "postgresql_crud_semantic_matching",
        "table": "faq_items",
        "json_fallback": str(FAQ_PATH),
        "count": count,
        "active_count": active_count,
    }


@router.post("/match/test")
def test_faq_match(payload: FAQMatchRequest):
    """Test only FAQ semantic matching from the database-backed FAQ engine."""

    message = payload.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    faq = find_best_faq(message)

    return {
        "message": message,
        "matched": faq is not None,
        "faq": faq,
    }


@router.post("/reply/test")
def test_bot_reply(payload: BotReplyRequest):
    """Test full bot flow: sentiment + session + semantic FAQ + reply."""

    message = payload.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    result = handle_bot_message(
        message=message,
        session_id=payload.session_id,
    )

    return {
        "message": message,
        "session_id": payload.session_id,
        "result": result,
    }


@router.post("/import-json")
def import_faqs_json(
    overwrite_existing: bool = True,
    db: Session = Depends(get_db),
):
    """
    Import app/data/faqs.json into the PostgreSQL faq_items table.
    Use this once after connecting the database, or anytime you update the JSON manually.
    """

    faqs = read_faq_json()
    created = 0
    updated = 0
    skipped = 0

    for item in faqs:
        faq_id = item.get("id")
        if not faq_id:
            skipped += 1
            continue

        existing = db.query(FAQItem).filter(FAQItem.id == str(faq_id)).first()

        if existing and not overwrite_existing:
            skipped += 1
            continue

        if existing:
            faq = existing
            updated += 1
        else:
            faq = FAQItem(id=str(faq_id))
            db.add(faq)
            created += 1

        faq.category = item.get("category")
        faq.intent = item.get("intent")
        faq.question = item.get("question") or ""
        faq.examples = item.get("examples") or []
        faq.answer = item.get("answer") or ""
        faq.keywords = item.get("keywords") or ""
        faq.action = item.get("action") or "auto_reply"
        faq.needs_human = bool(item.get("needs_human", False))
        faq.priority = int(item.get("priority", 50) or 50)
        faq.is_active = bool(item.get("is_active", True))

    db.commit()
    clear_faq_cache()

    return {
        "message": "FAQ JSON imported to database successfully",
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total_in_json": len(faqs),
    }


@router.get("/export-json")
def export_faqs_json(db: Session = Depends(get_db)):
    """Return all FAQ rows in the same JSON shape used by your old file."""

    rows = db.query(FAQItem).order_by(FAQItem.priority.desc(), FAQItem.id.asc()).all()
    return {
        "count": len(rows),
        "items": [faq_to_dict(row) for row in rows],
    }


# ----------------------------
# CRUD APIs
# ----------------------------

@router.get("/")
def list_faqs(
    category: Optional[str] = None,
    intent: Optional[str] = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(FAQItem)

    if category:
        query = query.filter(FAQItem.category == category)

    if intent:
        query = query.filter(FAQItem.intent == intent)

    if active_only:
        query = query.filter(FAQItem.is_active == True)

    faqs = query.order_by(FAQItem.priority.desc(), FAQItem.id.asc()).all()

    return {
        "count": len(faqs),
        "items": [faq_to_dict(faq) for faq in faqs],
    }


@router.post("/")
def create_faq(payload: FAQCreate, db: Session = Depends(get_db)):
    existing = db.query(FAQItem).filter(FAQItem.id == payload.id).first()

    if existing:
        raise HTTPException(status_code=400, detail="FAQ with this id already exists")

    faq = FAQItem(**payload.model_dump())

    db.add(faq)
    db.commit()
    db.refresh(faq)
    clear_faq_cache()

    return {
        "message": "FAQ created successfully",
        "item": faq_to_dict(faq),
    }


@router.get("/{faq_id}")
def get_faq(faq_id: str, db: Session = Depends(get_db)):
    faq = db.query(FAQItem).filter(FAQItem.id == faq_id).first()

    if faq is None:
        raise HTTPException(status_code=404, detail="FAQ not found")

    return faq_to_dict(faq)


@router.put("/{faq_id}")
def update_faq(faq_id: str, payload: FAQUpdate, db: Session = Depends(get_db)):
    faq = db.query(FAQItem).filter(FAQItem.id == faq_id).first()

    if faq is None:
        raise HTTPException(status_code=404, detail="FAQ not found")

    update_data = payload.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(faq, key, value)

    db.commit()
    db.refresh(faq)
    clear_faq_cache()

    return {
        "message": "FAQ updated successfully",
        "item": faq_to_dict(faq),
    }


@router.delete("/{faq_id}")
def delete_faq(faq_id: str, db: Session = Depends(get_db)):
    faq = db.query(FAQItem).filter(FAQItem.id == faq_id).first()

    if faq is None:
        raise HTTPException(status_code=404, detail="FAQ not found")

    deleted_item = faq_to_dict(faq)
    db.delete(faq)
    db.commit()
    clear_faq_cache()

    return {
        "message": "FAQ deleted successfully",
        "deleted": deleted_item,
    }


@router.patch("/{faq_id}/disable")
def disable_faq(faq_id: str, db: Session = Depends(get_db)):
    faq = db.query(FAQItem).filter(FAQItem.id == faq_id).first()

    if faq is None:
        raise HTTPException(status_code=404, detail="FAQ not found")

    faq.is_active = False
    db.commit()
    db.refresh(faq)
    clear_faq_cache()

    return {
        "message": "FAQ disabled successfully",
        "item": faq_to_dict(faq),
    }


@router.patch("/{faq_id}/enable")
def enable_faq(faq_id: str, db: Session = Depends(get_db)):
    faq = db.query(FAQItem).filter(FAQItem.id == faq_id).first()

    if faq is None:
        raise HTTPException(status_code=404, detail="FAQ not found")

    faq.is_active = True
    db.commit()
    db.refresh(faq)
    clear_faq_cache()

    return {
        "message": "FAQ enabled successfully",
        "item": faq_to_dict(faq),
    }
