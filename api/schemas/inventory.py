import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InventoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    quantity_available: int
    quantity_reserved: int
    low_stock_threshold: int
    updated_at: datetime


class InventoryUpdate(BaseModel):
    quantity_available: int | None = Field(None, ge=0)
    low_stock_threshold: int | None = Field(None, ge=0)


class InventoryAdjust(BaseModel):
    delta: int
    reason: str | None = None


class InventoryMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    delta: int
    movement_type: str
    reason: str | None
    created_at: datetime
