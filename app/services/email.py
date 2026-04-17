"""Email service for sending verification codes via SMTP."""

import random
import string
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings
from app.core.redis import get_redis


def _generate_code(length: int = 6) -> str:
    """Generate a random numeric verification code."""
    return "".join(random.choices(string.digits, k=length))


async def send_verification_code(email: str) -> None:
    """Generate a verification code, store in Redis, and send via email.

    Code expires after 5 minutes.
    """
    code = _generate_code()

    # Store in Redis with 5 minute TTL
    # Use raw Redis client (not RedisClient wrapper) for simple key/value ops
    redis = await get_redis()
    await redis.set(f"verify:{email}", code, ex=300)

    # Build email
    msg = EmailMessage()
    msg["Subject"] = f"[{settings.smtp_from_name}] 验证码: {code}"
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_user}>"
    msg["To"] = email
    msg.set_content(
        f"你的验证码是: {code}\n\n"
        f"验证码将在 5 分钟后过期。\n"
        f"如果你没有请求此验证码，请忽略此邮件。"
    )

    # Send via SMTP
    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        start_tls=True,
    )


async def verify_code(email: str, code: str) -> bool:
    """Verify a code against the one stored in Redis.

    Deletes the code on successful verification (one-time use).
    Also writes a 10-minute "email_verified" flag so the /register endpoint
    can confirm the email was verified recently without requiring the
    caller to pass the (already-consumed) code again. This bridges the
    gap between verify-code and the subsequent register call, and survives
    transient register failures (e.g. duplicate username) so the user can
    retry registration without re-sending a new code.
    """
    redis = await get_redis()
    stored_code = await redis.get(f"verify:{email}")

    if stored_code is None:
        return False

    # decode_responses=True in pool → values are already str, no .decode() needed
    if stored_code == code:
        await redis.delete(f"verify:{email}")
        # 10-minute window for the subsequent /register call
        await redis.set(f"email_verified:{email}", "1", ex=600)
        return True

    return False
