"""
api/images.py — Endpoint for serving extracted images.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.pdf_service import get_image_path

router = APIRouter(prefix="/images", tags=["Images"])


@router.get("/{image_path:path}")
async def serve_image(image_path: str):
    """
    Serve an extracted image by its relative path.
    """
    absolute_path = get_image_path(image_path)

    if not absolute_path:
        raise HTTPException(
            status_code=404,
            detail=f"Image not found: {image_path}",
        )

    # Simple content type resolution
    ext = absolute_path.suffix.lower()
    media_type = "image/jpeg"
    if ext == ".png":
        media_type = "image/png"

    return FileResponse(
        str(absolute_path),
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
        },
    )
