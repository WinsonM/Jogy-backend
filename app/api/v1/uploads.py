"""File upload endpoints."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from uuid import UUID

from app.api.deps import get_current_user_id
from app.services.storage import save_image, save_file

router = APIRouter()


@router.post("/image", status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile,
    current_user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """Upload an image file. Returns URL and thumbnail URL.

    Response: {"url": "/uploads/images/...", "thumbnail_url": "/uploads/thumbnails/..."}
    Images are automatically compressed (max 1920px, WebP) and thumbnails generated (400x400).
    """
    try:
        result = await save_image(file)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/file", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    current_user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """Upload a generic file. Returns URL and metadata."""
    try:
        result = await save_file(file)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
