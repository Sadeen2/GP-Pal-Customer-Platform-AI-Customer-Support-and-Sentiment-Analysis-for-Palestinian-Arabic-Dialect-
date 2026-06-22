from pydantic import BaseModel
from typing import Dict, Optional


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
    assigned_agent: str


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
