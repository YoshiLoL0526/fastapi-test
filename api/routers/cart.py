import uuid

from fastapi import APIRouter

from api.core.dependencies import CurrentUser, DBSession
from api.schemas.cart import CartItemAdd, CartItemUpdate, CartRead, CouponApply
from api.services import cart as cart_service

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("/", response_model=CartRead)
async def get_cart(current_user: CurrentUser, db: DBSession):
    return await cart_service.get_or_create_cart(db, uuid.UUID(current_user["sub"]))


@router.delete("/", response_model=CartRead)
async def clear_cart(current_user: CurrentUser, db: DBSession):
    return await cart_service.clear_cart(db, uuid.UUID(current_user["sub"]))


@router.post("/coupon", response_model=CartRead)
async def apply_coupon(data: CouponApply, current_user: CurrentUser, db: DBSession):
    return await cart_service.apply_coupon(db, uuid.UUID(current_user["sub"]), data)


@router.post("/items", response_model=CartRead, status_code=201)
async def add_item(data: CartItemAdd, current_user: CurrentUser, db: DBSession):
    return await cart_service.add_item(db, uuid.UUID(current_user["sub"]), data)


@router.put("/items/{item_id}", response_model=CartRead)
async def update_item(item_id: uuid.UUID, data: CartItemUpdate, current_user: CurrentUser, db: DBSession):
    return await cart_service.update_item(db, uuid.UUID(current_user["sub"]), item_id, data)


@router.delete("/items/{item_id}", response_model=CartRead)
async def remove_item(item_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    return await cart_service.remove_item(db, uuid.UUID(current_user["sub"]), item_id)
