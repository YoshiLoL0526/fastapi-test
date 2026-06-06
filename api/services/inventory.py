import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.inventory import Inventory, InventoryMovement
from api.schemas.common import PaginatedResponse
from api.schemas.inventory import InventoryAdjust, InventoryMovementRead, InventoryRead, InventoryUpdate


async def get_inventory(db: AsyncSession, product_id: uuid.UUID) -> InventoryRead:
    inv = (await db.execute(select(Inventory).where(Inventory.product_id == product_id))).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory record not found")
    return InventoryRead.model_validate(inv)


async def update_inventory(db: AsyncSession, product_id: uuid.UUID, data: InventoryUpdate) -> InventoryRead:
    inv = (await db.execute(select(Inventory).where(Inventory.product_id == product_id))).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory record not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(inv, field, value)

    await db.flush()
    return InventoryRead.model_validate(inv)


async def adjust_stock(db: AsyncSession, product_id: uuid.UUID, data: InventoryAdjust) -> InventoryRead:
    inv = (await db.execute(
        select(Inventory).where(Inventory.product_id == product_id).with_for_update()
    )).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory record not found")

    new_qty = inv.quantity_available + data.delta
    if new_qty < 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot reduce stock below 0 (current: {inv.quantity_available})",
        )

    inv.quantity_available = new_qty
    db.add(InventoryMovement(
        product_id=product_id,
        delta=data.delta,
        movement_type="adjustment",
        reason=data.reason,
    ))
    await db.flush()
    return InventoryRead.model_validate(inv)


async def get_low_stock(
    db: AsyncSession, *, page: int = 1, page_size: int = 20
) -> PaginatedResponse[InventoryRead]:
    stmt = select(Inventory).where(Inventory.quantity_available <= Inventory.low_stock_threshold)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    result = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))

    return PaginatedResponse(
        items=[InventoryRead.model_validate(i) for i in result.scalars().all()],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


async def get_movements(
    db: AsyncSession, product_id: uuid.UUID, *, page: int = 1, page_size: int = 20
) -> PaginatedResponse[InventoryMovementRead]:
    stmt = select(InventoryMovement).where(InventoryMovement.product_id == product_id)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    result = await db.execute(
        stmt.order_by(InventoryMovement.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )

    return PaginatedResponse(
        items=[InventoryMovementRead.model_validate(m) for m in result.scalars().all()],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )
