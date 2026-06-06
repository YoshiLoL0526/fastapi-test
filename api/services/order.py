import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.cart import Cart, CartItem
from api.models.inventory import Inventory, InventoryMovement
from api.models.order import Order, OrderItem
from api.models.user import Address
from api.schemas.common import PaginatedResponse
from api.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate

TAX_RATE = 0.08

VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"processing", "cancelled"},
    "processing": {"shipped", "cancelled"},
    "shipped": {"delivered"},
    "delivered": {"refunded"},
    "cancelled": set(),
    "refunded": set(),
}


async def checkout(db: AsyncSession, user_id: uuid.UUID, data: OrderCreate) -> OrderRead:
    addr = await db.get(Address, data.shipping_address_id)
    if not addr or addr.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipping address not found")

    result = await db.execute(
        select(Cart)
        .options(selectinload(Cart.items).selectinload(CartItem.product))
        .where(Cart.user_id == user_id)
    )
    cart = result.scalar_one_or_none()
    if not cart or not cart.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

    # Lock and validate stock for every item before reserving any
    reservations: list[tuple[Inventory, int]] = []
    for item in cart.items:
        inv = (await db.execute(
            select(Inventory).where(Inventory.product_id == item.product_id).with_for_update()
        )).scalar_one_or_none()
        if not inv or inv.quantity_available < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Insufficient stock for: {item.product.name}",
            )
        reservations.append((inv, item.quantity))

    for inv, qty in reservations:
        inv.quantity_available -= qty
        inv.quantity_reserved += qty
        db.add(InventoryMovement(product_id=inv.product_id, delta=-qty, movement_type="reserve", reason="checkout"))

    subtotal = sum(float(item.unit_price) * item.quantity for item in cart.items)
    discount = round(subtotal * float(cart.discount_pct) / 100, 2) if cart.discount_pct else 0.0
    tax = round((subtotal - discount) * TAX_RATE, 2)
    total = round(subtotal - discount + tax, 2)

    order = Order(
        user_id=user_id,
        status="pending",
        subtotal=round(subtotal, 2),
        discount=discount,
        tax=tax,
        total=total,
        shipping_address_id=data.shipping_address_id,
    )
    db.add(order)
    await db.flush()

    for item in cart.items:
        db.add(OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            product_name=item.product.name,
            quantity=item.quantity,
            unit_price=float(item.unit_price),
        ))

    for item in list(cart.items):
        await db.delete(item)
    cart.coupon_code = None
    cart.discount_pct = 0.0
    await db.flush()

    reloaded = (await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order.id)
    )).scalar_one()
    return OrderRead.model_validate(reloaded)


async def get_orders(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
) -> PaginatedResponse[OrderRead]:
    stmt = select(Order).options(selectinload(Order.items))
    if user_id:
        stmt = stmt.where(Order.user_id == user_id)
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    result = await db.execute(stmt.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size))

    return PaginatedResponse(
        items=[OrderRead.model_validate(o) for o in result.scalars().all()],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


async def get_order(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID | None = None) -> OrderRead:
    result = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if user_id and order.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return OrderRead.model_validate(order)


async def update_status(db: AsyncSession, order_id: uuid.UUID, data: OrderStatusUpdate) -> OrderRead:
    result = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    allowed = VALID_TRANSITIONS.get(order.status, set())
    if data.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition from '{order.status}' to '{data.status}'",
        )

    if data.status == "cancelled":
        await _release_reserved_stock(db, order_id)

    order.status = data.status
    await db.flush()
    return OrderRead.model_validate(order)


async def cancel_order(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID) -> OrderRead:
    result = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if order.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending orders can be cancelled")

    return await update_status(db, order_id, OrderStatusUpdate(status="cancelled"))


async def _release_reserved_stock(db: AsyncSession, order_id: uuid.UUID) -> None:
    items = (await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))).scalars().all()
    for oi in items:
        inv = (await db.execute(
            select(Inventory).where(Inventory.product_id == oi.product_id).with_for_update()
        )).scalar_one_or_none()
        if inv:
            inv.quantity_available += oi.quantity
            inv.quantity_reserved = max(0, inv.quantity_reserved - oi.quantity)
            db.add(InventoryMovement(
                product_id=oi.product_id,
                delta=oi.quantity,
                movement_type="release",
                reason=f"Order {order_id} cancelled",
            ))
