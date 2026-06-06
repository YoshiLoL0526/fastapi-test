import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    addresses: Mapped[list["Address"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    cart: Mapped["Cart | None"] = relationship(back_populates="user", uselist=False)  # noqa: F821
    orders: Mapped[list["Order"]] = relationship(back_populates="user")  # noqa: F821
    reviews: Mapped[list["Review"]] = relationship(back_populates="user")  # noqa: F821


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    line1: Mapped[str] = mapped_column(String, nullable=False)
    line2: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    zip_code: Mapped[str] = mapped_column(String, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped["User"] = relationship(back_populates="addresses")
    orders: Mapped[list["Order"]] = relationship(back_populates="shipping_address")  # noqa: F821
