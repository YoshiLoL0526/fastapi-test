import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.core.dependencies import AdminUser, DBSession
from api.models.product import Category
from api.schemas.category import CategoryCreate, CategoryRead, CategoryTree, CategoryUpdate
from api.schemas.common import MessageResponse

router = APIRouter(prefix="/categories", tags=["categories"])


def _build_tree(categories: list[Category]) -> list[CategoryTree]:
    by_id = {c.id: CategoryTree.model_validate(c) for c in categories}
    roots: list[CategoryTree] = []
    for node in by_id.values():
        if node.parent_id and node.parent_id in by_id:
            by_id[node.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


@router.get("/", response_model=list[CategoryTree])
async def list_categories(db: DBSession):
    result = await db.execute(select(Category).where(Category.is_active.is_(True)).order_by(Category.name))
    categories = result.scalars().all()
    return _build_tree(list(categories))


@router.post("/", response_model=CategoryRead, status_code=201)
async def create_category(data: CategoryCreate, db: DBSession, _admin: AdminUser):
    if data.parent_id:
        parent = await db.get(Category, data.parent_id)
        if not parent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent category not found")

    existing = (await db.execute(select(Category).where(Category.slug == data.slug))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category slug already exists")

    category = Category(**data.model_dump())
    db.add(category)
    await db.flush()
    return CategoryRead.model_validate(category)


@router.get("/{category_id}", response_model=CategoryRead)
async def get_category(category_id: uuid.UUID, db: DBSession):
    category = await db.get(Category, category_id)
    if not category or not category.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return CategoryRead.model_validate(category)


@router.put("/{category_id}", response_model=CategoryRead)
async def update_category(category_id: uuid.UUID, data: CategoryUpdate, db: DBSession, _admin: AdminUser):
    category = await db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(category, field, value)
    await db.flush()
    return CategoryRead.model_validate(category)


@router.delete("/{category_id}", response_model=MessageResponse)
async def delete_category(category_id: uuid.UUID, db: DBSession, _admin: AdminUser):
    category = await db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    category.is_active = False
    return MessageResponse(message="Category deactivated")
