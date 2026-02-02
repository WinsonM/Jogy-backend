"""Post schemas for request/response validation."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserResponse


class LocationPoint(BaseModel):
    """Schema for location coordinates."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class PostBase(BaseModel):
    """Base post schema."""

    content_text: str = Field(..., min_length=1, max_length=5000)
    address_name: Optional[str] = Field(None, max_length=500)


class PostCreate(PostBase):
    """Schema for creating a post."""

    media_urls: Optional[list[str]] = Field(default_factory=list, max_length=10)
    location: LocationPoint


class PostResponse(BaseModel):
    """Schema for post response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_id: UUID
    content_text: str
    media_urls: Optional[list[str]] = None
    location: LocationPoint
    address_name: Optional[str] = None
    created_at: datetime
    likes_count: int = 0
    comments_count: int = 0

    # Populated from join
    author: Optional[UserResponse] = None


class PostDiscoverRequest(BaseModel):
    """Schema for discover request with viewport."""

    min_latitude: float = Field(..., ge=-90, le=90)
    min_longitude: float = Field(..., ge=-180, le=180)
    max_latitude: float = Field(..., ge=-90, le=90)
    max_longitude: float = Field(..., ge=-180, le=180)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PostDiscoverResponse(BaseModel):
    """Schema for discover response."""

    posts: list[PostResponse]
    total: int
    has_more: bool
