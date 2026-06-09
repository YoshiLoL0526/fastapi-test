import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.inventory import Inventory
from api.models.product import Category, Product
from api.schemas.common import PaginatedResponse
from api.schemas.product import ProductCreate, ProductDetail, ProductRead, ProductUpdate


async def list_products(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    category_id: uuid.UUID | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_rating: float | None = None,
    search: str | None = None,
    in_stock: bool | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> PaginatedResponse[ProductRead]:
    stmt = select(Product).where(Product.is_active.is_(True))

    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    if min_rating is not None:
        stmt = stmt.where(Product.rating_avg >= min_rating)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(or_(Product.name.ilike(pattern), Product.description.ilike(pattern)))
    if in_stock:
        stmt = stmt.join(Inventory, Inventory.product_id == Product.id).where(
            Inventory.quantity_available > 0
        )

    sort_col = getattr(Product, sort_by, Product.created_at)
    stmt = stmt.order_by(sort_col.asc() if sort_dir == "asc" else sort_col.desc())

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    result = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    products = result.scalars().all()

    return PaginatedResponse(
        items=[ProductRead.model_validate(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


async def get_product(db: AsyncSession, product_id: uuid.UUID) -> ProductDetail:
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product_id, Product.is_active.is_(True))
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductDetail.model_validate(product)


async def create_product(db: AsyncSession, data: ProductCreate) -> ProductRead:
    cat = await db.get(Category, data.category_id)
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    existing = (await db.execute(select(Product).where(Product.slug == data.slug))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product slug already exists")

    product = Product(**data.model_dump())
    db.add(product)
    await db.flush()

    inventory = Inventory(product_id=product.id)
    db.add(inventory)
    await db.flush()
    await db.refresh(product)

    return ProductRead.model_validate(product)


async def update_product(db: AsyncSession, product_id: uuid.UUID, data: ProductUpdate) -> ProductRead:
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(product, field, value)

    await db.flush()
    await db.refresh(product)
    return ProductRead.model_validate(product)


async def delete_product(db: AsyncSession, product_id: uuid.UUID) -> None:
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    product.is_active = False


async def get_related_products(db: AsyncSession, product_id: uuid.UUID, limit: int = 4) -> list[ProductRead]:
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    result = await db.execute(
        select(Product)
        .where(
            Product.category_id == product.category_id,
            Product.id != product_id,
            Product.is_active.is_(True),
        )
        .order_by(Product.rating_avg.desc())
        .limit(limit)
    )
    return [ProductRead.model_validate(p) for p in result.scalars().all()]
