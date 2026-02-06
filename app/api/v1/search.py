"""Global search routes."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id_optional
from app.core.database import get_db
from app.models.post import Post
from app.models.user import User
from app.schemas.search import GlobalSearchResponse
from app.schemas.user import UserResponse
from app.services.discover import DiscoverService

router = APIRouter()


@router.get("/global", response_model=GlobalSearchResponse)
async def global_search(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    current_user_id: Optional[UUID] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
) -> GlobalSearchResponse:
    """Search users and posts by keyword."""
    like_query = f"%{q}%"

    users_result = await db.execute(
        select(User)
        .where(User.username.ilike(like_query))
        .order_by(User.created_at.desc())
        .limit(limit)
    )
    users = users_result.scalars().all()

    posts_result = await db.execute(
        select(Post)
        .where(
            or_(
                Post.content_text.ilike(like_query),
                Post.address_name.ilike(like_query),
                Post.title.ilike(like_query),
            )
        )
        .order_by(Post.created_at.desc())
        .limit(limit)
    )
    posts = posts_result.scalars().all()
    discover_service = DiscoverService(db)

    return GlobalSearchResponse(
        users=[UserResponse.model_validate(user) for user in users],
        posts=[
            await discover_service._post_to_response(post, current_user_id)
            for post in posts
        ],
    )

