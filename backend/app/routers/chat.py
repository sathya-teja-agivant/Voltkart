import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.connection import get_db
from app.models import Conversation, User
from app.schemas import ChatRequest
from app.services.assistant import handle_chat
from app.services.groq_service import GroqService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["AI Assistant"])
groq_service = GroqService()


@router.post("/message")
def send_message(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    owner = str(user.user_id)
    if payload.conversation_id:
        conversation = db.get(Conversation, payload.conversation_id)
        if not conversation or conversation.user_key != owner:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(user_key=owner, title=payload.message[:60])
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    try:
        return handle_chat(db, groq_service, conversation, payload.message)
    except Exception:
        db.rollback()
        logger.exception("handle_chat failed")
        raise HTTPException(
            status_code=500,
            detail="Sorry, something went wrong while processing your message. Please try again.",
        )