import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PaymentInitiate(BaseModel):
    order_id: uuid.UUID


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    status: str
    amount: Decimal
    gateway_ref: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
