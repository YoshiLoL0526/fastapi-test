import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8)
    full_name: str = Field(max_length=200)
    phone: str | None = Field(None, max_length=20)


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=20)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    full_name: str
    phone: str | None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AddressCreate(BaseModel):
    line1: str
    line2: str | None = None
    city: str
    state: str
    country: str = Field(min_length=2, max_length=2)
    zip_code: str
    is_default: bool = False


class AddressUpdate(BaseModel):
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = Field(None, min_length=2, max_length=2)
    zip_code: str | None = None
    is_default: bool | None = None


class AddressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    line1: str
    line2: str | None
    city: str
    state: str
    country: str
    zip_code: str
    is_default: bool


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str
