"""API v1 module."""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    comment_likes,
    comments,
    conversations,
    favorites,
    follows,
    history,
    likes,
    location,
    posts,
    qr,
    search,
    users,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(follows.router, prefix="/users", tags=["follows"])
api_router.include_router(history.router, prefix="/users", tags=["history"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
api_router.include_router(comments.router, prefix="/posts", tags=["comments"])
api_router.include_router(likes.router, prefix="/posts", tags=["likes"])
api_router.include_router(favorites.router, prefix="/posts", tags=["favorites"])
api_router.include_router(comment_likes.router, prefix="/comments", tags=["comment_likes"])
api_router.include_router(location.router, prefix="/location", tags=["location"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(qr.router, prefix="/qr", tags=["qr"])
