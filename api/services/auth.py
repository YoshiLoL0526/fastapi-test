import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import settings
from api.core.security import JWTError, create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from api.models.user import RefreshToken, User
from api.schemas.user import TokenResponse, UserCreate, UserRead


async def register(db: AsyncSession, data: UserCreate) -> UserRead:
    dup_email = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if dup_email:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    dup_username = (await db.execute(select(User).where(User.username == data.username))).scalar_one_or_none()
    if dup_username:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    user = User(
        email=data.email,
        username=data.username,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
    )
    db.add(user)
    await db.flush()
    return UserRead.model_validate(user)


async def login(db: AsyncSession, email: str, password: str) -> TokenResponse:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    access_token = create_access_token(str(user.id), user.role)
    refresh_token_str = create_refresh_token(str(user.id))

    db.add(RefreshToken(
        user_id=user.id,
        token=refresh_token_str,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    ))
    await db.flush()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token_str)


async def refresh(db: AsyncSession, refresh_token_str: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token_str)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    record = (await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == refresh_token_str,
            RefreshToken.revoked.is_(False),
        )
    )).scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or not found")

    expires = record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or disabled")

    record.revoked = True

    new_access = create_access_token(str(user.id), user.role)
    new_refresh_str = create_refresh_token(str(user.id))
    db.add(RefreshToken(
        user_id=user.id,
        token=new_refresh_str,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    ))
    await db.flush()
    return TokenResponse(access_token=new_access, refresh_token=new_refresh_str)


async def logout(db: AsyncSession, user_id: uuid.UUID, refresh_token_str: str) -> None:
    record = (await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == refresh_token_str,
            RefreshToken.user_id == user_id,
        )
    )).scalar_one_or_none()
    if record:
        record.revoked = True
