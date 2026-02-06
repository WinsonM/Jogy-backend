"""Comment like routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.core.database import get_db
from app.models.comment import Comment
from app.models.comment_like import CommentLike
from app.schemas.like import LikeToggleResponse

router = APIRouter()


async def _get_comment_or_404(comment_id: UUID, db: AsyncSession) -> Comment:
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return comment


async def _get_existing_comment_like(
    comment_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> CommentLike | None:
    result = await db.execute(
        select(CommentLike).where(
            CommentLike.comment_id == comment_id,
            CommentLike.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _create_like(
    comment: Comment,
    user_id: UUID,
    db: AsyncSession,
) -> LikeToggleResponse:
    db.add(CommentLike(user_id=user_id, comment_id=comment.id))
    await db.execute(
        update(Comment)
        .where(Comment.id == comment.id)
        .values(likes_count=Comment.likes_count + 1)
    )
    await db.flush()
    return LikeToggleResponse(liked=True, likes_count=comment.likes_count + 1)


async def _delete_like(
    comment: Comment,
    like: CommentLike,
    db: AsyncSession,
) -> LikeToggleResponse:
    await db.delete(like)
    await db.execute(
        update(Comment)
        .where(Comment.id == comment.id)
        .values(likes_count=Comment.likes_count - 1)
    )
    await db.flush()
    return LikeToggleResponse(liked=False, likes_count=max(comment.likes_count - 1, 0))


@router.put("/{comment_id}/likes/me", response_model=LikeToggleResponse)
async def like_comment(
    comment_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> LikeToggleResponse:
    """Like a comment (idempotent)."""
    comment = await _get_comment_or_404(comment_id, db)
    existing = await _get_existing_comment_like(comment_id, current_user_id, db)
    if existing:
        return LikeToggleResponse(liked=True, likes_count=comment.likes_count)
    return await _create_like(comment, current_user_id, db)


@router.delete("/{comment_id}/likes/me", response_model=LikeToggleResponse)
async def unlike_comment(
    comment_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> LikeToggleResponse:
    """Unlike a comment (idempotent)."""
    comment = await _get_comment_or_404(comment_id, db)
    existing = await _get_existing_comment_like(comment_id, current_user_id, db)
    if not existing:
        return LikeToggleResponse(liked=False, likes_count=comment.likes_count)
    return await _delete_like(comment, existing, db)

