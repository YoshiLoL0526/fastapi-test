import uuid

from fastapi import APIRouter

from api.core.dependencies import CurrentUser, DBSession
from api.schemas.payment import PaymentInitiate, PaymentRead
from api.services import payment as payment_service

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/", response_model=PaymentRead, status_code=201)
async def initiate_payment(data: PaymentInitiate, current_user: CurrentUser, db: DBSession):
    return await payment_service.initiate_payment(db, data.order_id, uuid.UUID(current_user["sub"]))


@router.get("/orders/{order_id}", response_model=PaymentRead)
async def get_payment(order_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    return await payment_service.get_payment(db, order_id, uuid.UUID(current_user["sub"]))


@router.post("/orders/{order_id}/refund", response_model=PaymentRead)
async def refund(order_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    return await payment_service.refund(db, order_id, uuid.UUID(current_user["sub"]))
