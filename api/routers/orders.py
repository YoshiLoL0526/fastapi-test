import uuid

from fastapi import APIRouter, BackgroundTasks

from api.core.dependencies import AdminUser, CurrentUser, DBSession
from api.schemas.common import MessageResponse, PaginatedResponse
from api.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate
from api.services import order as order_service
from api.tasks.background import send_order_confirmation

router = APIRouter(prefix="/orders", tags=["orders"])


# ── Admin routes must be defined BEFORE /{order_id} to avoid path conflicts ──

@router.get("/admin/all", response_model=PaginatedResponse[OrderRead])
async def admin_list_orders(
    db: DBSession,
    _admin: AdminUser,
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
):
    return await order_service.get_orders(db, page=page, page_size=page_size, status_filter=status_filter)


@router.patch("/admin/{order_id}/status", response_model=OrderRead)
async def admin_update_status(order_id: uuid.UUID, data: OrderStatusUpdate, db: DBSession, _admin: AdminUser):
    return await order_service.update_status(db, order_id, data)


# ── User routes ───────────────────────────────────────────────────────────────

@router.post("/", response_model=OrderRead, status_code=201)
async def checkout(data: OrderCreate, current_user: CurrentUser, db: DBSession, bg: BackgroundTasks):
    order = await order_service.checkout(db, uuid.UUID(current_user["sub"]), data)
    bg.add_task(send_order_confirmation, order.id, current_user["sub"])
    return order


@router.get("/", response_model=PaginatedResponse[OrderRead])
async def list_orders(
    current_user: CurrentUser,
    db: DBSession,
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
):
    return await order_service.get_orders(
        db, user_id=uuid.UUID(current_user["sub"]), page=page, page_size=page_size, status_filter=status_filter
    )


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    return await order_service.get_order(db, order_id, uuid.UUID(current_user["sub"]))


@router.post("/{order_id}/cancel", response_model=OrderRead)
async def cancel_order(order_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    return await order_service.cancel_order(db, order_id, uuid.UUID(current_user["sub"]))
