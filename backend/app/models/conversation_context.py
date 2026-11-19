import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class ConversationContext(Base):
    __tablename__ = "conversation_context"

    context_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.conversation_id", ondelete="CASCADE"), unique=True, nullable=False)
    active_constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    previous_recommendations: Mapped[list] = mapped_column(JSON, default=list)
    previous_comparisons: Mapped[list] = mapped_column(JSON, default=list)
    recent_searches: Mapped[list] = mapped_column(JSON, default=list)
    preference_signals: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    conversation = relationship("Conversation", back_populates="context")
