import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.order import Order, OrderItem
from api.models.review import Review
from api.schemas.common import PaginatedResponse
from api.schemas.review import ReviewCreate, ReviewRead, ReviewUpdate


async def _assert_verified_purchase(
    db: AsyncSession, user_id: uuid.UUID, product_id: uuid.UUID, order_id: uuid.UUID
) -> None:
    result = await db.execute(
        select(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(
            Order.id == order_id,
            Order.user_id == user_id,
            Order.status.in_(["delivered", "completed"]),
            OrderItem.product_id == product_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only review products from your delivered orders",
        )


async def create_review(db: AsyncSession, user_id: uuid.UUID, data: ReviewCreate) -> ReviewRead:
    await _assert_verified_purchase(db, user_id, data.product_id, data.order_id)

    existing = (await db.execute(
        select(Review).where(Review.product_id == data.product_id, Review.user_id == user_id)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already reviewed this product")

    review = Review(
        product_id=data.product_id,
        user_id=user_id,
        order_id=data.order_id,
        rating=data.rating,
        title=data.title,
        body=data.body,
    )
    db.add(review)
    await db.flush()
    return ReviewRead.model_validate(review)


async def get_reviews(
    db: AsyncSession,
    product_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "created_at",
) -> PaginatedResponse[ReviewRead]:
    stmt = select(Review).where(Review.product_id == product_id)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    sort_col = getattr(Review, sort_by, Review.created_at)
    result = await db.execute(
        stmt.order_by(sort_col.desc()).offset((page - 1) * page_size).limit(page_size)
    )

    return PaginatedResponse(
        items=[ReviewRead.model_validate(r) for r in result.scalars().all()],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


async def update_review(
    db: AsyncSession, review_id: uuid.UUID, user_id: uuid.UUID, data: ReviewUpdate
) -> ReviewRead:
    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    if review.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(review, field, value)

    await db.flush()
    return ReviewRead.model_validate(review)


async def delete_review(
    db: AsyncSession, review_id: uuid.UUID, user_id: uuid.UUID, is_admin: bool = False
) -> None:
    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    if not is_admin and review.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    await db.delete(review)


async def vote_helpful(db: AsyncSession, review_id: uuid.UUID) -> ReviewRead:
    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    review.helpful_votes += 1
    await db.flush()
    return ReviewRead.model_validate(review)
