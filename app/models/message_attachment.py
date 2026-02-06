"""Message attachment model."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.message import Message


class MessageAttachment(Base, UUIDMixin, TimestampMixin):
    """Attachment metadata for message media/files."""

    __tablename__ = "message_attachments"

    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    file_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    file_size: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    message: Mapped["Message"] = relationship(
        "Message",
        back_populates="attachments",
    )
