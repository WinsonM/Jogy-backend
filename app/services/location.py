"""Location service for syncing user locations."""

from typing import Optional
from uuid import UUID

from app.core.redis import RedisClient, get_redis_client


# Redis key for user locations
USER_LOCATIONS_KEY = "user:locations"


class LocationService:
    """Service for location sync and nearby queries."""

    def __init__(self, redis_client: Optional[RedisClient] = None):
        self._redis_client = redis_client

    async def _get_redis(self) -> RedisClient:
        """Get Redis client."""
        if self._redis_client is None:
            self._redis_client = await get_redis_client()
        return self._redis_client

    async def sync_location(
        self,
        user_id: UUID,
        latitude: float,
        longitude: float,
    ) -> bool:
        """
        Sync user location to Redis.

        Stores precise coordinates for real-time queries.
        """
        redis = await self._get_redis()

        # Add to geo index
        await redis.geo_add(
            USER_LOCATIONS_KEY,
            longitude,
            latitude,
            str(user_id),
        )

        return True

    async def get_user_location(
        self,
        user_id: UUID,
    ) -> Optional[tuple[float, float]]:
        """Get user's last known location."""
        redis = await self._get_redis()

        result = await redis.geo_pos(USER_LOCATIONS_KEY, str(user_id))
        if result:
            # Returns (longitude, latitude)
            return (result[1], result[0])  # Return as (lat, lng)
        return None

    async def get_nearby_users(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float = 1000,
        count: Optional[int] = 50,
    ) -> list[dict]:
        """
        Get users within radius of a point.

        Returns list of {user_id, distance, latitude, longitude}.
        """
        redis = await self._get_redis()

        results = await redis.geo_radius(
            USER_LOCATIONS_KEY,
            longitude,
            latitude,
            radius_meters,
            unit="m",
            count=count,
            sort="ASC",  # Closest first
        )

        nearby = []
        for item in results:
            member = item[0]
            distance = item[1]
            coords = item[2]

            nearby.append({
                "user_id": member,
                "distance": distance,
                "longitude": coords[0],
                "latitude": coords[1],
            })

        return nearby
