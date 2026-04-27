"""Jogy App Backend - FastAPI Application."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.core.config import settings
from app.core.middleware import RateLimitMiddleware, SignatureMiddleware
from app.core.redis import close_redis_pool
from app.services.cleanup import delete_expired_posts

logger = logging.getLogger(__name__)


async def _run_cleanup_once() -> None:
    try:
        deleted = await delete_expired_posts()
        if deleted > 0:
            logger.info("[cleanup] deleted %d expired posts", deleted)
    except Exception:
        logger.exception("[cleanup] failed")


async def _cleanup_loop() -> None:
    await _run_cleanup_once()
    while True:
        await asyncio.sleep(60 * 60)
        await _run_cleanup_once()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    cleanup_task = asyncio.create_task(_cleanup_loop(), name="cleanup_expired_posts")
    logger.info("[startup] cleanup task started (interval=1h)")
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        await close_redis_pool()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Jogy App Backend - A geo-social application",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware — each has its own toggle in settings
# SignatureMiddleware is off by default until the Flutter app implements signing
if settings.signature_middleware_enabled:
    app.add_middleware(SignatureMiddleware, enabled=True)
if settings.rate_limit_middleware_enabled and not settings.debug:
    app.add_middleware(RateLimitMiddleware, enabled=True)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

os.makedirs("uploads/images", exist_ok=True)
os.makedirs("uploads/thumbnails", exist_ok=True)
os.makedirs("uploads/files", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}
