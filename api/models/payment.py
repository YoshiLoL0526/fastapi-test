import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    gateway_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    order: Mapped["Order"] = relationship(back_populates="payment")  # noqa: F821
