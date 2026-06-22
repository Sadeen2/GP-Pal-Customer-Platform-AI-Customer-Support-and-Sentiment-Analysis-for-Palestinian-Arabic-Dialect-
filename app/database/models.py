from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)

    # super_admin / manager / agent
    role = Column(String, default="agent")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Customer(Base):
    """
    Real customer profile.
    One customer can have multiple channel identities:
    WhatsApp number, Instagram id, Messenger psid, web id, etc.
    """

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True, index=True)
    email = Column(String, nullable=True, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    channels = relationship("CustomerChannel", back_populates="customer", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="customer")


class CustomerChannel(Base):
    """
    Maps a real customer to the external id used by each platform.
    Example: customer #1 -> whatsapp:97259..., instagram:insta_user_123
    """

    __tablename__ = "customer_channels"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    channel = Column(String, nullable=False, index=True)  # web / whatsapp / instagram / messenger
    external_id = Column(String, nullable=False, index=True)  # phone number, psid, ig scoped id, etc.
    display_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="channels")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)

    # Old field kept for frontend compatibility.
    # For WhatsApp this is usually the phone number.
    customer_id = Column(String, nullable=True, index=True)

    # New normalized customer relation.
    customer_db_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)

    channel = Column(String, default="web", index=True)
    external_conversation_id = Column(String, nullable=True, index=True)
    status = Column(String, default="active", index=True)

    assigned_agent = Column(String, nullable=True, index=True)
    agent_note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class FAQItem(Base):
    """
    FAQ rows used by the web CRUD screen and the bot matching engine.
    The id is a string because your JSON uses ids like slow_reply_001.
    """

    __tablename__ = "faq_items"

    id = Column(String, primary_key=True, index=True)
    category = Column(String, nullable=True, index=True)
    intent = Column(String, nullable=True, index=True)
    question = Column(Text, nullable=False)
    examples = Column(JSON, nullable=True)
    answer = Column(Text, nullable=False)
    keywords = Column(Text, nullable=True)
    action = Column(String, default="auto_reply", index=True)
    needs_human = Column(Boolean, default=False)
    priority = Column(Integer, default=50, index=True)
    is_active = Column(Boolean, default=True, index=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True, index=True)

    # Old field kept for frontend compatibility.
    customer_id = Column(String, nullable=True, index=True)

    # New normalized customer relation.
    customer_db_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)

    text = Column(Text, nullable=False)

    # customer / bot / agent / system
    sender_type = Column(String, default="customer", nullable=False, index=True)

    # web / whatsapp / instagram / messenger
    channel = Column(String, default="web", index=True)

    # text / voice / image / document / unsupported
    message_type = Column(String, default="text", index=True)

    # WhatsApp/Meta message id. Important to avoid duplicate webhook messages.
    external_message_id = Column(String, nullable=True, unique=True, index=True)
    whatsapp_media_id = Column(String, nullable=True)

    sentiment = Column(String, nullable=False, index=True)
    sentiment_confidence = Column(Float, nullable=True)

    category = Column(String, nullable=False, index=True)
    category_confidence = Column(Float, nullable=True)

    urgency = Column(String, nullable=False, index=True)
    urgency_confidence = Column(Float, nullable=True)

    routing_action = Column(String, nullable=True, index=True)
    routing_reason = Column(Text, nullable=True)

    matched_faq_id = Column(String, ForeignKey("faq_items.id"), nullable=True, index=True)
    needs_human = Column(Boolean, default=False)

    corrected_sentiment = Column(String, nullable=True)
    corrected_category = Column(String, nullable=True)
    corrected_urgency = Column(String, nullable=True)
    feedback_note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    conversation = relationship("Conversation", back_populates="messages")
    attachments = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True)

    # voice / image / document / video / sticker
    type = Column(String, nullable=False, index=True)
    media_id = Column(String, nullable=True, index=True)
    file_url = Column(Text, nullable=True)
    mime_type = Column(String, nullable=True)
    filename = Column(String, nullable=True)
    transcript = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    message = relationship("Message", back_populates="attachments")
