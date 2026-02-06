"""Additional auth schemas."""

from pydantic import BaseModel, EmailStr, Field


class SendCodeRequest(BaseModel):
    """Send verification code request."""

    email: EmailStr


class VerifyCodeRequest(BaseModel):
    """Verify one-time code request."""

    email: EmailStr
    code: str = Field(..., min_length=4, max_length=8)


class AuthActionResponse(BaseModel):
    """Generic auth action response."""

    success: bool
    message: str

