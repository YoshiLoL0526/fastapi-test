import asyncio
import random
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import settings
from api.models.order import Order
from api.models.payment import Payment
from api.schemas.payment import PaymentRead


async def _simulate_gateway() -> tuple[bool, str | None, str | None]:
    delay_ms = random.randint(settings.payment_delay_min_ms, settings.payment_delay_max_ms)
    await asyncio.sleep(delay_ms / 1000)
    failed = random.random() < settings.payment_failure_rate
    if failed:
        return False, None, "Card declined by issuer"
    return True, str(uuid.uuid4()), None


async def initiate_payment(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID) -> PaymentRead:
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if order.status not in {"pending", "processing"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order is not payable")

    existing = (await db.execute(select(Payment).where(Payment.order_id == order_id))).scalar_one_or_none()
    if existing and existing.status == "succeeded":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order already paid")

    succeeded, gateway_ref, failure_reason = await _simulate_gateway()
    pay_status = "succeeded" if succeeded else "failed"

    if existing:
        existing.status = pay_status
        existing.gateway_ref = gateway_ref
        existing.failure_reason = failure_reason
        payment = existing
    else:
        payment = Payment(
            order_id=order_id,
            status=pay_status,
            amount=float(order.total),
            gateway_ref=gateway_ref,
            failure_reason=failure_reason,
        )
        db.add(payment)

    if succeeded:
        order.status = "processing"

    await db.flush()
    return PaymentRead.model_validate(payment)


async def get_payment(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID) -> PaymentRead:
    order = await db.get(Order, order_id)
    if not order or order.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    payment = (await db.execute(select(Payment).where(Payment.order_id == order_id))).scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return PaymentRead.model_validate(payment)


async def refund(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID) -> PaymentRead:
    order = await db.get(Order, order_id)
    if not order or order.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != "delivered":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only delivered orders can be refunded")

    payment = (await db.execute(select(Payment).where(Payment.order_id == order_id))).scalar_one_or_none()
    if not payment or payment.status != "succeeded":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No successful payment to refund")

    delay_ms = random.randint(settings.payment_delay_min_ms, settings.payment_delay_max_ms)
    await asyncio.sleep(delay_ms / 1000)

    payment.status = "refunded"
    order.status = "refunded"
    await db.flush()
    return PaymentRead.model_validate(payment)
