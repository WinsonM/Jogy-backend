"""Like routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.core.database import get_db
from app.models.like import Like
from app.models.post import Post
from app.schemas.like import LikeToggleResponse

router = APIRouter()


@router.post("/{post_id}/like", response_model=LikeToggleResponse)
async def toggle_like(
    post_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> LikeToggleResponse:
    """
    Toggle like on a post.

    If not liked, adds a like. If already liked, removes it.
    """
    # Check post exists
    post_result = await db.execute(
        select(Post).where(Post.id == post_id)
    )
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    # Check if already liked
    like_result = await db.execute(
        select(Like).where(
            Like.user_id == current_user_id,
            Like.post_id == post_id,
        )
    )
    existing_like = like_result.scalar_one_or_none()

    if existing_like:
        # Unlike
        await db.delete(existing_like)
        await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(likes_count=Post.likes_count - 1)
        )
        await db.flush()

        return LikeToggleResponse(
            liked=False,
            likes_count=post.likes_count - 1,
        )
    else:
        # Like
        new_like = Like(
            user_id=current_user_id,
            post_id=post_id,
        )
        db.add(new_like)
        await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(likes_count=Post.likes_count + 1)
        )
        await db.flush()

        return LikeToggleResponse(
            liked=True,
            likes_count=post.likes_count + 1,
        )
