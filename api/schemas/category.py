import uuid

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    name: str = Field(max_length=100)
    slug: str = Field(max_length=100)
    description: str | None = None
    parent_id: uuid.UUID | None = None
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    slug: str | None = Field(None, max_length=100)
    description: str | None = None
    parent_id: uuid.UUID | None = None
    is_active: bool | None = None


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    parent_id: uuid.UUID | None
    is_active: bool


class CategoryTree(CategoryRead):
    children: list["CategoryTree"] = []
