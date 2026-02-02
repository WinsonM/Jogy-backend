"""Pydantic schemas module."""

from app.schemas.comment import (
    CommentCreate,
    CommentResponse,
    CommentTreeResponse,
)
from app.schemas.like import LikeResponse, LikeToggleResponse
from app.schemas.location import LocationSyncRequest, LocationSyncResponse
from app.schemas.post import (
    PostCreate,
    PostDiscoverRequest,
    PostDiscoverResponse,
    PostResponse,
)
from app.schemas.user import (
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)

__all__ = [
    # User
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "UserUpdate",
    "TokenResponse",
    # Post
    "PostCreate",
    "PostResponse",
    "PostDiscoverRequest",
    "PostDiscoverResponse",
    # Comment
    "CommentCreate",
    "CommentResponse",
    "CommentTreeResponse",
    # Like
    "LikeResponse",
    "LikeToggleResponse",
    # Location
    "LocationSyncRequest",
    "LocationSyncResponse",
]
