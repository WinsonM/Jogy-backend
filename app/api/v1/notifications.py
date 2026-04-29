"""Activity notification routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.core.database import get_db
from app.schemas.notification import (
    NotificationActionResponse,
    NotificationListResponse,
    NotificationUnreadCountResponse,
)
from app.services.notification import NotificationService

router = APIRouter()


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    """Get current user's activity notifications."""
    service = NotificationService(db)
    notifications, unread_count = await service.list_notifications(
        recipient_user_id=current_user_id,
        limit=limit,
        offset=offset,
    )
    return NotificationListResponse(
        notifications=notifications,
        unread_count=unread_count,
    )


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
async def get_notification_unread_count(
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> NotificationUnreadCountResponse:
    """Get current user's unread notification count."""
    service = NotificationService(db)
    return NotificationUnreadCountResponse(
        unread_count=await service.get_unread_count(current_user_id)
    )


@router.patch("/{notification_id}/read", response_model=NotificationActionResponse)
async def mark_notification_read(
    notification_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> NotificationActionResponse:
    """Mark a single notification as read."""
    service = NotificationService(db)
    updated = await service.mark_read(notification_id, current_user_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    return NotificationActionResponse()


@router.post("/read-all", response_model=NotificationActionResponse)
async def mark_all_notifications_read(
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> NotificationActionResponse:
    """Mark all current user's notifications as read."""
    service = NotificationService(db)
    await service.mark_all_read(current_user_id)
    return NotificationActionResponse()
