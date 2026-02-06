"""User browsing history model."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class UserBrowsingHistory(Base, UUIDMixin):
    """Stores latest viewed timestamp per user-post pair."""

    __tablename__ = "user_browsing_history"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    post_id: Mapped[UUID] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="browsing_history",
    )
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="browsing_history",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_user_browsing_history_user_post"),
        Index("idx_user_browsing_history_user_viewed_at", "user_id", "viewed_at"),
    )

