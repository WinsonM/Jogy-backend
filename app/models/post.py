"""Post model with PostGIS geometry."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.like import Like
    from app.models.user import User


class Post(Base, UUIDMixin, TimestampMixin):
    """Post model with geospatial location."""

    __tablename__ = "posts"

    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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

    # Denormalized counts for performance
    likes_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    comments_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    # Relationships
    author: Mapped["User"] = relationship(
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

    # Spatial index for efficient geo queries
    __table_args__ = (
        Index("idx_posts_location", location, postgresql_using="gist"),
        Index("idx_posts_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Post(id={self.id}, author_id={self.author_id})>"
