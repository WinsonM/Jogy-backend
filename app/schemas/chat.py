"""Conversation and message schemas."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.user import UserResponse


class AttachmentInput(BaseModel):
    """Attachment input for message create."""

    file_url: str = Field(..., max_length=500)
    file_name: Optional[str] = Field(None, max_length=255)
    file_size: Optional[int] = None
    mime_type: Optional[str] = Field(None, max_length=100)


class MessageCreateRequest(BaseModel):
    """Create message payload."""

    message_type: str = Field(default="text", max_length=20)
    content_text: Optional[str] = None
    meta: Optional[dict[str, Any]] = None
    attachments: list[AttachmentInput] = Field(default_factory=list)


class MessageResponse(BaseModel):
    """Message response."""

    id: UUID
    conversation_id: UUID
    sender_id: Optional[UUID]
    message_type: str
    content_text: Optional[str]
    meta: Optional[dict[str, Any]] = None
    created_at: datetime
    attachments: list[AttachmentInput] = Field(default_factory=list)


class MessageListResponse(BaseModel):
    """Message pagination response."""

    items: list[MessageResponse]
    total: int
    has_more: bool


class ConversationDirectCreateRequest(BaseModel):
    """Direct conversation create payload."""

    user_id: UUID


class ConversationPinRequest(BaseModel):
    """Pin state update payload."""

    is_pinned: bool


class ConversationSummary(BaseModel):
    """Conversation summary for list page."""

    id: UUID
    conversation_type: str
    participant: Optional[UserResponse] = None
    last_message: Optional[MessageResponse] = None
    last_message_at: Optional[datetime] = None
    is_pinned: bool = False
    unread_count: int = 0


class ConversationListResponse(BaseModel):
    """Conversation list response."""

    items: list[ConversationSummary]
    total: int
    has_more: bool


class ConversationReadRequest(BaseModel):
    """Mark read payload."""

    last_read_message_id: Optional[UUID] = None

