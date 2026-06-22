from pydantic import BaseModel
from fastapi import APIRouter
from app.services.bot_service import handle_bot_message

router = APIRouter(
    prefix="/bot",
    tags=["Bot"]
)


class BotRequest(BaseModel):
    message: str


@router.post("/reply")
def bot_reply(request: BotRequest):
    return handle_bot_message(request.message)