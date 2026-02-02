"""Discover service with geo-spatial queries and location obfuscation."""

import math
import random
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from geoalchemy2.functions import ST_MakeEnvelope, ST_MakePoint, ST_SetSRID, ST_X, ST_Y
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.post import Post
from app.models.user import User
from app.schemas.post import LocationPoint, PostDiscoverRequest, PostDiscoverResponse, PostResponse


class DiscoverService:
    """Service for discover/feed operations with geo-spatial queries."""

    # Scoring weights
    WEIGHT_LIKES = 0.3
    WEIGHT_COMMENTS = 0.2
    WEIGHT_RECENCY = 0.5

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_posts_in_viewport(
        self,
        request: PostDiscoverRequest,
        current_user_id: Optional[UUID] = None,
    ) -> PostDiscoverResponse:
        """
        Get posts within the specified viewport.

        Uses PostGIS ST_MakeEnvelope for efficient spatial queries.
        """
        # Create bounding box envelope
        envelope = ST_MakeEnvelope(
            request.min_longitude,
            request.min_latitude,
            request.max_longitude,
            request.max_latitude,
            4326,  # SRID
        )

        # Build query with scoring
        query = (
            select(Post)
            .where(Post.location.ST_Within(envelope))
            .options(selectinload(Post.author))
        )

        # Count total
        count_query = (
            select(func.count(Post.id))
            .where(Post.location.ST_Within(envelope))
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply scoring and ordering
        # Score = likes * 0.3 + comments * 0.2 + recency * 0.5
        # Recency = 1 / (1 + hours_since_post)
        hours_since = func.extract(
            "epoch",
            func.now() - Post.created_at
        ) / 3600

        score = (
            Post.likes_count * self.WEIGHT_LIKES +
            Post.comments_count * self.WEIGHT_COMMENTS +
            (1.0 / (1.0 + hours_since)) * self.WEIGHT_RECENCY
        )

        query = query.order_by(score.desc())
        query = query.offset(request.offset).limit(request.limit)

        result = await self.db.execute(query)
        posts = result.scalars().all()

        # Convert to response with location obfuscation
        post_responses = []
        for post in posts:
            post_response = await self._post_to_response(
                post, current_user_id
            )
            post_responses.append(post_response)

        return PostDiscoverResponse(
            posts=post_responses,
            total=total,
            has_more=request.offset + len(posts) < total,
        )

    async def create_post(
        self,
        author_id: UUID,
        content_text: str,
        location: LocationPoint,
        media_urls: Optional[list[str]] = None,
        address_name: Optional[str] = None,
    ) -> Post:
        """Create a new post with geo location."""
        # Create PostGIS point
        point = ST_SetSRID(
            ST_MakePoint(location.longitude, location.latitude),
            4326,
        )

        post = Post(
            author_id=author_id,
            content_text=content_text,
            media_urls=media_urls or [],
            location=point,
            address_name=address_name,
        )
        self.db.add(post)
        await self.db.flush()
        await self.db.refresh(post)
        return post

    async def get_post_by_id(
        self,
        post_id: UUID,
        current_user_id: Optional[UUID] = None,
    ) -> Optional[PostResponse]:
        """Get post by ID with optional location obfuscation."""
        result = await self.db.execute(
            select(Post)
            .where(Post.id == post_id)
            .options(selectinload(Post.author))
        )
        post = result.scalar_one_or_none()

        if not post:
            return None

        return await self._post_to_response(post, current_user_id)

    async def delete_post(self, post_id: UUID, user_id: UUID) -> bool:
        """Delete a post (only by author)."""
        result = await self.db.execute(
            select(Post).where(Post.id == post_id, Post.author_id == user_id)
        )
        post = result.scalar_one_or_none()

        if not post:
            return False

        await self.db.delete(post)
        return True

    async def _post_to_response(
        self,
        post: Post,
        current_user_id: Optional[UUID] = None,
    ) -> PostResponse:
        """
        Convert Post model to PostResponse with location obfuscation.

        Location is obfuscated if:
        - Current user is not the author
        - Current user is not following the author (TODO: implement following)
        """
        # Extract coordinates from PostGIS geometry
        coords_query = select(
            ST_X(post.location).label("longitude"),
            ST_Y(post.location).label("latitude"),
        )
        coords_result = await self.db.execute(coords_query)
        coords = coords_result.one()

        lat = coords.latitude
        lng = coords.longitude

        # Apply obfuscation if not author
        should_obfuscate = (
            current_user_id is None or
            current_user_id != post.author_id
        )

        if should_obfuscate:
            lat, lng = self._obfuscate_location(lat, lng)

        return PostResponse(
            id=post.id,
            author_id=post.author_id,
            content_text=post.content_text,
            media_urls=post.media_urls,
            location=LocationPoint(latitude=lat, longitude=lng),
            address_name=post.address_name,
            created_at=post.created_at,
            likes_count=post.likes_count,
            comments_count=post.comments_count,
            author=post.author,
        )

    def _obfuscate_location(
        self,
        latitude: float,
        longitude: float,
    ) -> tuple[float, float]:
        """
        Apply random offset to location coordinates.

        Adds ±LOCATION_FUZZY_METERS random offset.
        """
        fuzzy_meters = settings.location_fuzzy_meters

        # Convert meters to approximate degrees
        # 1 degree latitude ≈ 111,000 meters
        # 1 degree longitude varies with latitude
        lat_offset_degrees = fuzzy_meters / 111000
        lng_offset_degrees = fuzzy_meters / (111000 * math.cos(math.radians(latitude)))

        # Apply random offset
        new_lat = latitude + random.uniform(-lat_offset_degrees, lat_offset_degrees)
        new_lng = longitude + random.uniform(-lng_offset_degrees, lng_offset_degrees)

        # Clamp to valid ranges
        new_lat = max(-90, min(90, new_lat))
        new_lng = max(-180, min(180, new_lng))

        return new_lat, new_lng
