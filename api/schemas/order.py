import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    quantity: int
    unit_price: Decimal


class OrderCreate(BaseModel):
    shipping_address_id: uuid.UUID


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    subtotal: Decimal
    tax: Decimal
    discount: Decimal
    total: Decimal
    shipping_address_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead] = []


class OrderStatusUpdate(BaseModel):
    status: str
