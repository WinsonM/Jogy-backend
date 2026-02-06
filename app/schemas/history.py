"""Browsing history schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.post import PostResponse


class HistoryCreateRequest(BaseModel):
    """Request for writing/refreshing a browsing history item."""

    post_id: UUID


class HistoryItemResponse(BaseModel):
    """Single browsing history item."""

    post: PostResponse
    viewed_at: datetime


class HistoryListResponse(BaseModel):
    """List response for browsing history."""

    items: list[HistoryItemResponse]
    total: int
    has_more: bool

