"""Pydantic schemas module."""

from app.schemas.comment import (
    CommentCreate,
    CommentResponse,
    CommentTreeResponse,
)
from app.schemas.chat import (
    ConversationDirectCreateRequest,
    ConversationListResponse,
    ConversationPinRequest,
    ConversationReadRequest,
    ConversationSummary,
    MessageCreateRequest,
    MessageListResponse,
    MessageResponse,
)
from app.schemas.favorite import FavoriteToggleResponse
from app.schemas.follow import FollowActionResponse, FollowListResponse
from app.schemas.history import (
    HistoryCreateRequest,
    HistoryItemResponse,
    HistoryListResponse,
)
from app.schemas.like import LikeResponse, LikeToggleResponse
from app.schemas.location import LocationSyncRequest, LocationSyncResponse
from app.schemas.post import (
    PostCreate,
    PostDiscoverRequest,
    PostDiscoverResponse,
    PostResponse,
)
from app.schemas.qr import MyQRCodeResponse, QRResolveRequest, QRResolveResponse
from app.schemas.search import GlobalSearchResponse
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
    # Chat
    "ConversationDirectCreateRequest",
    "ConversationPinRequest",
    "ConversationReadRequest",
    "ConversationSummary",
    "ConversationListResponse",
    "MessageCreateRequest",
    "MessageResponse",
    "MessageListResponse",
    # Like
    "LikeResponse",
    "LikeToggleResponse",
    "FavoriteToggleResponse",
    # Follow
    "FollowActionResponse",
    "FollowListResponse",
    # History
    "HistoryCreateRequest",
    "HistoryItemResponse",
    "HistoryListResponse",
    # Location
    "LocationSyncRequest",
    "LocationSyncResponse",
    # Search
    "GlobalSearchResponse",
    # QR
    "MyQRCodeResponse",
    "QRResolveRequest",
    "QRResolveResponse",
]
