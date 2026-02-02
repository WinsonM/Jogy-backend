"""API v1 module."""

from fastapi import APIRouter

from app.api.v1 import auth, comments, likes, location, posts, users

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
api_router.include_router(comments.router, prefix="/posts", tags=["comments"])
api_router.include_router(likes.router, prefix="/posts", tags=["likes"])
api_router.include_router(location.router, prefix="/location", tags=["location"])
