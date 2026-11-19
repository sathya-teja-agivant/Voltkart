import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True, default="local-demo-user")
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    context = relationship("ConversationContext", back_populates="conversation", uselist=False, cascade="all, delete-orphan")
