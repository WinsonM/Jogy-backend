"""QR utility routes."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.qr import QRResolveRequest, QRResolveResponse

router = APIRouter()


@router.post("/resolve", response_model=QRResolveResponse)
async def resolve_qr_code(request: QRResolveRequest) -> QRResolveResponse:
    """Resolve app QR code into target resource metadata."""
    code = request.code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR code")

    # Example: jogy://user/profile/{id}
    if code.startswith("jogy://user/profile/"):
        user_id = code.rsplit("/", maxsplit=1)[-1]
        if not user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR code")
        return QRResolveResponse(target_type="user_profile", target_id=user_id)

    if code.startswith("jogy://post/"):
        post_id = code.rsplit("/", maxsplit=1)[-1]
        if not post_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR code")
        return QRResolveResponse(target_type="post", target_id=post_id)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported QR code")

