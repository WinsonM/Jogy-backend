"""Post favorite routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.core.database import get_db
from app.models.post import Post
from app.models.post_favorite import PostFavorite
from app.schemas.favorite import FavoriteToggleResponse

router = APIRouter()


async def _get_post_or_404(post_id: UUID, db: AsyncSession) -> Post:
    post_result = await db.execute(select(Post).where(Post.id == post_id))
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


async def _get_existing_favorite(
    post_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> PostFavorite | None:
    result = await db.execute(
        select(PostFavorite).where(
            PostFavorite.post_id == post_id,
            PostFavorite.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _create_favorite(
    post: Post,
    user_id: UUID,
    db: AsyncSession,
) -> FavoriteToggleResponse:
    db.add(PostFavorite(user_id=user_id, post_id=post.id))
    await db.execute(
        update(Post)
        .where(Post.id == post.id)
        .values(favorites_count=Post.favorites_count + 1)
    )
    await db.flush()
    return FavoriteToggleResponse(
        favorited=True,
        favorites_count=post.favorites_count + 1,
    )


async def _delete_favorite(
    post: Post,
    favorite: PostFavorite,
    db: AsyncSession,
) -> FavoriteToggleResponse:
    await db.delete(favorite)
    await db.execute(
        update(Post)
        .where(Post.id == post.id)
        .values(favorites_count=Post.favorites_count - 1)
    )
    await db.flush()
    return FavoriteToggleResponse(
        favorited=False,
        favorites_count=max(post.favorites_count - 1, 0),
    )


@router.post("/{post_id}/favorite", response_model=FavoriteToggleResponse)
async def toggle_favorite(
    post_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> FavoriteToggleResponse:
    """Toggle favorite on a post."""
    post = await _get_post_or_404(post_id, db)
    existing = await _get_existing_favorite(post_id, current_user_id, db)
    if existing:
        return await _delete_favorite(post, existing, db)
    return await _create_favorite(post, current_user_id, db)


@router.put("/{post_id}/favorites/me", response_model=FavoriteToggleResponse)
async def favorite_post(
    post_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> FavoriteToggleResponse:
    """Favorite a post (idempotent)."""
    post = await _get_post_or_404(post_id, db)
    existing = await _get_existing_favorite(post_id, current_user_id, db)
    if existing:
        return FavoriteToggleResponse(
            favorited=True,
            favorites_count=post.favorites_count,
        )
    return await _create_favorite(post, current_user_id, db)


@router.delete("/{post_id}/favorites/me", response_model=FavoriteToggleResponse)
async def unfavorite_post(
    post_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> FavoriteToggleResponse:
    """Unfavorite a post (idempotent)."""
    post = await _get_post_or_404(post_id, db)
    existing = await _get_existing_favorite(post_id, current_user_id, db)
    if not existing:
        return FavoriteToggleResponse(
            favorited=False,
            favorites_count=post.favorites_count,
        )
    return await _delete_favorite(post, existing, db)

