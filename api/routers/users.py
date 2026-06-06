import math
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from api.core.dependencies import AdminUser, CurrentUser, DBSession
from api.core.security import hash_password, verify_password
from api.models.user import Address, User
from api.schemas.common import MessageResponse, PaginatedResponse
from api.schemas.user import AddressCreate, AddressRead, AddressUpdate, PasswordChange, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=PaginatedResponse[UserRead])
async def list_users(db: DBSession, _admin: AdminUser, page: int = 1, page_size: int = 20):
    stmt = select(User)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    result = await db.execute(stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    users = result.scalars().all()
    return PaginatedResponse(
        items=[UserRead.model_validate(u) for u in users],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/me", response_model=UserRead)
async def get_me(current_user: CurrentUser, db: DBSession):
    user = await db.get(User, uuid.UUID(current_user["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserRead.model_validate(user)


@router.put("/me", response_model=UserRead)
async def update_me(data: UserUpdate, current_user: CurrentUser, db: DBSession):
    user = await db.get(User, uuid.UUID(current_user["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await db.flush()
    return UserRead.model_validate(user)


@router.post("/me/password", response_model=MessageResponse)
async def change_password(data: PasswordChange, current_user: CurrentUser, db: DBSession):
    user = await db.get(User, uuid.UUID(current_user["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.hashed_password = hash_password(data.new_password)
    await db.flush()
    return MessageResponse(message="Password changed successfully")


# ── Addresses ─────────────────────────────────────────────────────────────────

@router.get("/me/addresses", response_model=list[AddressRead])
async def list_addresses(current_user: CurrentUser, db: DBSession):
    result = await db.execute(select(Address).where(Address.user_id == uuid.UUID(current_user["sub"])))
    return [AddressRead.model_validate(a) for a in result.scalars().all()]


@router.post("/me/addresses", response_model=AddressRead, status_code=201)
async def create_address(data: AddressCreate, current_user: CurrentUser, db: DBSession):
    user_id = uuid.UUID(current_user["sub"])
    if data.is_default:
        existing = (await db.execute(
            select(Address).where(Address.user_id == user_id, Address.is_default.is_(True))
        )).scalars().all()
        for addr in existing:
            addr.is_default = False
    address = Address(user_id=user_id, **data.model_dump())
    db.add(address)
    await db.flush()
    return AddressRead.model_validate(address)


@router.put("/me/addresses/{address_id}", response_model=AddressRead)
async def update_address(address_id: uuid.UUID, data: AddressUpdate, current_user: CurrentUser, db: DBSession):
    user_id = uuid.UUID(current_user["sub"])
    address = await db.get(Address, address_id)
    if not address or address.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    if data.is_default:
        existing = (await db.execute(
            select(Address).where(Address.user_id == user_id, Address.is_default.is_(True))
        )).scalars().all()
        for addr in existing:
            addr.is_default = False
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(address, field, value)
    await db.flush()
    return AddressRead.model_validate(address)


@router.delete("/me/addresses/{address_id}", response_model=MessageResponse)
async def delete_address(address_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    user_id = uuid.UUID(current_user["sub"])
    address = await db.get(Address, address_id)
    if not address or address.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    await db.delete(address)
    return MessageResponse(message="Address deleted")


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: uuid.UUID, _admin: AdminUser, db: DBSession):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserRead.model_validate(user)
