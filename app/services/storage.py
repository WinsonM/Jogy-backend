"""File storage service - local filesystem with easy migration to OSS/S3."""

import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings

# Base upload directory
UPLOAD_DIR = Path("uploads")
IMAGE_DIR = UPLOAD_DIR / "images"
FILE_DIR = UPLOAD_DIR / "files"

# Allowed image types
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _ensure_dirs() -> None:
    """Create upload directories if they don't exist."""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    FILE_DIR.mkdir(parents=True, exist_ok=True)


def _generate_filename(original_name: str) -> str:
    """Generate a unique filename preserving the extension."""
    ext = Path(original_name).suffix.lower() if original_name else ""
    date_prefix = datetime.now().strftime("%Y%m%d")
    unique_id = uuid.uuid4().hex[:12]
    return f"{date_prefix}_{unique_id}{ext}"


async def save_image(file: UploadFile) -> str:
    """Save an uploaded image and return its URL path.

    Returns:
        Relative URL path like /uploads/images/20260331_abc123def456.jpg
    """
    _ensure_dirs()

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(
            f"Unsupported image type: {file.content_type}. "
            f"Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}"
        )

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise ValueError(f"Image too large. Max size: {MAX_IMAGE_SIZE // 1024 // 1024}MB")

    filename = _generate_filename(file.filename or "image.jpg")
    filepath = IMAGE_DIR / filename

    with open(filepath, "wb") as f:
        f.write(content)

    return f"/uploads/images/{filename}"


async def save_file(file: UploadFile) -> dict:
    """Save an uploaded file and return its metadata.

    Returns:
        Dict with url, file_name, file_size, mime_type
    """
    _ensure_dirs()

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"File too large. Max size: {MAX_FILE_SIZE // 1024 // 1024}MB")

    filename = _generate_filename(file.filename or "file")
    filepath = FILE_DIR / filename

    with open(filepath, "wb") as f:
        f.write(content)

    return {
        "url": f"/uploads/files/{filename}",
        "file_name": file.filename,
        "file_size": len(content),
        "mime_type": file.content_type,
    }
