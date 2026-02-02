"""Tests for security utilities."""

import time

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_signature,
    hash_password,
    verify_password,
    verify_signature,
    verify_token,
)
from uuid import uuid4


class TestPasswordHashing:
    """Tests for password hashing."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "TestPassword123"
        hashed = hash_password(password)
        assert hashed != password
        assert hashed.startswith("$argon2")

    def test_verify_password_correct(self):
        """Test verifying correct password."""
        password = "TestPassword123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        password = "TestPassword123"
        wrong_password = "WrongPassword123"
        hashed = hash_password(password)
        assert verify_password(wrong_password, hashed) is False


class TestJWT:
    """Tests for JWT token operations."""

    def test_create_access_token(self):
        """Test creating access token."""
        user_id = uuid4()
        token = create_access_token(user_id)
        assert token is not None
        assert len(token) > 0

    def test_create_refresh_token(self):
        """Test creating refresh token."""
        user_id = uuid4()
        token = create_refresh_token(user_id)
        assert token is not None
        assert len(token) > 0

    def test_verify_access_token(self):
        """Test verifying access token."""
        user_id = uuid4()
        token = create_access_token(user_id)
        verified_id = verify_token(token, token_type="access")
        assert verified_id == user_id

    def test_verify_refresh_token(self):
        """Test verifying refresh token."""
        user_id = uuid4()
        token = create_refresh_token(user_id)
        verified_id = verify_token(token, token_type="refresh")
        assert verified_id == user_id

    def test_verify_token_wrong_type(self):
        """Test that access token fails refresh verification."""
        user_id = uuid4()
        token = create_access_token(user_id)
        verified_id = verify_token(token, token_type="refresh")
        assert verified_id is None

    def test_verify_invalid_token(self):
        """Test verifying invalid token."""
        verified_id = verify_token("invalid.token.here")
        assert verified_id is None


class TestAPISignature:
    """Tests for API signature verification."""

    def test_generate_signature(self):
        """Test generating signature."""
        body = b'{"test": "data"}'
        timestamp = str(int(time.time()))
        signature = generate_signature(body, timestamp)
        assert signature is not None
        assert len(signature) == 64  # SHA256 hex digest

    def test_verify_signature_valid(self):
        """Test verifying valid signature."""
        body = b'{"test": "data"}'
        timestamp = str(int(time.time()))
        signature = generate_signature(body, timestamp)
        assert verify_signature(body, timestamp, signature) is True

    def test_verify_signature_invalid(self):
        """Test verifying invalid signature."""
        body = b'{"test": "data"}'
        timestamp = str(int(time.time()))
        assert verify_signature(body, timestamp, "invalid_signature") is False

    def test_verify_signature_expired(self):
        """Test that old timestamps are rejected."""
        body = b'{"test": "data"}'
        old_timestamp = str(int(time.time()) - 600)  # 10 minutes ago
        signature = generate_signature(body, old_timestamp)
        assert verify_signature(body, old_timestamp, signature) is False
