"""Integration tests for API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    """Test root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    """Test health endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    """Test user registration."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "password": "TestPass123",
            "email": "test@example.com",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert "id" in data
    assert "password" not in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    """Test registration with duplicate username."""
    # First registration
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "duplicate",
            "password": "TestPass123",
        },
    )
    # Duplicate registration
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "duplicate",
            "password": "TestPass456",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    """Test user login."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "logintest",
            "password": "TestPass123",
        },
    )
    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": "logintest",
            "password": "TestPass123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Test login with wrong password."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "wrongpwtest",
            "password": "TestPass123",
        },
    )
    # Login with wrong password
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": "wrongpwtest",
            "password": "WrongPass123",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(client: AsyncClient):
    """Test getting current user profile."""
    # Register and login
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "profiletest",
            "password": "TestPass123",
        },
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": "profiletest",
            "password": "TestPass123",
        },
    )
    token = login_response.json()["access_token"]

    # Get profile
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "profiletest"


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient):
    """Test accessing protected endpoint without token."""
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401
