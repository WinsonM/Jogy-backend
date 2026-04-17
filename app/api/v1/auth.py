"""Authentication routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.core.database import get_db
from app.core.exceptions import (
    EmailNotVerifiedError,
    EmailTakenError,
    InvalidCredentialsError,
    InvalidTokenError,
    UserDisabledError,
    UsernameTakenError,
)
from app.schemas.auth import AuthActionResponse, SendCodeRequest, VerifyCodeRequest
from app.schemas.user import (
    RefreshTokenRequest,
    RegisterResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.auth import AuthService
from app.services.email import send_verification_code as send_email_code
from app.services.email import verify_code as verify_email_code

router = APIRouter()


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """Register a new user and return JWT tokens for auto-login.

    Requires the email to have been verified via POST /verify-code within
    the last 10 minutes. This lets the client retry registration after a
    transient failure (e.g. duplicate username) without needing the user
    to request and type a fresh verification code.
    """
    from app.core.redis import get_redis

    # Enforce email verification when an email is provided.
    # (Email is optional per UserCreate schema; the frontend requires it but
    # direct API callers could omit it.)
    redis = await get_redis()
    verified_key = f"email_verified:{user_data.email}" if user_data.email else None
    if verified_key is not None:
        verified = await redis.get(verified_key)
        if not verified:
            err = EmailNotVerifiedError()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": err.code, "message": err.message},
            )

    auth_service = AuthService(db)
    try:
        user = await auth_service.register(user_data)
    except UsernameTakenError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": e.code, "message": e.message},
        )
    except EmailTakenError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": e.code, "message": e.message},
        )

    # Consume the verification flag so it can't be reused for another account.
    if verified_key is not None:
        await redis.delete(verified_key)

    # Issue tokens so the client can skip the separate /login round-trip.
    tokens = auth_service.create_tokens(user.id)
    return RegisterResponse(
        user=UserResponse.model_validate(user),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Login and get access token."""
    auth_service = AuthService(db)
    try:
        user = await auth_service.authenticate(
            credentials.username,
            credentials.password,
        )
        return auth_service.create_tokens(user.id)
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": e.code, "message": e.message},
        )
    except UserDisabledError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": e.code, "message": e.message},
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Refresh access token."""
    auth_service = AuthService(db)
    try:
        return await auth_service.refresh_tokens(request.refresh_token)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": e.code, "message": e.message},
        )
    except UserDisabledError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": e.code, "message": e.message},
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    _: UUID = Depends(get_current_user_id),
) -> None:
    """Logout current user.

    JWT is stateless here, so this endpoint is currently a client-side token drop hook.
    """
    return None


@router.post("/send-code", response_model=AuthActionResponse)
async def send_verification_code(
    request: SendCodeRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthActionResponse:
    """Send verification code to email via SMTP.

    Rejects emails that are already registered so the user gets fast feedback
    instead of walking through the whole signup flow just to hit a 409 at the
    end. Rate-limited: one code per email per 60 seconds.
    """
    from sqlalchemy import select

    from app.core.redis import get_redis
    from app.models.user import User

    # Reject already-registered emails up front (same lookup as AuthService.register).
    # Placed *before* the cooldown check so this error path never writes the cooldown key.
    existing = await db.execute(select(User).where(User.email == request.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": EmailTakenError.code,
                "message": "此邮箱已注册，请直接登录",
            },
        )

    # Rate limit: 60s cooldown per email
    redis = await get_redis()
    cooldown_key = f"send_code_cd:{request.email}"
    if await redis.exists(cooldown_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请等待 60 秒后再重新发送验证码",
        )

    try:
        await send_email_code(request.email)
        # Set 60s cooldown
        await redis.set(cooldown_key, "1", ex=60)
        return AuthActionResponse(success=True, message=f"Code sent to {request.email}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send code: {str(e)}",
        )


@router.post("/verify-code", response_model=AuthActionResponse)
async def verify_code(
    request: VerifyCodeRequest,
) -> AuthActionResponse:
    """Verify a one-time code stored in Redis."""
    is_valid = await verify_email_code(request.email, request.code)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code",
        )
    return AuthActionResponse(success=True, message="Code verified")
