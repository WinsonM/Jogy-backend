"""Security utilities: JWT, password hashing, API signature."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings

# Password hasher
ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
)


# ==================== Password Hashing ====================


def hash_password(password: str) -> str:
    """Hash password using Argon2."""
    return ph.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    try:
        ph.verify(hashed_password, password)
        return True
    except VerifyMismatchError:
        return False


def check_needs_rehash(hashed_password: str) -> bool:
    """Check if password hash needs to be updated."""
    return ph.check_needs_rehash(hashed_password)


# ==================== JWT Tokens ====================


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str  # User ID
    exp: datetime
    iat: datetime
    type: str  # "access" or "refresh"


def create_access_token(
    user_id: UUID,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create JWT access token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    user_id: UUID,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create JWT refresh token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[TokenPayload]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenPayload(**payload)
    except JWTError:
        return None


def verify_token(token: str, token_type: str = "access") -> Optional[UUID]:
    """Verify token and return user ID if valid."""
    payload = decode_token(token)
    if payload is None:
        return None
    if payload.type != token_type:
        return None
    try:
        return UUID(payload.sub)
    except ValueError:
        return None


# ==================== API Signature ====================


def generate_signature(body: bytes, timestamp: str, secret: Optional[str] = None) -> str:
    """
    Generate HMAC-SHA256 signature for API request.

    Signature = HMAC_SHA256(Body + Timestamp + Secret)
    """
    if secret is None:
        secret = settings.api_signature_secret

    message = body + timestamp.encode() + secret.encode()
    return hmac.new(
        secret.encode(),
        message,
        hashlib.sha256,
    ).hexdigest()


def verify_signature(
    body: bytes,
    timestamp: str,
    signature: str,
    secret: Optional[str] = None,
    max_age_seconds: int = 300,
) -> bool:
    """
    Verify API request signature.

    Returns True if signature is valid and timestamp is within max_age_seconds.
    """
    # Check timestamp age
    try:
        request_time = int(timestamp)
        current_time = int(datetime.now(timezone.utc).timestamp())
        if abs(current_time - request_time) > max_age_seconds:
            return False
    except (ValueError, TypeError):
        return False

    # Verify signature
    expected_signature = generate_signature(body, timestamp, secret)
    return hmac.compare_digest(signature, expected_signature)


# ==================== Utilities ====================


def generate_random_token(length: int = 32) -> str:
    """Generate a random URL-safe token."""
    return secrets.token_urlsafe(length)
