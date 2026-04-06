"""File storage service with image compression and thumbnail generation.

Local filesystem storage with easy migration path to OSS/S3.
Images are automatically compressed and thumbnails generated for bubble previews.
"""

import io
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings

# Base upload directory
UPLOAD_DIR = Path("uploads")
IMAGE_DIR = UPLOAD_DIR / "images"
THUMB_DIR = UPLOAD_DIR / "thumbnails"
FILE_DIR = UPLOAD_DIR / "files"

# Allowed image types
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# Image compression settings
COMPRESS_MAX_DIMENSION = 1920  # Max width or height after compression
COMPRESS_QUALITY = 85          # JPEG quality (1-100)
THUMB_SIZE = (400, 400)        # Thumbnail max dimensions (for bubble preview)
THUMB_QUALITY = 75             # Thumbnail JPEG quality


def _ensure_dirs() -> None:
    """Create upload directories if they don't exist."""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    FILE_DIR.mkdir(parents=True, exist_ok=True)


def _generate_filename(original_name: str) -> str:
    """Generate a unique filename preserving the extension."""
    ext = Path(original_name).suffix.lower() if original_name else ""
    date_prefix = datetime.now().strftime("%Y%m%d")
    unique_id = uuid.uuid4().hex[:12]
    return f"{date_prefix}_{unique_id}{ext}"


def _compress_image(content: bytes, content_type: str) -> tuple[bytes, str]:
    """Compress image: resize if oversized, re-encode with quality control.

    Returns:
        Tuple of (compressed_bytes, output_filename_extension)
    """
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(content))

        # Handle EXIF rotation
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # GIF: skip compression (animated frames)
        if content_type == "image/gif":
            return content, ".gif"

        # Convert RGBA to RGB for JPEG output (PNG with transparency)
        if img.mode in ("RGBA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[3])
            img = background

        # Resize if larger than max dimension
        w, h = img.size
        if max(w, h) > COMPRESS_MAX_DIMENSION:
            ratio = COMPRESS_MAX_DIMENSION / max(w, h)
            new_size = (int(w * ratio), int(h * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        # Encode as WebP (best compression for web) or JPEG as fallback
        output = io.BytesIO()
        try:
            img.save(output, format="WEBP", quality=COMPRESS_QUALITY, method=4)
            return output.getvalue(), ".webp"
        except Exception:
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=COMPRESS_QUALITY, optimize=True)
            return output.getvalue(), ".jpg"

    except ImportError:
        # Pillow not installed, return original
        ext = ".jpg"
        if content_type == "image/png":
            ext = ".png"
        elif content_type == "image/gif":
            ext = ".gif"
        elif content_type == "image/webp":
            ext = ".webp"
        return content, ext


def _generate_thumbnail(content: bytes, content_type: str) -> bytes | None:
    """Generate a thumbnail for bubble preview display.

    Returns:
        Thumbnail bytes, or None if Pillow unavailable.
    """
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(content))

        # Handle EXIF rotation
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # GIF: take first frame only
        if hasattr(img, "n_frames") and img.n_frames > 1:
            img.seek(0)

        # Convert to RGB
        if img.mode in ("RGBA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[3])
            img = background

        # Create thumbnail (maintains aspect ratio, fits within box)
        img.thumbnail(THUMB_SIZE, Image.LANCZOS)

        output = io.BytesIO()
        try:
            img.save(output, format="WEBP", quality=THUMB_QUALITY, method=4)
        except Exception:
            img.save(output, format="JPEG", quality=THUMB_QUALITY, optimize=True)
        return output.getvalue()

    except ImportError:
        return None


async def save_image(file: UploadFile) -> dict:
    """Save an uploaded image with compression and thumbnail generation.

    Returns:
        Dict with url and thumbnail_url:
        {
            "url": "/uploads/images/20260331_abc123def456.webp",
            "thumbnail_url": "/uploads/thumbnails/20260331_abc123def456.webp"
        }
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

    # Compress image
    compressed, ext = _compress_image(content, file.content_type)

    # Generate unique base name
    date_prefix = datetime.now().strftime("%Y%m%d")
    unique_id = uuid.uuid4().hex[:12]
    base_name = f"{date_prefix}_{unique_id}"

    # Save compressed image
    image_filename = f"{base_name}{ext}"
    image_path = IMAGE_DIR / image_filename
    with open(image_path, "wb") as f:
        f.write(compressed)

    result = {"url": f"/uploads/images/{image_filename}"}

    # Generate and save thumbnail
    thumb_bytes = _generate_thumbnail(content, file.content_type)
    if thumb_bytes:
        thumb_ext = ".webp" if ext != ".gif" else ".jpg"
        thumb_filename = f"{base_name}{thumb_ext}"
        thumb_path = THUMB_DIR / thumb_filename
        with open(thumb_path, "wb") as f:
            f.write(thumb_bytes)
        result["thumbnail_url"] = f"/uploads/thumbnails/{thumb_filename}"

    return result


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
