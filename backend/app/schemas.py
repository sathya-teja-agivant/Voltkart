from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[UUID] = None


class ConversationCreate(BaseModel):
    title: str = "New conversation"


class ProductOut(BaseModel):
    product_id: UUID
    product_name: str
    brand: str
    category: str
    processor: str
    ram: int
    storage: int
    display_size: float
    battery_life: float
    weight: float
    operating_system: str
    price: float
    warranty: str
    stock_status: str
    description: str

    model_config = {"from_attributes": True}
