"""Post routes including discover endpoint."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_id, get_current_user_id_optional
from app.core.database import get_db
from app.models.user import User
from app.schemas.post import (
    PostCreate,
    PostDiscoverRequest,
    PostDiscoverResponse,
    PostResponse,
)
from app.services.discover import DiscoverService

router = APIRouter()


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_data: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostResponse:
    """Create a new post."""
    discover_service = DiscoverService(db)
    post = await discover_service.create_post(
        author_id=current_user.id,
        content_text=post_data.content_text,
        location=post_data.location,
        media_urls=post_data.media_urls,
        address_name=post_data.address_name,
    )
    return await discover_service.get_post_by_id(post.id, current_user.id)


@router.get("/discover", response_model=PostDiscoverResponse)
async def discover_posts(
    min_latitude: float = Query(..., ge=-90, le=90),
    min_longitude: float = Query(..., ge=-180, le=180),
    max_latitude: float = Query(..., ge=-90, le=90),
    max_longitude: float = Query(..., ge=-180, le=180),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user_id: Optional[UUID] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
) -> PostDiscoverResponse:
    """
    Discover posts within viewport.

    This is the main feed endpoint that returns posts within the
    specified geographic bounds, sorted by relevance score.
    """
    request = PostDiscoverRequest(
        min_latitude=min_latitude,
        min_longitude=min_longitude,
        max_latitude=max_latitude,
        max_longitude=max_longitude,
        limit=limit,
        offset=offset,
    )
    discover_service = DiscoverService(db)
    return await discover_service.get_posts_in_viewport(request, current_user_id)


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: UUID,
    current_user_id: Optional[UUID] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
) -> PostResponse:
    """Get a single post by ID."""
    discover_service = DiscoverService(db)
    post = await discover_service.get_post_by_id(post_id, current_user_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a post (author only)."""
    discover_service = DiscoverService(db)
    deleted = await discover_service.delete_post(post_id, current_user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or not authorized",
        )
