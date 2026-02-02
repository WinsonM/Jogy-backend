"""Location sync routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user_id
from app.schemas.location import LocationSyncRequest, LocationSyncResponse
from app.services.location import LocationService

router = APIRouter()


@router.post("/sync", response_model=LocationSyncResponse)
async def sync_location(
    location: LocationSyncRequest,
    current_user_id: UUID = Depends(get_current_user_id),
) -> LocationSyncResponse:
    """
    Sync user's current location.

    Stores precise coordinates in Redis for real-time nearby queries.
    Rate limited to prevent abuse.
    """
    location_service = LocationService()
    success = await location_service.sync_location(
        user_id=current_user_id,
        latitude=location.latitude,
        longitude=location.longitude,
    )

    return LocationSyncResponse(
        success=success,
        message="Location synced" if success else "Failed to sync location",
    )
