"""QR code schemas."""

from pydantic import BaseModel


class MyQRCodeResponse(BaseModel):
    """Current user QR payload."""

    qr_data: str


class QRResolveRequest(BaseModel):
    """Resolve QR payload request."""

    code: str


class QRResolveResponse(BaseModel):
    """Resolve QR payload response."""

    target_type: str
    target_id: str

