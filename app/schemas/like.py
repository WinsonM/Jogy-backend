"""Like schemas for request/response validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LikeResponse(BaseModel):
    """Schema for like response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    post_id: UUID
    created_at: datetime


class LikeToggleResponse(BaseModel):
    """Schema for like toggle response."""

    liked: bool
    likes_count: int
