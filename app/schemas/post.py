"""Post schemas for request/response validation."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import CamelModel, CamelORMModel
from app.schemas.user import UserResponse


class LocationPoint(CamelModel):
    """Schema for location coordinates.

    Serializes to camelCase: place_name -> placeName.
    """

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    place_name: Optional[str] = None
    address: Optional[str] = None


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


class PostUpdate(BaseModel):
    """Partial update for an existing post (author only).

    All fields are optional. Only fields explicitly set in the request body
    are applied (semantic of `model_dump(exclude_unset=True)`).

    Note: `location` and `post_type` are intentionally NOT editable here —
    those changes imply "re-publish", not "edit".

    `media_urls` IS editable: lets author add / remove / reorder images
    without losing post identity (likes / comments / favorites stay on
    the same post id).
    """

    title: Optional[str] = Field(None, max_length=100)
    content_text: Optional[str] = Field(None, min_length=1, max_length=5000)
    address_name: Optional[str] = Field(None, max_length=500)
    expire_at: Optional[datetime] = None
    media_urls: Optional[list[str]] = Field(None, max_length=10)


class PostResponse(CamelORMModel):
    """Schema for post response.

    Serializes to camelCase with custom aliases for frontend compatibility:
    - content_text -> "content"
    - media_urls -> "imageUrls"
    - likes_count -> "likes"
    - favorites_count -> "favorites"
    - author -> "user"
    Standard camelCase (auto): is_liked -> isLiked, created_at -> createdAt, etc.
    """

    id: UUID
    author_id: Optional[UUID] = None
    title: Optional[str] = None
    content_text: str = Field(serialization_alias="content")
    post_type: str = "bubble"
    media_urls: Optional[list[str]] = Field(default=None, serialization_alias="imageUrls")
    location: LocationPoint
    address_name: Optional[str] = None
    expire_at: Optional[datetime] = None
    created_at: datetime
    likes_count: int = Field(default=0, serialization_alias="likes")
    comments_count: int = 0
    favorites_count: int = Field(default=0, serialization_alias="favorites")
    is_liked: bool = False
    is_favorited: bool = False

    # Populated from join - serializes as "user" for frontend
    author: Optional[UserResponse] = Field(default=None, serialization_alias="user")

    # Frontend expects a comments array (empty by default, loaded separately)
    comments: list = Field(default_factory=list)


class PostDiscoverRequest(BaseModel):
    """Schema for discover request with viewport."""

    min_latitude: float = Field(..., ge=-90, le=90)
    min_longitude: float = Field(..., ge=-180, le=180)
    max_latitude: float = Field(..., ge=-90, le=90)
    max_longitude: float = Field(..., ge=-180, le=180)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PostDiscoverResponse(CamelModel):
    """Schema for discover response.

    Serializes to camelCase: has_more -> hasMore.
    """

    posts: list[PostResponse]
    total: int
    has_more: bool
