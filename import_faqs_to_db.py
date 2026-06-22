"""Import app/data/faqs.json into the faq_items table."""
from app.database.init_db import ensure_database_ready, import_faqs_from_json_if_empty
from app.database.db import SessionLocal
from app.database.models import FAQItem
import json
from pathlib import Path

FAQ_PATH = Path("app/data/faqs.json")


def main(overwrite: bool = True):
    ensure_database_ready(import_json_faqs=False)

    if not FAQ_PATH.exists():
        raise FileNotFoundError(f"FAQ file not found: {FAQ_PATH}")

    data = json.loads(FAQ_PATH.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("faqs", [])

    db = SessionLocal()
    created = updated = skipped = 0

    try:
        for item in data:
            if not isinstance(item, dict) or not item.get("id"):
                skipped += 1
                continue

            faq = db.query(FAQItem).filter(FAQItem.id == str(item["id"])).first()
            if faq and not overwrite:
                skipped += 1
                continue

            if faq:
                updated += 1
            else:
                faq = FAQItem(id=str(item["id"]))
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
        print("FAQ import done ✅")
        print(f"Created: {created}")
        print(f"Updated: {updated}")
        print(f"Skipped: {skipped}")
        print(f"Total in JSON: {len(data)}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main(overwrite=True)
