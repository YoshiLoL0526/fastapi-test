import uuid

from fastapi import APIRouter, BackgroundTasks

from api.core.dependencies import CurrentUser, DBSession
from api.schemas.common import MessageResponse, PaginatedResponse
from api.schemas.review import ReviewCreate, ReviewRead, ReviewUpdate
from api.services import review as review_service
from api.tasks.background import recalculate_product_rating

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/products/{product_id}", response_model=PaginatedResponse[ReviewRead])
async def list_reviews(
    product_id: uuid.UUID,
    db: DBSession,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "created_at",
):
    return await review_service.get_reviews(db, product_id, page=page, page_size=page_size, sort_by=sort_by)


@router.post("/", response_model=ReviewRead, status_code=201)
async def create_review(data: ReviewCreate, current_user: CurrentUser, db: DBSession, bg: BackgroundTasks):
    review = await review_service.create_review(db, uuid.UUID(current_user["sub"]), data)
    bg.add_task(recalculate_product_rating, db, data.product_id)
    return review


@router.put("/{review_id}", response_model=ReviewRead)
async def update_review(review_id: uuid.UUID, data: ReviewUpdate, current_user: CurrentUser, db: DBSession, bg: BackgroundTasks):
    review = await review_service.update_review(db, review_id, uuid.UUID(current_user["sub"]), data)
    bg.add_task(recalculate_product_rating, db, review.product_id)
    return review


@router.delete("/{review_id}", response_model=MessageResponse)
async def delete_review(review_id: uuid.UUID, current_user: CurrentUser, db: DBSession, bg: BackgroundTasks):
    from api.models.review import Review
    review = await db.get(Review, review_id)
    product_id = review.product_id if review else None
    is_admin = current_user.get("role") == "admin"
    await review_service.delete_review(db, review_id, uuid.UUID(current_user["sub"]), is_admin=is_admin)
    if product_id:
        bg.add_task(recalculate_product_rating, db, product_id)
    return MessageResponse(message="Review deleted")


@router.post("/{review_id}/helpful", response_model=ReviewRead)
async def vote_helpful(review_id: uuid.UUID, db: DBSession):
    return await review_service.vote_helpful(db, review_id)
