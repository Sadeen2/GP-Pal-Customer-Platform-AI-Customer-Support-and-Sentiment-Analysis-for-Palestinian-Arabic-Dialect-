"""
Small database bootstrap for the graduation-project backend.

What it does:
1) creates missing tables using SQLAlchemy models,
2) adds missing columns to older local PostgreSQL/SQLite databases,
3) imports app/data/faqs.json into faq_items if the table is empty.

This keeps your project simple without introducing Alembic migrations yet.
For a production system, Alembic is better.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.database.db import Base, SessionLocal, engine
from app.database import models
from app.database.models import FAQItem


BASE_DIR = Path(__file__).resolve().parents[2]
FAQ_PATH = BASE_DIR / "app" / "data" / "faqs.json"


# Minimal schema repair for existing tables you already created before adding DB support.
# create_all() does not add new columns to existing tables, so these ALTER statements do it safely.
MISSING_COLUMNS: dict[str, dict[str, str]] = {
    "users": {
        "is_available": "BOOLEAN DEFAULT TRUE",
        "max_active_conversations": "INTEGER DEFAULT 5",
        "last_seen_at": "TIMESTAMP",
        "last_assigned_at": "TIMESTAMP",
    },
    "conversations": {
        "customer_db_id": "INTEGER",
        "external_conversation_id": "VARCHAR",
        "updated_at": "TIMESTAMP",
        "bot_enabled": "BOOLEAN DEFAULT TRUE",
    },
    "messages": {
        "customer_db_id": "INTEGER",
        "message_type": "VARCHAR DEFAULT 'text'",
        "external_message_id": "VARCHAR",
        "whatsapp_media_id": "VARCHAR",
        "matched_faq_id": "VARCHAR",
        "needs_human": "BOOLEAN DEFAULT FALSE",
    },
    "faq_items": {
        "created_by": "INTEGER",
        "updated_by": "INTEGER",
    },
    "admins": {
        "phone": "VARCHAR",
        "department": "VARCHAR",
        "permissions": "JSON",
        "is_active": "BOOLEAN DEFAULT TRUE",
        "updated_at": "TIMESTAMP",
    },
}


def _table_columns(table_name: str) -> set[str]:
    inspector = inspect(engine)
    try:
        return {column["name"] for column in inspector.get_columns(table_name)}
    except Exception:
        return set()


def _table_exists(table_name: str) -> bool:
    inspector = inspect(engine)
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def _run_sql(sql: str):
    with engine.begin() as conn:
        conn.execute(text(sql))


def add_missing_columns():
    for table_name, columns in MISSING_COLUMNS.items():
        if not _table_exists(table_name):
            continue

        existing = _table_columns(table_name)

        for column_name, column_type in columns.items():
            if column_name in existing:
                continue

            try:
                _run_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                print(f"[db] added missing column {table_name}.{column_name}")
            except SQLAlchemyError as exc:
                # Keep startup alive, but show exactly what failed.
                print(f"[db] could not add column {table_name}.{column_name}: {exc}")

    # Useful indexes. Keep them separate so failure does not block startup.
    index_statements = [
        "CREATE INDEX IF NOT EXISTS ix_customer_channels_channel_external_id ON customer_channels (channel, external_id)",
        "CREATE INDEX IF NOT EXISTS ix_conversations_customer_channel ON conversations (customer_id, channel)",
        "CREATE INDEX IF NOT EXISTS ix_messages_external_message_id ON messages (external_message_id)",
        "CREATE INDEX IF NOT EXISTS ix_faq_items_active_priority ON faq_items (is_active, priority)",
        "CREATE INDEX IF NOT EXISTS ix_admins_user_id ON admins (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_users_role_available ON users (role, is_active, is_available)",
    ]

    for sql in index_statements:
        try:
            _run_sql(sql)
        except SQLAlchemyError as exc:
            print(f"[db] index skipped: {exc}")

    # Backfill default values for older rows after adding availability columns.
    backfill_statements = [
        "UPDATE users SET is_available = TRUE WHERE is_available IS NULL",
        "UPDATE users SET max_active_conversations = 5 WHERE max_active_conversations IS NULL",
    ]

    for sql in backfill_statements:
        try:
            _run_sql(sql)
        except SQLAlchemyError as exc:
            print(f"[db] backfill skipped: {exc}")


def _load_faqs_json() -> list[dict[str, Any]]:
    if not FAQ_PATH.exists():
        return []

    with open(FAQ_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        data = data.get("faqs", [])

    if not isinstance(data, list):
        return []

    return [item for item in data if isinstance(item, dict)]


def import_faqs_from_json_if_empty() -> dict[str, int]:
    db = SessionLocal()
    created = 0

    try:
        existing_count = db.query(FAQItem).count()
        if existing_count > 0:
            return {"created": 0, "skipped_existing": existing_count}

        for faq in _load_faqs_json():
            faq_id = faq.get("id")
            if not faq_id:
                continue

            db.add(
                FAQItem(
                    id=str(faq_id),
                    category=faq.get("category"),
                    intent=faq.get("intent"),
                    question=faq.get("question") or "",
                    examples=faq.get("examples") or [],
                    answer=faq.get("answer") or "",
                    keywords=faq.get("keywords") or "",
                    action=faq.get("action") or "auto_reply",
                    needs_human=bool(faq.get("needs_human", False)),
                    priority=int(faq.get("priority", 50) or 50),
                    is_active=bool(faq.get("is_active", True)),
                )
            )
            created += 1

        db.commit()
        if created:
            print(f"[db] imported {created} FAQs from {FAQ_PATH}")
        return {"created": created, "skipped_existing": 0}

    except Exception as exc:
        db.rollback()
        print(f"[db] FAQ auto-import failed: {exc}")
        return {"created": 0, "error": 1}

    finally:
        db.close()


def ensure_database_ready(import_json_faqs: bool = True):
    # Import models above registers all tables in Base.metadata.
    Base.metadata.create_all(bind=engine)
    add_missing_columns()

    if import_json_faqs:
        import_faqs_from_json_if_empty()
