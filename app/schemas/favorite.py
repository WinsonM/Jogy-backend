"""Favorite schemas."""

from pydantic import BaseModel


class FavoriteToggleResponse(BaseModel):
    """Response schema for favorite/unfavorite operations."""

    favorited: bool
    favorites_count: int

