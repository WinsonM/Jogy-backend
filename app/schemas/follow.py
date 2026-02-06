"""Follow schemas."""

from pydantic import BaseModel

from app.schemas.user import UserResponse


class FollowActionResponse(BaseModel):
    """Response for follow/unfollow action."""

    following: bool


class FollowListResponse(BaseModel):
    """Response for followers/following list."""

    users: list[UserResponse]
    total: int
    has_more: bool

