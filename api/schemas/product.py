import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.category import CategoryRead


class ProductCreate(BaseModel):
    name: str = Field(max_length=300)
    slug: str = Field(max_length=300)
    description: str | None = None
    price: Decimal = Field(gt=0, decimal_places=2)
    category_id: uuid.UUID
    image_url: str | None = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: str | None = Field(None, max_length=300)
    slug: str | None = Field(None, max_length=300)
    description: str | None = None
    price: Decimal | None = Field(None, gt=0, decimal_places=2)
    category_id: uuid.UUID | None = None
    image_url: str | None = None
    is_active: bool | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    price: Decimal
    category_id: uuid.UUID
    image_url: str | None
    rating_avg: Decimal
    rating_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductDetail(ProductRead):
    category: CategoryRead
