"""Post favorite model."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class PostFavorite(Base, UUIDMixin, TimestampMixin):
    """User favorite relation for posts."""

    __tablename__ = "post_favorites"

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

    user: Mapped["User"] = relationship(
        "User",
        back_populates="post_favorites",
    )
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="favorites",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_post_favorites_user_post"),
    )
