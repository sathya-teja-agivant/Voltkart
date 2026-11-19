from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

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

    # --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def _bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    user_id: UUID
    email: str
    full_name: str
    role: str

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --------------------------------------------------------------------------- #
# Admin: products and policies
# --------------------------------------------------------------------------- #
StockStatus = Literal["IN_STOCK", "OUT_OF_STOCK"]


class ProductCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=180)
    brand: str = Field(min_length=1, max_length=80)
    category: str = Field(default="Laptop", max_length=80)
    processor: str = Field(min_length=1, max_length=180)
    ram: int = Field(ge=1, le=256)
    storage: int = Field(ge=16, le=8000)  # GB
    display_size: float = Field(gt=0, le=30)
    battery_life: float = Field(gt=0, le=72)
    weight: float = Field(gt=0, le=20)
    operating_system: str = Field(min_length=1, max_length=100)
    price: float = Field(gt=0, le=10_000_000)
    warranty: str = Field(default="1 year manufacturer warranty", max_length=100)
    stock_status: StockStatus = "IN_STOCK"
    description: str = ""


class ProductUpdate(BaseModel):
    product_name: Optional[str] = Field(default=None, min_length=1, max_length=180)
    brand: Optional[str] = Field(default=None, min_length=1, max_length=80)
    category: Optional[str] = Field(default=None, max_length=80)
    processor: Optional[str] = Field(default=None, min_length=1, max_length=180)
    ram: Optional[int] = Field(default=None, ge=1, le=256)
    storage: Optional[int] = Field(default=None, ge=16, le=8000)
    display_size: Optional[float] = Field(default=None, gt=0, le=30)
    battery_life: Optional[float] = Field(default=None, gt=0, le=72)
    weight: Optional[float] = Field(default=None, gt=0, le=20)
    operating_system: Optional[str] = Field(default=None, min_length=1, max_length=100)
    price: Optional[float] = Field(default=None, gt=0, le=10_000_000)
    warranty: Optional[str] = Field(default=None, max_length=100)
    stock_status: Optional[StockStatus] = None
    description: Optional[str] = None


class PolicyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    category: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=20000)


class PolicyUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=180)
    category: Optional[str] = Field(default=None, min_length=1, max_length=80)
    content: Optional[str] = Field(default=None, min_length=1, max_length=20000)
    is_active: Optional[bool] = None


class PolicyOut(BaseModel):
    policy_id: UUID
    title: str
    category: str
    content: str
    is_active: bool

    model_config = {"from_attributes": True}