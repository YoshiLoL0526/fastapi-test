import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    parent: Mapped["Category | None"] = relationship("Category", remote_side="Category.id", back_populates="children")
    children: Mapped[list["Category"]] = relationship("Category", back_populates="parent")
    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    rating_avg: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.0, index=True)
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    category: Mapped["Category"] = relationship(back_populates="products")
    inventory: Mapped["Inventory | None"] = relationship(back_populates="product", uselist=False)  # noqa: F821
    cart_items: Mapped[list["CartItem"]] = relationship(back_populates="product")  # noqa: F821
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="product")  # noqa: F821
    reviews: Mapped[list["Review"]] = relationship(back_populates="product")  # noqa: F821
    inventory_movements: Mapped[list["InventoryMovement"]] = relationship(back_populates="product")  # noqa: F821
