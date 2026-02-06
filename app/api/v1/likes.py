"""Like routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.core.database import get_db
from app.models.like import Like
from app.models.post import Post
from app.schemas.like import LikeToggleResponse

router = APIRouter()


async def _get_post_or_404(post_id: UUID, db: AsyncSession) -> Post:
    post_result = await db.execute(select(Post).where(Post.id == post_id))
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    return post


async def _get_existing_like(
    post_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Like | None:
    like_result = await db.execute(
        select(Like).where(
            Like.user_id == user_id,
            Like.post_id == post_id,
        )
    )
    return like_result.scalar_one_or_none()


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
    post = await _get_post_or_404(post_id, db)

    existing_like = await _get_existing_like(post_id, current_user_id, db)

    if existing_like:
        return await _delete_like(post, existing_like, db)
    return await _create_like(post, current_user_id, db)


async def _create_like(post: Post, user_id: UUID, db: AsyncSession) -> LikeToggleResponse:
    new_like = Like(user_id=user_id, post_id=post.id)
    db.add(new_like)
    await db.execute(
        update(Post)
        .where(Post.id == post.id)
        .values(likes_count=Post.likes_count + 1)
    )
    await db.flush()
    return LikeToggleResponse(liked=True, likes_count=post.likes_count + 1)


async def _delete_like(post: Post, like: Like, db: AsyncSession) -> LikeToggleResponse:
    await db.delete(like)
    await db.execute(
        update(Post)
        .where(Post.id == post.id)
        .values(likes_count=Post.likes_count - 1)
    )
    await db.flush()
    return LikeToggleResponse(liked=False, likes_count=max(post.likes_count - 1, 0))


@router.put("/{post_id}/likes/me", response_model=LikeToggleResponse)
async def like_post(
    post_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> LikeToggleResponse:
    """Like a post (idempotent)."""
    post = await _get_post_or_404(post_id, db)
    existing_like = await _get_existing_like(post_id, current_user_id, db)
    if existing_like:
        return LikeToggleResponse(liked=True, likes_count=post.likes_count)
    return await _create_like(post, current_user_id, db)


@router.delete("/{post_id}/likes/me", response_model=LikeToggleResponse)
async def unlike_post(
    post_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> LikeToggleResponse:
    """Unlike a post (idempotent)."""
    post = await _get_post_or_404(post_id, db)
    existing_like = await _get_existing_like(post_id, current_user_id, db)
    if not existing_like:
        return LikeToggleResponse(liked=False, likes_count=post.likes_count)
    return await _delete_like(post, existing_like, db)
