"""Notification creation and query helpers."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.models.notification import Notification
from app.models.post import Post


POST_LIKE = "post_like"
POST_REPLY = "post_reply"


def _preview(text: str | None, max_length: int = 120) -> str:
    value = " ".join((text or "").split())
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 1]}..."


class NotificationService:
    """Service for activity notifications."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_post_like_notification(
        self,
        post: Post,
        actor_user_id: UUID,
    ) -> Notification | None:
        """Create or refresh a like notification for a post owner."""
        if post.author_id is None or post.author_id == actor_user_id:
            return None

        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(Notification).where(
                Notification.recipient_user_id == post.author_id,
                Notification.actor_user_id == actor_user_id,
                Notification.type == POST_LIKE,
                Notification.post_id == post.id,
            )
        )
        notification = result.scalar_one_or_none()
        if notification is None:
            notification = Notification(
                recipient_user_id=post.author_id,
                actor_user_id=actor_user_id,
                type=POST_LIKE,
                target_type=post.post_type,
                post_id=post.id,
                target_preview=_preview(post.content_text),
            )
            self.db.add(notification)
        else:
            notification.target_type = post.post_type
            notification.target_preview = _preview(post.content_text)
            notification.created_at = now
            notification.updated_at = now
            notification.read_at = None

        await self.db.flush()
        return notification

    async def create_post_reply_notification(
        self,
        post: Post,
        comment: Comment,
        actor_user_id: UUID,
    ) -> Notification | None:
        """Create a reply notification for a post owner."""
        if post.author_id is None or post.author_id == actor_user_id:
            return None

        notification = Notification(
            recipient_user_id=post.author_id,
            actor_user_id=actor_user_id,
            type=POST_REPLY,
            target_type=post.post_type,
            post_id=post.id,
            comment_id=comment.id,
            target_preview=_preview(comment.content),
        )
        self.db.add(notification)
        await self.db.flush()
        return notification

    async def list_notifications(
        self,
        recipient_user_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Notification], int]:
        """Return notifications and current unread count for a recipient."""
        unread_count = await self.get_unread_count(recipient_user_id)
        result = await self.db.execute(
            select(Notification)
            .where(Notification.recipient_user_id == recipient_user_id)
            .options(selectinload(Notification.actor))
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), unread_count

    async def get_unread_count(self, recipient_user_id: UUID) -> int:
        """Return unread notification count for a recipient."""
        result = await self.db.execute(
            select(func.count(Notification.id)).where(
                Notification.recipient_user_id == recipient_user_id,
                Notification.read_at.is_(None),
            )
        )
        return int(result.scalar_one() or 0)

    async def mark_read(
        self,
        notification_id: UUID,
        recipient_user_id: UUID,
    ) -> bool:
        """Mark one notification as read."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.recipient_user_id == recipient_user_id,
            )
            .values(read_at=now)
        )
        await self.db.flush()
        return (result.rowcount or 0) > 0

    async def mark_all_read(self, recipient_user_id: UUID) -> int:
        """Mark all notifications as read for a recipient."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.recipient_user_id == recipient_user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=now)
        )
        await self.db.flush()
        return int(result.rowcount or 0)
