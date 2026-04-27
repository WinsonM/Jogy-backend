"""User routes."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_current_user_id_optional
from app.core.database import get_db
from app.models.like import Like
from app.models.post import Post
from app.models.post_favorite import PostFavorite
from app.models.user import User
from app.schemas.post import PostResponse
from app.schemas.qr import MyQRCodeResponse
from app.schemas.user import UserResponse, UserUpdate
from app.services.discover import DiscoverService

router = APIRouter()


def _active_post_filter():
    return (Post.expire_at.is_(None)) | (Post.expire_at > func.now())


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get current user's profile."""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update current user's profile."""
    update_data = user_update.model_dump(exclude_unset=True)

    if not update_data:
        return UserResponse.model_validate(current_user)

    # Check username uniqueness if updating
    if "username" in update_data:
        existing = await db.execute(
            select(User).where(
                User.username == update_data["username"],
                User.id != current_user.id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

    # Update user
    for key, value in update_data.items():
        setattr(current_user, key, value)

    await db.flush()
    await db.refresh(current_user)

    return UserResponse.model_validate(current_user)


@router.get("/me/qr", response_model=MyQRCodeResponse)
async def get_my_qr(
    current_user: User = Depends(get_current_user),
) -> MyQRCodeResponse:
    """Get current user's profile QR payload."""
    return MyQRCodeResponse(qr_data=f"jogy://user/profile/{current_user.id}")


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_profile(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Get public profile by user id."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.model_validate(user)


@router.get("/{user_id}/posts", response_model=list[PostResponse])
async def get_user_posts(
    user_id: UUID,
    current_user_id: Optional[UUID] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
) -> list[PostResponse]:
    """Get posts created by user."""
    # selectinload(Post.author) is REQUIRED — _batch_posts_to_response →
    # _post_to_response_fast accesses post.author. Async SQLAlchemy disallows
    # implicit lazy loading on a relationship; without eager load this raises
    # MissingGreenlet → 500 → frontend Future.wait fails → profile shows empty.
    result = await db.execute(
        select(Post)
        .where(Post.author_id == user_id)
        .where(_active_post_filter())
        .order_by(Post.created_at.desc())
        .options(selectinload(Post.author))
    )
    posts = result.scalars().all()
    return await _batch_posts_to_response(db, posts, current_user_id)


@router.get("/{user_id}/liked-posts", response_model=list[PostResponse])
async def get_user_liked_posts(
    user_id: UUID,
    current_user_id: Optional[UUID] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
) -> list[PostResponse]:
    """Get posts liked by user."""
    result = await db.execute(
        select(Post)
        .join(Like, Like.post_id == Post.id)
        .where(Like.user_id == user_id)
        .where(_active_post_filter())
        .order_by(Like.created_at.desc())
        .options(selectinload(Post.author))
    )
    posts = result.scalars().all()
    return await _batch_posts_to_response(db, posts, current_user_id)


@router.get("/{user_id}/favorited-posts", response_model=list[PostResponse])
async def get_user_favorited_posts(
    user_id: UUID,
    current_user_id: Optional[UUID] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
) -> list[PostResponse]:
    """Get posts favorited by user."""
    result = await db.execute(
        select(Post)
        .join(PostFavorite, PostFavorite.post_id == Post.id)
        .where(PostFavorite.user_id == user_id)
        .where(_active_post_filter())
        .order_by(PostFavorite.created_at.desc())
        .options(selectinload(Post.author))
    )
    posts = result.scalars().all()
    return await _batch_posts_to_response(db, posts, current_user_id)


async def _batch_posts_to_response(
    db: AsyncSession,
    posts: list[Post],
    current_user_id: Optional[UUID],
) -> list[PostResponse]:
    """Convert posts to responses with batch isLiked/isFavorited queries (2 queries total)."""
    if not posts:
        return []

    post_ids = [p.id for p in posts]
    liked_ids: set[UUID] = set()
    favorited_ids: set[UUID] = set()

    if current_user_id:
        liked_result = await db.execute(
            select(Like.post_id).where(
                Like.user_id == current_user_id,
                Like.post_id.in_(post_ids),
            )
        )
        liked_ids = set(liked_result.scalars().all())

        favorited_result = await db.execute(
            select(PostFavorite.post_id).where(
                PostFavorite.user_id == current_user_id,
                PostFavorite.post_id.in_(post_ids),
            )
        )
        favorited_ids = set(favorited_result.scalars().all())

    discover_service = DiscoverService(db)
    return [
        discover_service._post_to_response_fast(
            post, post.id in liked_ids, post.id in favorited_ids
        )
        for post in posts
    ]
