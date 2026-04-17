"""User model."""

from datetime import date
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.browsing_history import UserBrowsingHistory
    from app.models.comment_like import CommentLike
    from app.models.conversation_member import ConversationMember
    from app.models.comment import Comment
    from app.models.follow import Follow
    from app.models.like import Like
    from app.models.message import Message
    from app.models.post import Post
    from app.models.post_favorite import PostFavorite


class User(Base, UUIDMixin, TimestampMixin):
    """User model for authentication and profile."""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    bio: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    gender: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="保密",
        server_default="保密",
    )
    birthday: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    # Relationships
    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="author",
        lazy="selectin",
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="user",
        foreign_keys="Comment.user_id",
        lazy="selectin",
    )
    likes: Mapped[list["Like"]] = relationship(
        "Like",
        back_populates="user",
        lazy="selectin",
    )
    post_favorites: Mapped[list["PostFavorite"]] = relationship(
        "PostFavorite",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    comment_likes: Mapped[list["CommentLike"]] = relationship(
        "CommentLike",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    following_relations: Mapped[list["Follow"]] = relationship(
        "Follow",
        foreign_keys="Follow.follower_id",
        back_populates="follower",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    follower_relations: Mapped[list["Follow"]] = relationship(
        "Follow",
        foreign_keys="Follow.followee_id",
        back_populates="followee",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    conversation_memberships: Mapped[list["ConversationMember"]] = relationship(
        "ConversationMember",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    sent_messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="sender",
        lazy="selectin",
    )
    browsing_history: Mapped[list["UserBrowsingHistory"]] = relationship(
        "UserBrowsingHistory",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    @property
    def followers(self) -> int:
        """Count of users following this user."""
        return len(self.follower_relations) if self.follower_relations else 0

    @property
    def following(self) -> int:
        """Count of users this user is following."""
        return len(self.following_relations) if self.following_relations else 0

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"
