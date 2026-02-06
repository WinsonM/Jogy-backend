"""Conversation and message routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.api.deps import get_current_user_id
from app.core.database import get_db
from app.models.conversation import Conversation
from app.models.conversation_member import ConversationMember
from app.models.message import Message
from app.models.message_attachment import MessageAttachment
from app.models.user import User
from app.schemas.chat import (
    ConversationDirectCreateRequest,
    ConversationListResponse,
    ConversationPinRequest,
    ConversationReadRequest,
    ConversationSummary,
    MessageCreateRequest,
    MessageListResponse,
    MessageResponse,
)
from app.schemas.user import UserResponse

router = APIRouter()


async def _get_membership_or_404(
    conversation_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> ConversationMember:
    result = await db.execute(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return member


async def _message_to_response(message: Message, db: AsyncSession) -> MessageResponse:
    attachments_result = await db.execute(
        select(MessageAttachment).where(MessageAttachment.message_id == message.id)
    )
    attachments = attachments_result.scalars().all()
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        message_type=message.message_type,
        content_text=message.content_text,
        meta=message.meta,
        created_at=message.created_at,
        attachments=[
            {
                "file_url": item.file_url,
                "file_name": item.file_name,
                "file_size": item.file_size,
                "mime_type": item.mime_type,
            }
            for item in attachments
        ],
    )


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    """Get current user's conversation list."""
    total_result = await db.execute(
        select(func.count(ConversationMember.id)).where(ConversationMember.user_id == current_user_id)
    )
    total = total_result.scalar() or 0

    membership_result = await db.execute(
        select(ConversationMember)
        .where(ConversationMember.user_id == current_user_id)
        .options(selectinload(ConversationMember.conversation))
        .order_by(ConversationMember.is_pinned.desc(), ConversationMember.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    memberships = membership_result.scalars().all()

    items: list[ConversationSummary] = []
    for member in memberships:
        conversation = member.conversation
        if not conversation:
            continue

        participant = None
        if conversation.conversation_type == "direct":
            participant_result = await db.execute(
                select(User)
                .join(ConversationMember, ConversationMember.user_id == User.id)
                .where(
                    ConversationMember.conversation_id == conversation.id,
                    ConversationMember.user_id != current_user_id,
                )
                .limit(1)
            )
            participant_user = participant_result.scalar_one_or_none()
            if participant_user:
                participant = UserResponse.model_validate(participant_user)

        last_message = None
        if conversation.last_message_id:
            last_message_result = await db.execute(
                select(Message).where(Message.id == conversation.last_message_id)
            )
            last_message_model = last_message_result.scalar_one_or_none()
            if last_message_model:
                last_message = await _message_to_response(last_message_model, db)

        unread_count = 0
        if member.last_read_message_id:
            last_read_result = await db.execute(
                select(Message.created_at).where(Message.id == member.last_read_message_id)
            )
            last_read_time = last_read_result.scalar_one_or_none()
            if last_read_time is not None:
                unread_result = await db.execute(
                    select(func.count(Message.id)).where(
                        Message.conversation_id == conversation.id,
                        Message.sender_id != current_user_id,
                        Message.created_at > last_read_time,
                    )
                )
                unread_count = unread_result.scalar() or 0
        else:
            unread_result = await db.execute(
                select(func.count(Message.id)).where(
                    Message.conversation_id == conversation.id,
                    Message.sender_id != current_user_id,
                )
            )
            unread_count = unread_result.scalar() or 0

        items.append(
            ConversationSummary(
                id=conversation.id,
                conversation_type=conversation.conversation_type,
                participant=participant,
                last_message=last_message,
                last_message_at=conversation.last_message_at,
                is_pinned=member.is_pinned,
                unread_count=unread_count,
            )
        )

    return ConversationListResponse(
        items=items,
        total=total,
        has_more=offset + len(items) < total,
    )


@router.post("/direct", response_model=ConversationSummary, status_code=status.HTTP_201_CREATED)
async def create_direct_conversation(
    request: ConversationDirectCreateRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ConversationSummary:
    """Create or return existing direct conversation with target user."""
    if request.user_id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create direct conversation with yourself",
        )

    target_user_result = await db.execute(select(User).where(User.id == request.user_id))
    target_user = target_user_result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    member_count_alias = aliased(ConversationMember)
    existing_result = await db.execute(
        select(Conversation)
        .join(
            ConversationMember,
            ConversationMember.conversation_id == Conversation.id,
        )
        .where(
            Conversation.conversation_type == "direct",
            select(func.count(member_count_alias.id))
            .where(member_count_alias.conversation_id == Conversation.id)
            .scalar_subquery()
            == 2,
            ConversationMember.user_id.in_([current_user_id, request.user_id]),
        )
        .group_by(Conversation.id)
        .having(func.count(func.distinct(ConversationMember.user_id)) == 2)
    )
    existing = existing_result.scalars().first()
    if existing:
        member_result = await db.execute(
            select(ConversationMember).where(
                ConversationMember.conversation_id == existing.id,
                ConversationMember.user_id == current_user_id,
            )
        )
        member = member_result.scalar_one()
        return ConversationSummary(
            id=existing.id,
            conversation_type=existing.conversation_type,
            participant=UserResponse.model_validate(target_user),
            last_message=None,
            last_message_at=existing.last_message_at,
            is_pinned=member.is_pinned,
            unread_count=0,
        )

    conversation = Conversation(conversation_type="direct")
    db.add(conversation)
    await db.flush()

    db.add_all(
        [
            ConversationMember(conversation_id=conversation.id, user_id=current_user_id),
            ConversationMember(conversation_id=conversation.id, user_id=request.user_id),
        ]
    )
    await db.flush()

    return ConversationSummary(
        id=conversation.id,
        conversation_type=conversation.conversation_type,
        participant=UserResponse.model_validate(target_user),
        last_message=None,
        last_message_at=conversation.last_message_at,
        is_pinned=False,
        unread_count=0,
    )


@router.patch("/{conversation_id}/pin", status_code=status.HTTP_204_NO_CONTENT)
async def update_pin_state(
    conversation_id: UUID,
    request: ConversationPinRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Pin or unpin conversation for current user."""
    await _get_membership_or_404(conversation_id, current_user_id, db)
    await db.execute(
        update(ConversationMember)
        .where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == current_user_id,
        )
        .values(is_pinned=request.is_pinned)
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove current user from conversation; clean up if empty."""
    member = await _get_membership_or_404(conversation_id, current_user_id, db)
    await db.delete(member)
    await db.flush()

    remaining_result = await db.execute(
        select(func.count(ConversationMember.id)).where(
            ConversationMember.conversation_id == conversation_id
        )
    )
    remaining = remaining_result.scalar() or 0
    if remaining == 0:
        await db.execute(delete(Conversation).where(Conversation.id == conversation_id))


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def list_messages(
    conversation_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MessageListResponse:
    """Get messages in a conversation."""
    await _get_membership_or_404(conversation_id, current_user_id, db)

    total_result = await db.execute(
        select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    messages = result.scalars().all()

    items = [await _message_to_response(message, db) for message in messages]
    return MessageListResponse(
        items=items,
        total=total,
        has_more=offset + len(items) < total,
    )


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=201)
async def send_message(
    conversation_id: UUID,
    request: MessageCreateRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Send a message in a conversation."""
    await _get_membership_or_404(conversation_id, current_user_id, db)
    if request.message_type == "text" and not request.content_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content_text is required")

    message = Message(
        conversation_id=conversation_id,
        sender_id=current_user_id,
        message_type=request.message_type,
        content_text=request.content_text,
        meta=request.meta,
    )
    db.add(message)
    await db.flush()

    for index, attachment in enumerate(request.attachments):
        db.add(
            MessageAttachment(
                message_id=message.id,
                file_url=attachment.file_url,
                file_name=attachment.file_name,
                file_size=attachment.file_size,
                mime_type=attachment.mime_type,
                sort_order=index,
            )
        )

    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(last_message_id=message.id, last_message_at=message.created_at)
    )
    await db.flush()
    return await _message_to_response(message, db)


@router.post("/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_conversation_read(
    conversation_id: UUID,
    request: ConversationReadRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Mark conversation as read for current user."""
    await _get_membership_or_404(conversation_id, current_user_id, db)
    target_message_id = request.last_read_message_id
    if target_message_id is None:
        latest_result = await db.execute(
            select(Message.id)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        target_message_id = latest_result.scalar_one_or_none()

    await db.execute(
        update(ConversationMember)
        .where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == current_user_id,
        )
        .values(last_read_message_id=target_message_id)
    )
