"""Browsing history routes."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user_id
from app.core.database import get_db
from app.models.browsing_history import UserBrowsingHistory
from app.models.post import Post
from app.schemas.history import HistoryCreateRequest, HistoryItemResponse, HistoryListResponse
from app.services.discover import DiscoverService

router = APIRouter()


def _active_post_filter():
    return (Post.expire_at.is_(None)) | (Post.expire_at > func.now())


@router.get("/me/history", response_model=HistoryListResponse)
async def get_my_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> HistoryListResponse:
    """Get current user's browsing history."""
    total_result = await db.execute(
        select(func.count(UserBrowsingHistory.id))
        .join(Post, Post.id == UserBrowsingHistory.post_id)
        .where(UserBrowsingHistory.user_id == current_user_id)
        .where(_active_post_filter())
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(UserBrowsingHistory)
        .join(Post, Post.id == UserBrowsingHistory.post_id)
        .where(UserBrowsingHistory.user_id == current_user_id)
        .where(_active_post_filter())
        .options(selectinload(UserBrowsingHistory.post).selectinload(Post.author))
        .order_by(UserBrowsingHistory.viewed_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = result.scalars().all()
    discover_service = DiscoverService(db)

    response_items: list[HistoryItemResponse] = []
    for item in items:
        if item.post is None:
            continue
        post_response = await discover_service._post_to_response(item.post, current_user_id)
        response_items.append(HistoryItemResponse(post=post_response, viewed_at=item.viewed_at))

    return HistoryListResponse(
        items=response_items,
        total=total,
        has_more=offset + len(response_items) < total,
    )


@router.post("/me/history", status_code=status.HTTP_204_NO_CONTENT)
async def add_my_history(
    request: HistoryCreateRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Upsert a browsing history record."""
    post_result = await db.execute(
        select(Post).where(Post.id == request.post_id).where(_active_post_filter())
    )
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    existing_result = await db.execute(
        select(UserBrowsingHistory).where(
            UserBrowsingHistory.user_id == current_user_id,
            UserBrowsingHistory.post_id == request.post_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        existing.viewed_at = datetime.now(timezone.utc)
        await db.flush()
        return

    db.add(
        UserBrowsingHistory(
            user_id=current_user_id,
            post_id=request.post_id,
            viewed_at=datetime.now(timezone.utc),
        )
    )
    await db.flush()


@router.delete("/me/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_my_history(
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Clear current user's browsing history."""
    await db.execute(
        delete(UserBrowsingHistory).where(UserBrowsingHistory.user_id == current_user_id)
    )
