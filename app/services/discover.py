"""Discover service with geo-spatial queries and location obfuscation."""

import math

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from geoalchemy2.functions import ST_MakeEnvelope, ST_MakePoint, ST_SetSRID, ST_X, ST_Y
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.post import Post
from app.models.user import User
from app.schemas.post import LocationPoint, PostDiscoverRequest, PostDiscoverResponse, PostResponse


class DiscoverService:
    """Service for discover/feed operations with geo-spatial queries."""

    # Scoring weights (Gravity Model)
    FACTOR_LIKES = 1.0      # A
    FACTOR_COMMENTS = 2.0   # B
    EXP_DISTANCE = 1.5      # C
    EXP_TIME = 1.2          # Time Decay Power

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
        # Validate and expand viewport
        # Calculate width/height
        lat_diff = request.max_latitude - request.min_latitude
        lng_diff = request.max_longitude - request.min_longitude
        
        # Calculate center point
        center_lat = (request.min_latitude + request.max_latitude) / 2
        center_lng = (request.min_longitude + request.max_longitude) / 2
        
        # Expand by 15% buffer
        lat_buffer = lat_diff * 0.15
        lng_buffer = lng_diff * 0.15
        
        expanded_min_lat = max(-90, request.min_latitude - lat_buffer)
        expanded_max_lat = min(90, request.max_latitude + lat_buffer)
        expanded_min_lng = max(-180, request.min_longitude - lng_buffer)
        expanded_max_lng = min(180, request.max_longitude + lng_buffer)

        # Create bounding box envelope with expanded bounds
        envelope = ST_MakeEnvelope(
            expanded_min_lng,
            expanded_min_lat,
            expanded_max_lng,
            expanded_max_lat,
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

        # Apply scoring (Gravity Model)
        # Formula: (Likes * A + Comments * B + 1) / ( (DistanceKM + 1)^C * (AgeHours + 2)^1.2 )
        
        # 1. Age in hours
        hours_since = func.extract("epoch", func.now() - Post.created_at) / 3600
        
        # 2. Distance in KM (Approx 111km per degree)
        center_point = ST_SetSRID(ST_MakePoint(center_lng, center_lat), 4326)
        distance_degrees = func.ST_Distance(Post.location, center_point)
        distance_km = distance_degrees * 111.0 

        # 3. Calculate Score
        numerator = (
            Post.likes_count * self.FACTOR_LIKES +
            Post.comments_count * self.FACTOR_COMMENTS + 
            1.0  # Base score to ensure new posts have visibility
        )
        
        denominator = (
            func.power(distance_km + 1, self.EXP_DISTANCE) * 
            func.power(hours_since + 2, self.EXP_TIME)
        )

        score = numerator / denominator

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
        Convert Post model to PostResponse.
        
        Returns precise location as requested.
        """
        # Extract coordinates from PostGIS geometry
        coords_query = select(
            ST_X(post.location).label("longitude"),
            ST_Y(post.location).label("latitude"),
        )
        coords_result = await self.db.execute(coords_query)
        coords = coords_result.one()

        return PostResponse(
            id=post.id,
            author_id=post.author_id,
            content_text=post.content_text,
            media_urls=post.media_urls,
            location=LocationPoint(latitude=coords.latitude, longitude=coords.longitude),
            address_name=post.address_name,
            created_at=post.created_at,
            likes_count=post.likes_count,
            comments_count=post.comments_count,
            author=post.author,
        )

