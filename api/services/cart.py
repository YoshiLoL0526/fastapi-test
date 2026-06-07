import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from api.models.cart import Cart, CartItem, Coupon
from api.models.inventory import Inventory
from api.models.product import Product
from api.schemas.cart import CartItemAdd, CartItemUpdate, CartRead, CouponApply


async def _load_cart(db: AsyncSession, user_id: uuid.UUID) -> Cart | None:
    result = await db.execute(
        select(Cart).options(selectinload(Cart.items)).where(Cart.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def _available_stock(db: AsyncSession, product_id: uuid.UUID) -> int:
    inv = (await db.execute(select(Inventory).where(Inventory.product_id == product_id))).scalar_one_or_none()
    return inv.quantity_available if inv else 0


async def get_or_create_cart(db: AsyncSession, user_id: uuid.UUID) -> CartRead:
    cart = await _load_cart(db, user_id)
    if not cart:
        cart = Cart(user_id=user_id)
        db.add(cart)
        await db.flush()
        set_committed_value(cart, "items", [])
    return CartRead.model_validate(cart)


async def add_item(db: AsyncSession, user_id: uuid.UUID, data: CartItemAdd) -> CartRead:
    product = await db.get(Product, data.product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    cart = await _load_cart(db, user_id)
    if not cart:
        cart = Cart(user_id=user_id)
        db.add(cart)
        await db.flush()
        set_committed_value(cart, "items", [])

    existing_item = next((i for i in cart.items if i.product_id == data.product_id), None)
    total_needed = data.quantity + (existing_item.quantity if existing_item else 0)

    if total_needed > await _available_stock(db, data.product_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Insufficient stock")

    if existing_item:
        existing_item.quantity += data.quantity
        existing_item.unit_price = float(product.price)
    else:
        item = CartItem(
            cart_id=cart.id,
            product_id=data.product_id,
            quantity=data.quantity,
            unit_price=float(product.price),
        )
        db.add(item)
        cart.items.append(item)

    await db.flush()
    return CartRead.model_validate(cart)


async def update_item(db: AsyncSession, user_id: uuid.UUID, item_id: uuid.UUID, data: CartItemUpdate) -> CartRead:
    cart = await _load_cart(db, user_id)
    if not cart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")

    item = next((i for i in cart.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")

    if data.quantity > await _available_stock(db, item.product_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Insufficient stock")

    product = await db.get(Product, item.product_id)
    item.quantity = data.quantity
    if product:
        item.unit_price = float(product.price)

    await db.flush()
    return CartRead.model_validate(cart)


async def remove_item(db: AsyncSession, user_id: uuid.UUID, item_id: uuid.UUID) -> CartRead:
    cart = await _load_cart(db, user_id)
    if not cart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")

    item = next((i for i in cart.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")

    await db.delete(item)
    cart.items.remove(item)
    await db.flush()
    return CartRead.model_validate(cart)


async def clear_cart(db: AsyncSession, user_id: uuid.UUID) -> CartRead:
    cart = await _load_cart(db, user_id)
    if not cart:
        cart = Cart(user_id=user_id)
        db.add(cart)
        await db.flush()
        set_committed_value(cart, "items", [])
        return CartRead.model_validate(cart)

    for item in list(cart.items):
        await db.delete(item)
    cart.items.clear()
    cart.coupon_code = None
    cart.discount_pct = 0.0
    await db.flush()
    return CartRead.model_validate(cart)


async def apply_coupon(db: AsyncSession, user_id: uuid.UUID, data: CouponApply) -> CartRead:
    now = datetime.now(UTC)

    coupon = (await db.execute(
        select(Coupon).where(Coupon.code == data.code, Coupon.is_active.is_(True))
    )).scalar_one_or_none()

    if not coupon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found or inactive")

    expires = coupon.expires_at
    if expires:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < now:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Coupon expired")

    if coupon.max_uses is not None and coupon.uses_count >= coupon.max_uses:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Coupon usage limit reached")

    cart = await _load_cart(db, user_id)
    if not cart:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

    cart.coupon_code = coupon.code
    cart.discount_pct = float(coupon.discount_pct)
    await db.flush()
    return CartRead.model_validate(cart)
