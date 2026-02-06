"""Search response schemas."""

from pydantic import BaseModel

from app.schemas.post import PostResponse
from app.schemas.user import UserResponse


class GlobalSearchResponse(BaseModel):
    """Combined search response for users and posts."""

    users: list[UserResponse]
    posts: list[PostResponse]

