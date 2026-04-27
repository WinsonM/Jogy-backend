"""Post model with PostGIS geometry."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.browsing_history import UserBrowsingHistory
    from app.models.comment import Comment
    from app.models.like import Like
    from app.models.post_favorite import PostFavorite
    from app.models.user import User


class Post(Base, UUIDMixin, TimestampMixin):
    """Post model with geospatial location."""

    __tablename__ = "posts"

    author_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    post_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="bubble",
        server_default="bubble",
    )
    content_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    media_urls: Mapped[Optional[list[str]]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
    )
    # PostGIS Point geometry with SRID 4326 (WGS84)
    location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=False,
    )
    address_name: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    expire_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Denormalized counts for performance
    likes_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    comments_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    favorites_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    # Relationships
    author: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="posts",
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="post",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    likes: Mapped[list["Like"]] = relationship(
        "Like",
        back_populates="post",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    favorites: Mapped[list["PostFavorite"]] = relationship(
        "PostFavorite",
        back_populates="post",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    browsing_history: Mapped[list["UserBrowsingHistory"]] = relationship(
        "UserBrowsingHistory",
        back_populates="post",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    # Spatial index for efficient geo queries
    __table_args__ = (
        Index("idx_posts_location", location, postgresql_using="gist"),
        Index("idx_posts_created_at", "created_at"),
        Index(
            "idx_posts_expire_at",
            "expire_at",
            postgresql_where=text("expire_at IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Post(id={self.id}, author_id={self.author_id})>"
