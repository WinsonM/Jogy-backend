"""Comment model with self-referential tree structure."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class Comment(Base, UUIDMixin, TimestampMixin):
    """Comment model with nested replies support."""

    __tablename__ = "comments"

    post_id: Mapped[UUID] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # Self-referential for tree structure
    parent_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Denormalized reply count for performance
    replies_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    # Relationships
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="comments",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="comments",
    )
    # Self-referential relationship for parent
    parent: Mapped[Optional["Comment"]] = relationship(
        "Comment",
        remote_side="Comment.id",
        back_populates="replies",
    )
    # Children replies
    replies: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="parent",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_comments_post_parent", "post_id", "parent_id"),
    )

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, post_id={self.post_id}, parent_id={self.parent_id})>"
