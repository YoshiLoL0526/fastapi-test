import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    quantity_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    product: Mapped["Product"] = relationship(back_populates="inventory")  # noqa: F821


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped["Product"] = relationship(back_populates="inventory_movements")  # noqa: F821
