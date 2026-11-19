import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Numeric, Text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    brand: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(80), default="Laptop")
    processor: Mapped[str] = mapped_column(String(180), nullable=False)
    ram: Mapped[int] = mapped_column(Integer, nullable=False)
    storage: Mapped[int] = mapped_column(Integer, nullable=False)  # GB
    display_size: Mapped[float] = mapped_column(Float, nullable=False)
    battery_life: Mapped[float] = mapped_column(Float, nullable=False)  # hours
    weight: Mapped[float] = mapped_column(Float, nullable=False)  # kg
    operating_system: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    warranty: Mapped[str] = mapped_column(String(100), default="1 year")
    image_url: Mapped[str] = mapped_column(String(255), nullable=True, default=None)
    stock_status: Mapped[str] = mapped_column(String(30), default="IN_STOCK", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
