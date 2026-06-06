import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    tax: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    discount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    shipping_address_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="orders")  # noqa: F821
    shipping_address: Mapped["Address"] = relationship(back_populates="orders")  # noqa: F821
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    payment: Mapped["Payment | None"] = relationship(back_populates="order", uselist=False)  # noqa: F821
    reviews: Mapped[list["Review"]] = relationship(back_populates="order")  # noqa: F821


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    product_name: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="order_items")  # noqa: F821
