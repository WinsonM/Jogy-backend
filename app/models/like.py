"""Like model."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class Like(Base, UUIDMixin, TimestampMixin):
    """Like model for post likes."""

    __tablename__ = "likes"

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

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="likes",
    )
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="likes",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_likes_user_post"),
    )

    def __repr__(self) -> str:
        return f"<Like(id={self.id}, user_id={self.user_id}, post_id={self.post_id})>"
