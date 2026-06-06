import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.dependencies import CurrentUser, DBSession
from api.schemas.user import TokenRefresh, TokenResponse, UserCreate, UserRead
from api.schemas.common import MessageResponse
from api.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", response_model=UserRead, status_code=201)
async def register(data: UserCreate, db: DBSession):
    return await auth_service.register(db, data)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: DBSession):
    return await auth_service.login(db, data.email, data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: TokenRefresh, db: DBSession):
    return await auth_service.refresh(db, data.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(data: TokenRefresh, current_user: CurrentUser, db: DBSession):
    await auth_service.logout(db, uuid.UUID(current_user["sub"]), data.refresh_token)
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser, db: DBSession):
    from sqlalchemy import select
    from api.models.user import User
    user = (await db.execute(select(User).where(User.id == uuid.UUID(current_user["sub"])))).scalar_one_or_none()
    if not user:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserRead.model_validate(user)
