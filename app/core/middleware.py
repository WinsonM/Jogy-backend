"""FastAPI middleware for security and rate limiting."""

import time
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings
from app.core.redis import get_redis_client
from app.core.security import verify_signature


class SignatureMiddleware(BaseHTTPMiddleware):
    """
    Middleware to verify API request signatures.

    Expects headers:
    - X-Signature: HMAC-SHA256 signature
    - X-Timestamp: Unix timestamp of request
    """

    # Paths that don't require signature verification.
    # Auth endpoints are exempt because they run before the user has any
    # credentials to sign with (login / register / verification codes).
    EXEMPT_PATHS = {
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/register",
        "/api/v1/auth/send-code",
        "/api/v1/auth/verify-code",
        "/api/v1/auth/refresh",
    }

    def __init__(self, app: ASGIApp, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip if disabled or exempt path
        if not self.enabled or request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Skip preflight requests
        if request.method == "OPTIONS":
            return await call_next(request)

        # Get signature headers
        signature = request.headers.get("X-Signature")
        timestamp = request.headers.get("X-Timestamp")

        if not signature or not timestamp:
            return Response(
                content='{"detail": "Missing signature headers"}',
                status_code=401,
                media_type="application/json",
            )

        # Read request body
        body = await request.body()

        # Verify signature
        if not verify_signature(body, timestamp, signature):
            return Response(
                content='{"detail": "Invalid signature"}',
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for rate limiting using Redis token bucket.

    Different limits for different endpoints.
    """

    # Rate limit configuration: path prefix -> (max_tokens, refill_rate)
    RATE_LIMITS = {
        "/api/v1/discover": ("discover", settings.rate_limit_discover),
        "/api/v1/location/sync": ("location_sync", settings.rate_limit_location_sync),
    }

    # Default rate limit for all other paths
    DEFAULT_LIMIT = ("default", 30)  # 30 requests per second

    def __init__(self, app: ASGIApp, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)

        # Skip non-API paths
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Get client identifier (user ID from JWT or IP)
        client_id = self._get_client_id(request)
        if not client_id:
            return await call_next(request)

        # Determine rate limit for this path
        limit_name, limit_rate = self._get_limit_for_path(request.url.path)

        # Check rate limit
        try:
            redis_client = await get_redis_client()
            key = f"rate:{limit_name}:{client_id}"
            allowed, remaining = await redis_client.check_rate_limit(
                key=key,
                max_tokens=limit_rate * 10,  # 10 seconds worth of tokens
                refill_rate=limit_rate,
                tokens_to_consume=1,
            )

            if not allowed:
                return Response(
                    content='{"detail": "Rate limit exceeded"}',
                    status_code=429,
                    media_type="application/json",
                    headers={
                        "X-RateLimit-Remaining": str(remaining),
                        "Retry-After": "1",
                    },
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            return response

        except Exception:
            # On Redis error, allow request to proceed
            return await call_next(request)

    def _get_client_id(self, request: Request) -> Optional[str]:
        """Get client identifier from request."""
        # Try to get user ID from request state (set by auth dependency)
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return str(user_id)

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else None

    def _get_limit_for_path(self, path: str) -> tuple[str, int]:
        """Get rate limit configuration for path."""
        for prefix, config in self.RATE_LIMITS.items():
            if path.startswith(prefix):
                return config
        return self.DEFAULT_LIMIT
