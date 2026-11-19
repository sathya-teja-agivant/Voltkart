import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class Message(Base):
    __tablename__ = "messages"

    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False, index=True)
    sender_type: Mapped[str] = mapped_column(String(20), nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), default="TEXT")
    message_content: Mapped[str] = mapped_column(Text, nullable=False)
    # Products / comparison table shown with this message, so reloading a
    # conversation shows the same cards and tables.
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    conversation = relationship("Conversation", back_populates="messages")