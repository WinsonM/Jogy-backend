"""User schemas for request/response validation."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.base import CamelORMModel


class UserBase(BaseModel):
    """Base user schema."""

    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    """Schema for user registration."""

    password: str = Field(..., min_length=8, max_length=100)
    email: Optional[EmailStr] = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password strength."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    """Schema for user login."""

    username: str
    password: str


class UserUpdate(BaseModel):
    """Schema for updating user profile."""

    username: Optional[str] = Field(None, min_length=3, max_length=50)
    avatar_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = Field(None, max_length=1000)
    gender: Optional[str] = Field(None, max_length=20)
    birthday: Optional[date] = None
    email: Optional[EmailStr] = None


class UserResponse(CamelORMModel):
    """Schema for user response (no sensitive fields).

    Serializes to camelCase for frontend compatibility:
    avatar_url -> avatarUrl, created_at -> createdAt, etc.
    """

    id: UUID
    username: str
    avatar_url: Optional[str] = ""
    bio: Optional[str] = ""
    gender: str = "保密"
    birthday: Optional[date] = None
    created_at: Optional[datetime] = None
    followers: int = 0
    following: int = 0


class UserInDB(UserResponse):
    """Internal user schema with additional fields."""

    email: Optional[str] = None
    is_active: bool = True


class TokenResponse(BaseModel):
    """Schema for JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshTokenRequest(BaseModel):
    """Schema for token refresh request."""

    refresh_token: str
