"""Chat message model."""

from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message_attachment import MessageAttachment
    from app.models.user import User


class Message(Base, UUIDMixin, TimestampMixin):
    """Chat message content."""

    __tablename__ = "messages"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    message_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="text",
        server_default="text",
    )
    content_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "meta",
        JSONB,
        nullable=True,
        default=dict,
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )
    sender: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="sent_messages",
    )
    attachments: Mapped[list["MessageAttachment"]] = relationship(
        "MessageAttachment",
        back_populates="message",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_messages_conversation_created_at", "conversation_id", "created_at"),
    )
