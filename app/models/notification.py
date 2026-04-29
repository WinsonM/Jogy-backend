"""Activity notification model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.user import User


class Notification(Base, UUIDMixin, TimestampMixin):
    """Notification generated from interactions with a user's posts."""

    __tablename__ = "notifications"

    recipient_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    post_id: Mapped[UUID] = mapped_column(
        nullable=False,
        index=True,
    )
    comment_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("comments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_preview: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    recipient: Mapped["User"] = relationship(
        "User",
        foreign_keys=[recipient_user_id],
    )
    actor: Mapped["User"] = relationship(
        "User",
        foreign_keys=[actor_user_id],
    )
    comment: Mapped[Optional["Comment"]] = relationship("Comment")

    __table_args__ = (
        Index("idx_notifications_recipient_created", "recipient_user_id", "created_at"),
        Index("idx_notifications_recipient_unread", "recipient_user_id", "read_at"),
        Index(
            "uq_notifications_post_like",
            "recipient_user_id",
            "actor_user_id",
            "type",
            "post_id",
            unique=True,
            postgresql_where=text("type = 'post_like'"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Notification(id={self.id}, recipient_user_id={self.recipient_user_id}, "
            f"type={self.type}, post_id={self.post_id})>"
        )
