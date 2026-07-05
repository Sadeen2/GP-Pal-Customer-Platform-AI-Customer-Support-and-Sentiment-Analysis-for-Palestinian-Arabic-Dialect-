from pydantic import BaseModel
from fastapi import APIRouter, Request
from app.services.bot_service import handle_bot_message
from app.rate_limit import limiter

router = APIRouter(
    prefix="/bot",
    tags=["Bot"]
)


class BotRequest(BaseModel):
    message: str


@router.post("/reply")
@limiter.limit("20/minute")
def bot_reply(request: Request, payload: BotRequest):
    return handle_bot_message(payload.message)