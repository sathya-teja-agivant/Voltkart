import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import Conversation
from app.schemas import ChatRequest
from app.services.assistant import handle_chat
from app.services.groq_service import GroqService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["AI Assistant"])
groq_service = GroqService()
DEMO_USER = "local-demo-user"


@router.post("/message")
def send_message(payload: ChatRequest, db: Session = Depends(get_db)):
    if payload.conversation_id:
        conversation = db.get(Conversation, payload.conversation_id)
        if not conversation or conversation.user_key != DEMO_USER:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(user_key=DEMO_USER, title=payload.message[:60])
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    try:
        return handle_chat(db, groq_service, conversation, payload.message)
    except Exception:
        db.rollback()
        # Log the real error; never return internals to the browser.
        logger.exception("handle_chat failed")
        raise HTTPException(
            status_code=500,
            detail="Sorry, something went wrong while processing your message. Please try again.",
        )