"""Redis connection and utilities."""

from typing import Optional

import redis.asyncio as redis
from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

# Connection pool
_pool: Optional[ConnectionPool] = None


async def get_redis_pool() -> ConnectionPool:
    """Get or create Redis connection pool."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
        )
    return _pool


async def get_redis() -> Redis:
    """Get Redis client."""
    pool = await get_redis_pool()
    return Redis(connection_pool=pool)


async def close_redis_pool() -> None:
    """Close Redis connection pool."""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None


class RedisClient:
    """Redis client wrapper with geo and rate limiting utilities."""

    def __init__(self, client: Redis):
        self.client = client

    # ==================== Geo Operations ====================

    async def geo_add(
        self,
        key: str,
        longitude: float,
        latitude: float,
        member: str,
    ) -> int:
        """Add a member with geo coordinates."""
        return await self.client.geoadd(key, (longitude, latitude, member))

    async def geo_radius(
        self,
        key: str,
        longitude: float,
        latitude: float,
        radius: float,
        unit: str = "m",
        count: Optional[int] = None,
        sort: Optional[str] = None,
    ) -> list:
        """Get members within radius."""
        return await self.client.georadius(
            key,
            longitude,
            latitude,
            radius,
            unit=unit,
            count=count,
            sort=sort,
            withcoord=True,
            withdist=True,
        )

    async def geo_pos(self, key: str, member: str) -> Optional[tuple]:
        """Get position of a member."""
        result = await self.client.geopos(key, member)
        return result[0] if result and result[0] else None

    # ==================== Rate Limiting (Token Bucket) ====================

    async def check_rate_limit(
        self,
        key: str,
        max_tokens: int,
        refill_rate: float,
        tokens_to_consume: int = 1,
    ) -> tuple[bool, int]:
        """
        Check and consume tokens from rate limiter.

        Args:
            key: Rate limit key (e.g., "rate:discover:user_id")
            max_tokens: Maximum tokens in bucket
            refill_rate: Tokens added per second
            tokens_to_consume: Tokens to consume for this request

        Returns:
            Tuple of (allowed: bool, remaining_tokens: int)
        """
        import time

        now = time.time()
        bucket_key = f"bucket:{key}"

        # Lua script for atomic token bucket operation
        lua_script = """
        local bucket_key = KEYS[1]
        local max_tokens = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local tokens_to_consume = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])

        local bucket = redis.call('HMGET', bucket_key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket[1]) or max_tokens
        local last_refill = tonumber(bucket[2]) or now

        -- Calculate tokens to add based on time elapsed
        local elapsed = now - last_refill
        local tokens_to_add = elapsed * refill_rate
        tokens = math.min(max_tokens, tokens + tokens_to_add)

        -- Check if we can consume
        local allowed = 0
        if tokens >= tokens_to_consume then
            tokens = tokens - tokens_to_consume
            allowed = 1
        end

        -- Update bucket
        redis.call('HMSET', bucket_key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', bucket_key, 3600)  -- Expire after 1 hour of inactivity

        return {allowed, math.floor(tokens)}
        """

        result = await self.client.eval(
            lua_script,
            1,
            bucket_key,
            max_tokens,
            refill_rate,
            tokens_to_consume,
            now,
        )
        return bool(result[0]), int(result[1])

    # ==================== Caching ====================

    async def set_cache(
        self,
        key: str,
        value: str,
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """Set a cache value."""
        if expire_seconds:
            return await self.client.setex(key, expire_seconds, value)
        return await self.client.set(key, value)

    async def get_cache(self, key: str) -> Optional[str]:
        """Get a cache value."""
        return await self.client.get(key)

    async def delete_cache(self, key: str) -> int:
        """Delete a cache key."""
        return await self.client.delete(key)


async def get_redis_client() -> RedisClient:
    """Get Redis client wrapper."""
    client = await get_redis()
    return RedisClient(client)
