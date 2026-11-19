from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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


Intent = Literal[
    "product_recommendation",
    "product_comparison",
    "product_info",
    "policy_query",
    "greetings",
    "out_of_scope",
    "clarify",
    "other",
]
Operator = Literal["eq", "gte", "lte"]


class IntentResult(BaseModel):
    """Validated output of the 'Understand' step.

    The LLM must return JSON in this shape. Anything that does not validate is
    discarded and the rule-based parser is used instead.
    """

    model_config = {"extra": "ignore"}

    intent: Intent = "other"
    is_follow_up: bool = False
    budget_min: Optional[int] = Field(default=None, ge=0)
    budget_max: Optional[int] = Field(default=None, ge=0)
    ram_gb: Optional[int] = Field(default=None, ge=1, le=256)
    ram_operator: Operator = "eq"
    storage_gb: Optional[int] = Field(default=None, ge=16, le=8000)
    storage_operator: Operator = "eq"
    brand: Optional[str] = None
    processor: Optional[str] = None
    usage: Optional[str] = None
    needs: list[str] = Field(default_factory=list)
    sort_by: Optional[Literal["price", "weight", "battery"]] = None
    refine: Optional[Literal["lighter", "cheaper", "longer_battery"]] = None
    product_names: list[str] = Field(default_factory=list)
    clarifying_question: Optional[str] = None
    # Filled by the rule-based parser only.
    result_limit: Optional[int] = None
    unsupported_attributes: list[str] = Field(default_factory=list)
    unparsed: list[str] = Field(default_factory=list)

    @field_validator("intent", mode="before")
    @classmethod
    def _unknown_intent_is_other(cls, value):
        allowed = set(Intent.__args__)  # type: ignore[attr-defined]
        return value if value in allowed else "other"

    @field_validator("needs", "product_names", "unsupported_attributes", "unparsed", mode="before")
    @classmethod
    def _none_to_list(cls, value):
        return [] if value is None else value

    @field_validator("ram_operator", "storage_operator", mode="before")
    @classmethod
    def _none_to_eq(cls, value):
        return value if value in ("eq", "gte", "lte") else "eq"

    @field_validator("is_follow_up", mode="before")
    @classmethod
    def _none_to_false(cls, value):
        return bool(value)