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

    title: Optional[str] = Field(None, max_length=100)
    content_text: str = Field(..., min_length=1, max_length=5000)
    post_type: str = Field(default="bubble", max_length=20)
    address_name: Optional[str] = Field(None, max_length=500)


class PostCreate(PostBase):
    """Schema for creating a post."""

    media_urls: Optional[list[str]] = Field(default_factory=list, max_length=10)
    location: LocationPoint
    expire_at: Optional[datetime] = None


class PostResponse(BaseModel):
    """Schema for post response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_id: Optional[UUID]
    title: Optional[str] = None
    content_text: str
    post_type: str = "bubble"
    media_urls: Optional[list[str]] = None
    location: LocationPoint
    address_name: Optional[str] = None
    expire_at: Optional[datetime] = None
    created_at: datetime
    likes_count: int = 0
    comments_count: int = 0
    favorites_count: int = 0
    is_liked: bool = False
    is_favorited: bool = False

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
