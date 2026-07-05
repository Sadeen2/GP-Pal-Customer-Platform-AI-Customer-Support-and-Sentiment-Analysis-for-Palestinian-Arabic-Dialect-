"""Quick database check."""
from app.database.init_db import ensure_database_ready
from app.database.db import engine, SessionLocal
from app.database.models import User, Conversation, Message, FAQItem, Customer, CustomerChannel, MessageAttachment

ensure_database_ready(import_json_faqs=True)

db = SessionLocal()
try:
    print("DB URL:", engine.url)
    print("users:", db.query(User).count())
    print("customers:", db.query(Customer).count())
    print("customer_channels:", db.query(CustomerChannel).count())
    print("conversations:", db.query(Conversation).count())
    print("messages:", db.query(Message).count())
    print("faq_items:", db.query(FAQItem).count())
    print("message_attachments:", db.query(MessageAttachment).count())
    print("DB OK ✅")
finally:
    db.close()
