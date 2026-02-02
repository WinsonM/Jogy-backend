"""Location schemas for request/response validation."""

from pydantic import BaseModel, Field


class LocationSyncRequest(BaseModel):
    """Schema for location sync request."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: float = Field(default=0, ge=0)  # meters


class LocationSyncResponse(BaseModel):
    """Schema for location sync response."""

    success: bool
    message: str = "Location synced"
