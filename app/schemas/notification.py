"""Notification schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationActorResponse(BaseModel):
    """Minimal actor fields needed by the notification UI."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    avatar_url: Optional[str] = ""


class NotificationResponse(BaseModel):
    """Single activity notification response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recipient_user_id: UUID
    actor_user_id: UUID
    type: str
    target_type: str
    post_id: UUID
    comment_id: Optional[UUID] = None
    target_preview: str = ""
    created_at: datetime
    read_at: Optional[datetime] = None
    actor: Optional[NotificationActorResponse] = None


class NotificationListResponse(BaseModel):
    """Paginated notifications response."""

    notifications: list[NotificationResponse]
    unread_count: int


class NotificationUnreadCountResponse(BaseModel):
    """Unread count response."""

    unread_count: int


class NotificationActionResponse(BaseModel):
    """Generic notification mutation response."""

    success: bool = True
