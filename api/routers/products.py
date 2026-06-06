import uuid

from fastapi import APIRouter

from api.core.dependencies import AdminUser, DBSession
from api.schemas.common import MessageResponse, PaginatedResponse
from api.schemas.product import ProductCreate, ProductDetail, ProductRead, ProductUpdate
from api.services import product as product_service

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/", response_model=PaginatedResponse[ProductRead])
async def list_products(
    db: DBSession,
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
):
    return await product_service.list_products(
        db,
        page=page,
        page_size=page_size,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        search=search,
        in_stock=in_stock,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.post("/", response_model=ProductRead, status_code=201)
async def create_product(data: ProductCreate, db: DBSession, _admin: AdminUser):
    return await product_service.create_product(db, data)


@router.get("/{product_id}", response_model=ProductDetail)
async def get_product(product_id: uuid.UUID, db: DBSession):
    return await product_service.get_product(db, product_id)


@router.put("/{product_id}", response_model=ProductRead)
async def update_product(product_id: uuid.UUID, data: ProductUpdate, db: DBSession, _admin: AdminUser):
    return await product_service.update_product(db, product_id, data)


@router.delete("/{product_id}", response_model=MessageResponse)
async def delete_product(product_id: uuid.UUID, db: DBSession, _admin: AdminUser):
    await product_service.delete_product(db, product_id)
    return MessageResponse(message="Product deactivated")


@router.get("/{product_id}/related", response_model=list[ProductRead])
async def related_products(product_id: uuid.UUID, db: DBSession, limit: int = 4):
    return await product_service.get_related_products(db, product_id, limit=limit)
