import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("product_id", "user_id", name="uq_review_product_user"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), nullable=False
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    helpful_votes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    product: Mapped["Product"] = relationship(back_populates="reviews")  # noqa: F821
    user: Mapped["User"] = relationship(back_populates="reviews")  # noqa: F821
    order: Mapped["Order"] = relationship(back_populates="reviews")  # noqa: F821
