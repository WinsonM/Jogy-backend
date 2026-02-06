"""Location sync routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user_id
from app.schemas.location import (
    LocationSyncRequest,
    LocationSyncResponse,
    NearbyPoiItem,
    NearbyPoiResponse,
    ReverseGeocodeResponse,
)
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


@router.get("/nearby-pois", response_model=NearbyPoiResponse)
async def get_nearby_pois(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
) -> NearbyPoiResponse:
    """Get nearby POIs (placeholder implementation)."""
    # TODO: integrate real map provider POI search.
    return NearbyPoiResponse(
        items=[
            NearbyPoiItem(
                place_name="当前位置",
                address="当前定位",
                latitude=latitude,
                longitude=longitude,
                distance_meters=0,
            ),
            NearbyPoiItem(
                place_name="附近咖啡店",
                address="示例路 88 号",
                latitude=latitude + 0.001,
                longitude=longitude + 0.001,
                distance_meters=140,
            ),
        ]
    )


@router.get("/reverse-geocode", response_model=ReverseGeocodeResponse)
async def reverse_geocode(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
) -> ReverseGeocodeResponse:
    """Reverse geocode coordinates (placeholder implementation)."""
    # TODO: integrate real reverse geocoding provider.
    return ReverseGeocodeResponse(
        place_name="定位点",
        address=f"{latitude:.6f}, {longitude:.6f}",
        latitude=latitude,
        longitude=longitude,
    )
