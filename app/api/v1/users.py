"""User routes."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    result = await db.execute(
        select(Post).where(Post.author_id == user_id).order_by(Post.created_at.desc())
    )
    posts = result.scalars().all()
    discover_service = DiscoverService(db)
    return [await discover_service._post_to_response(post, current_user_id) for post in posts]


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
        .order_by(Like.created_at.desc())
    )
    posts = result.scalars().all()
    discover_service = DiscoverService(db)
    return [await discover_service._post_to_response(post, current_user_id) for post in posts]


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
        .order_by(PostFavorite.created_at.desc())
    )
    posts = result.scalars().all()
    discover_service = DiscoverService(db)
    return [await discover_service._post_to_response(post, current_user_id) for post in posts]
