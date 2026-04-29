"""Comment routes with tree structure support."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_current_user_id_optional
from app.core.database import get_db
from app.schemas.comment import (
    CommentCreate,
    CommentListResponse,
    CommentResponse,
)
from app.services.comment import CommentService

router = APIRouter()


@router.post(
    "/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    post_id: UUID,
    comment_data: CommentCreate,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    """Create a comment or reply on a post."""
    comment_service = CommentService(db)
    try:
        comment = await comment_service.create_comment(
            post_id=post_id,
            user_id=current_user_id,
            data=comment_data,
        )
        comment = await comment_service.get_comment_by_id(comment.id)
        if comment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found",
            )
        return CommentResponse(
            id=comment.id,
            post_id=comment.post_id,
            user_id=comment.user_id,
            content=comment.content,
            parent_id=comment.parent_id,
            root_id=comment.root_id,
            reply_to_user_id=comment.reply_to_user_id,
            reply_to_username=comment.reply_to_user.username if comment.reply_to_user else None,
            created_at=comment.created_at,
            replies_count=comment.replies_count,
            likes_count=comment.likes_count,
            user=comment.user,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/{post_id}/comments", response_model=CommentListResponse)
async def get_comments(
    post_id: UUID,
    parent_id: Optional[UUID] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user_id: Optional[UUID] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
) -> CommentListResponse:
    """
    Get comments for a post.

    If parent_id is None, returns root-level comments with top 2 replies each.
    If parent_id is provided, returns all replies in that root thread.
    """
    comment_service = CommentService(db)
    return await comment_service.get_comments(
        post_id=post_id,
        parent_id=parent_id,
        limit=limit,
        offset=offset,
        current_user_id=current_user_id,
    )


@router.delete(
    "/{post_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_comment(
    post_id: UUID,
    comment_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a comment (author only)."""
    comment_service = CommentService(db)
    deleted = await comment_service.delete_comment(comment_id, current_user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found or not authorized",
        )
