import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.product import Product
from api.models.review import Review

logger = logging.getLogger(__name__)


async def recalculate_product_rating(db: AsyncSession, product_id: uuid.UUID) -> None:
    row = (await db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.product_id == product_id)
    )).one()
    avg_rating, count = row

    product = await db.get(Product, product_id)
    if product:
        product.rating_avg = round(float(avg_rating or 0), 2)
        product.rating_count = count or 0
        await db.flush()
        logger.info("Rating updated for product %s: avg=%.2f count=%d", product_id, product.rating_avg, product.rating_count)


async def notify_low_stock(product_id: uuid.UUID, quantity_available: int) -> None:
    logger.warning("LOW STOCK ALERT: product_id=%s quantity_available=%d", product_id, quantity_available)


async def send_order_confirmation(order_id: uuid.UUID, user_email: str) -> None:
    logger.info("Order confirmation queued: order_id=%s to=%s", order_id, user_email)
