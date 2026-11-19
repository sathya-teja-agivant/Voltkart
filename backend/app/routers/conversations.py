from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.connection import get_db
from app.models import Conversation, Message, User
from app.schemas import ConversationCreate

router = APIRouter(prefix="/conversations", tags=["Conversations"])


def _owned(db: Session, conversation_id: UUID, user: User) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.user_key != str(user.user_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post("")
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = Conversation(user_key=str(user.user_id), title=payload.title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return {"conversation_id": str(conversation.conversation_id), "title": conversation.title}


@router.get("")
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(
        select(Conversation)
        .where(Conversation.user_key == str(user.user_id))
        .order_by(Conversation.last_message_at.desc())
    ).all()
    return [{"conversation_id": str(c.conversation_id), "title": c.title, "last_message_at": c.last_message_at} for c in rows]


@router.get("/{conversation_id}/messages")
def get_messages(conversation_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _owned(db, conversation_id, user)
    rows = db.scalars(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    ).all()
    return [
        {
            "message_id": str(m.message_id),
            "sender_type": m.sender_type,
            "message_type": m.message_type,
            "message_content": m.message_content,
            "payload": m.payload,
            "created_at": m.created_at,
        }
        for m in rows
    ]


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    conversation = _owned(db, conversation_id, user)
    db.delete(conversation)
    db.commit()
    return {"deleted": True}