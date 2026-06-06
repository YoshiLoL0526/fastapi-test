import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CartItemAdd(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1)


class CartItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cart_id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    unit_price: Decimal


class CartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    coupon_code: str | None
    discount_pct: Decimal
    updated_at: datetime
    items: list[CartItemRead] = []


class CouponApply(BaseModel):
    code: str = Field(max_length=50)


class CouponCreate(BaseModel):
    code: str = Field(max_length=50)
    discount_pct: Decimal = Field(gt=0, le=100, decimal_places=2)
    max_uses: int | None = Field(None, ge=1)
    expires_at: datetime | None = None
    is_active: bool = True


class CouponRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    discount_pct: Decimal
    max_uses: int | None
    uses_count: int
    expires_at: datetime | None
    is_active: bool
