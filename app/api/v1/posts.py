"""Post routes including discover endpoint."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_current_user_id, get_current_user_id_optional
from app.core.database import get_db
from app.models.post import Post
from app.models.user import User
from app.schemas.post import (
    PostCreate,
    PostDiscoverRequest,
    PostDiscoverResponse,
    PostResponse,
    PostUpdate,
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
        title=post_data.title,
        post_type=post_data.post_type,
        media_urls=post_data.media_urls,
        address_name=post_data.address_name,
        expire_at=post_data.expire_at,
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


@router.get("/search", response_model=list[PostResponse])
async def search_posts(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    current_user_id: Optional[UUID] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
) -> list[PostResponse]:
    """Search posts by content, title, or address."""
    like_query = f"%{q}%"
    # selectinload(Post.author) — _post_to_response_fast accesses post.author;
    # async SQLAlchemy 不允许隐式 lazy load。
    result = await db.execute(
        select(Post)
        .where(
            or_(
                Post.content_text.ilike(like_query),
                Post.title.ilike(like_query),
                Post.address_name.ilike(like_query),
            )
        )
        .order_by(Post.created_at.desc())
        .limit(limit)
        .options(selectinload(Post.author))
    )
    posts = result.scalars().all()
    discover_service = DiscoverService(db)
    return [await discover_service._post_to_response(post, current_user_id) for post in posts]


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


@router.patch("/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: UUID,
    post_update: PostUpdate,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PostResponse:
    """Update a post (author only) — partial update.

    Editable fields: title / content_text / address_name / expire_at.
    Non-editable fields (location / media_urls / post_type) require a
    full re-publish to avoid corrupting feed history.
    """
    # Verify ownership before any mutation
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.author_id == current_user_id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or not authorized",
        )

    # Apply only fields explicitly set in the request body
    update_data = post_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(post, key, value)

    await db.flush()
    await db.refresh(post)

    discover_service = DiscoverService(db)
    response = await discover_service.get_post_by_id(post.id, current_user_id)
    if response is None:
        # Shouldn't happen — we just refreshed. Defensive guard.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load updated post",
        )
    return response


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
