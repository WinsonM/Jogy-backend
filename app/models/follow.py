"""Follow relation model."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class Follow(Base, UUIDMixin, TimestampMixin):
    """User follow relation."""

    __tablename__ = "follows"

    follower_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    followee_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    follower: Mapped["User"] = relationship(
        "User",
        foreign_keys=[follower_id],
        back_populates="following_relations",
    )
    followee: Mapped["User"] = relationship(
        "User",
        foreign_keys=[followee_id],
        back_populates="follower_relations",
    )

    __table_args__ = (
        UniqueConstraint("follower_id", "followee_id", name="uq_follows_follower_followee"),
        CheckConstraint("follower_id <> followee_id", name="ck_follows_no_self_follow"),
    )
