from pydantic import BaseModel
from typing import Dict, Optional, List
from datetime import datetime


class MessageRequest(BaseModel):
    text: str
    customer_id: Optional[str] = None
    conversation_id: Optional[int] = None
    channel: Optional[str] = "web"
    message_type: Optional[str] = "text"


class PredictionItem(BaseModel):
    label: str
    scores: Dict[str, float]


class RoutingDecision(BaseModel):
    action: str
    reason: str


class PredictionResponse(BaseModel):
    sentiment: PredictionItem
    category: PredictionItem
    urgency: PredictionItem
    routing: Optional[RoutingDecision] = None


class ConversationStatusUpdate(BaseModel):
    status: str


class MessageFeedbackUpdate(BaseModel):
    corrected_sentiment: Optional[str] = None
    corrected_category: Optional[str] = None
    corrected_urgency: Optional[str] = None
    feedback_note: Optional[str] = None


class ConversationNoteUpdate(BaseModel):
    note: str


class ConversationAssignUpdate(BaseModel):
    assigned_agent: Optional[str] = None


class ConversationReplyRequest(BaseModel):
    text: str


class ConversationBotToggleUpdate(BaseModel):
    enabled: bool


class UserRegister(BaseModel):
    name: str
    email: str
    password: str
    role: str = "agent"


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    is_available: Optional[bool] = True
    max_active_conversations: Optional[int] = 5
    last_seen_at: Optional[datetime] = None
    last_assigned_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_available: Optional[bool] = None
    max_active_conversations: Optional[int] = None


class AgentAvailabilityUpdate(BaseModel):
    is_available: bool


class UserPasswordChange(BaseModel):
    new_password: str



class AdminRegister(BaseModel):
    name: str
    email: str
    password: str
    phone: Optional[str] = None
    # Use super_admin for full access, manager for limited admin access.
    role: str = "super_admin"


class AdminLogin(BaseModel):
    email: str
    password: str


class AdminResponse(BaseModel):
    id: int
    user_id: int
    name: str
    email: str
    phone: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
