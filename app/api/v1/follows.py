"""Follow relationship routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.core.database import get_db
from app.models.follow import Follow
from app.models.user import User
from app.schemas.follow import FollowActionResponse, FollowListResponse
from app.schemas.user import UserResponse

router = APIRouter()


async def _get_user_or_404(user_id: UUID, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put("/{user_id}/follow", response_model=FollowActionResponse)
async def follow_user(
    user_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> FollowActionResponse:
    """Follow a user (idempotent)."""
    if user_id == current_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot follow yourself")

    await _get_user_or_404(user_id, db)
    existing_result = await db.execute(
        select(Follow).where(
            Follow.follower_id == current_user_id,
            Follow.followee_id == user_id,
        )
    )
    if existing_result.scalar_one_or_none():
        return FollowActionResponse(following=True)

    db.add(Follow(follower_id=current_user_id, followee_id=user_id))
    await db.flush()
    return FollowActionResponse(following=True)


@router.delete("/{user_id}/follow", response_model=FollowActionResponse)
async def unfollow_user(
    user_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> FollowActionResponse:
    """Unfollow a user (idempotent)."""
    existing_result = await db.execute(
        select(Follow).where(
            Follow.follower_id == current_user_id,
            Follow.followee_id == user_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if not existing:
        return FollowActionResponse(following=False)

    await db.delete(existing)
    await db.flush()
    return FollowActionResponse(following=False)


@router.get("/{user_id}/followers", response_model=FollowListResponse)
async def get_followers(
    user_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> FollowListResponse:
    """Get follower list for a user."""
    await _get_user_or_404(user_id, db)

    total_result = await db.execute(
        select(func.count(Follow.id)).where(Follow.followee_id == user_id)
    )
    total = total_result.scalar() or 0

    users_result = await db.execute(
        select(User)
        .join(Follow, Follow.follower_id == User.id)
        .where(Follow.followee_id == user_id)
        .order_by(Follow.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    users = users_result.scalars().all()
    return FollowListResponse(
        users=[UserResponse.model_validate(user) for user in users],
        total=total,
        has_more=offset + len(users) < total,
    )


@router.get("/{user_id}/following", response_model=FollowListResponse)
async def get_following(
    user_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> FollowListResponse:
    """Get following list for a user."""
    await _get_user_or_404(user_id, db)

    total_result = await db.execute(
        select(func.count(Follow.id)).where(Follow.follower_id == user_id)
    )
    total = total_result.scalar() or 0

    users_result = await db.execute(
        select(User)
        .join(Follow, Follow.followee_id == User.id)
        .where(Follow.follower_id == user_id)
        .order_by(Follow.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    users = users_result.scalars().all()
    return FollowListResponse(
        users=[UserResponse.model_validate(user) for user in users],
        total=total,
        has_more=offset + len(users) < total,
    )

