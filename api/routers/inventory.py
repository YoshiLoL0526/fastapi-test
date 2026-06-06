import uuid

from fastapi import APIRouter

from api.core.dependencies import AdminUser, DBSession
from api.schemas.common import PaginatedResponse
from api.schemas.inventory import InventoryAdjust, InventoryMovementRead, InventoryRead, InventoryUpdate
from api.services import inventory as inventory_service

router = APIRouter(prefix="/inventory", tags=["inventory"])


# ── Admin routes defined before /{product_id} to avoid path conflict ──

@router.get("/low-stock", response_model=PaginatedResponse[InventoryRead])
async def low_stock_report(db: DBSession, _admin: AdminUser, page: int = 1, page_size: int = 20):
    return await inventory_service.get_low_stock(db, page=page, page_size=page_size)


@router.get("/{product_id}", response_model=InventoryRead)
async def get_inventory(product_id: uuid.UUID, db: DBSession):
    return await inventory_service.get_inventory(db, product_id)


@router.patch("/{product_id}", response_model=InventoryRead)
async def update_inventory(product_id: uuid.UUID, data: InventoryUpdate, db: DBSession, _admin: AdminUser):
    return await inventory_service.update_inventory(db, product_id, data)


@router.post("/{product_id}/adjust", response_model=InventoryRead)
async def adjust_stock(product_id: uuid.UUID, data: InventoryAdjust, db: DBSession, _admin: AdminUser):
    return await inventory_service.adjust_stock(db, product_id, data)


@router.get("/{product_id}/movements", response_model=PaginatedResponse[InventoryMovementRead])
async def get_movements(product_id: uuid.UUID, db: DBSession, _admin: AdminUser, page: int = 1, page_size: int = 20):
    return await inventory_service.get_movements(db, product_id, page=page, page_size=page_size)
