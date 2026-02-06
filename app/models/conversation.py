"""Conversation model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.conversation_member import ConversationMember
    from app.models.message import Message


class Conversation(Base, UUIDMixin, TimestampMixin):
    """Conversation entity for direct or group chat."""

    __tablename__ = "conversations"

    conversation_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="direct",
        server_default="direct",
    )
    last_message_id: Mapped[Optional[UUID]] = mapped_column(
        nullable=True,
        index=True,
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    members: Mapped[list["ConversationMember"]] = relationship(
        "ConversationMember",
        back_populates="conversation",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_conversations_last_message_at", "last_message_at"),
    )

