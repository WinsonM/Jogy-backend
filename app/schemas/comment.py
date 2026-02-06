"""Comment schemas for request/response validation."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserResponse


class CommentBase(BaseModel):
    """Base comment schema."""

    content: str = Field(..., min_length=1, max_length=2000)


class CommentCreate(CommentBase):
    """Schema for creating a comment."""

    parent_id: Optional[UUID] = None
    reply_to_user_id: Optional[UUID] = None


class CommentResponse(BaseModel):
    """Schema for comment response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    user_id: Optional[UUID]
    content: str
    parent_id: Optional[UUID] = None
    root_id: Optional[UUID] = None
    reply_to_user_id: Optional[UUID] = None
    reply_to_username: Optional[str] = None
    created_at: datetime
    replies_count: int = 0
    likes_count: int = 0
    is_liked: bool = False

    # Populated from join
    user: Optional[UserResponse] = None


class CommentTreeResponse(BaseModel):
    """Schema for comment tree response with nested replies."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    user_id: Optional[UUID]
    content: str
    parent_id: Optional[UUID] = None
    root_id: Optional[UUID] = None
    reply_to_user_id: Optional[UUID] = None
    reply_to_username: Optional[str] = None
    created_at: datetime
    replies_count: int = 0
    likes_count: int = 0
    is_liked: bool = False

    # Populated from join
    user: Optional[UserResponse] = None

    # Nested replies (initially top 2)
    replies: list["CommentTreeResponse"] = Field(default_factory=list)

    # Pagination info for replies
    has_more_replies: bool = False


class CommentListRequest(BaseModel):
    """Schema for listing comments."""

    parent_id: Optional[UUID] = None  # None for root comments
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class CommentListResponse(BaseModel):
    """Schema for comment list response."""

    comments: list[CommentTreeResponse]
    total: int
    has_more: bool
