"""Authentication service."""

from datetime import timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    check_needs_rehash,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.models.user import User
from app.schemas.user import TokenResponse, UserCreate


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, user_data: UserCreate) -> User:
        """Register a new user."""
        # Check if username exists
        existing = await self.db.execute(
            select(User).where(User.username == user_data.username)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Username already exists")

        # Check if email exists
        if user_data.email:
            existing = await self.db.execute(
                select(User).where(User.email == user_data.email)
            )
            if existing.scalar_one_or_none():
                raise ValueError("Email already exists")

        # Create user
        user = User(
            username=user_data.username,
            hashed_password=hash_password(user_data.password),
            email=user_data.email,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def authenticate(
        self, username: str, password: str
    ) -> Optional[User]:
        """Authenticate user by username and password."""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        # Check if password needs rehash
        if check_needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(password)
            await self.db.flush()

        return user

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    def create_tokens(self, user_id: UUID) -> TokenResponse:
        """Create access and refresh tokens for user."""
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    async def refresh_tokens(self, refresh_token: str) -> Optional[TokenResponse]:
        """Refresh access token using refresh token."""
        user_id = verify_token(refresh_token, token_type="refresh")
        if not user_id:
            return None

        # Verify user still exists and is active
        user = await self.get_user_by_id(user_id)
        if not user or not user.is_active:
            return None

        return self.create_tokens(user_id)
