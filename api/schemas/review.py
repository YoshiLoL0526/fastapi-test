import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    product_id: uuid.UUID
    order_id: uuid.UUID
    rating: int = Field(ge=1, le=5)
    title: str = Field(max_length=200)
    body: str | None = None


class ReviewUpdate(BaseModel):
    rating: int | None = Field(None, ge=1, le=5)
    title: str | None = Field(None, max_length=200)
    body: str | None = None


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    user_id: uuid.UUID
    order_id: uuid.UUID
    rating: int
    title: str
    body: str | None
    helpful_votes: int
    created_at: datetime
    updated_at: datetime
