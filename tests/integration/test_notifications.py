"""Notification integration tests."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_current_user_id_optional
from app.main import app
from app.models.notification import Notification
from app.models.user import User
from app.schemas.post import LocationPoint
from app.services.discover import DiscoverService


async def _create_user(db: AsyncSession, username: str) -> User:
    user = User(username=username, hashed_password="hashed")
    db.add(user)
    await db.flush()
    return user


async def _create_post(
    db: AsyncSession,
    author: User,
    post_type: str = "bubble",
    content: str = "hello from a post",
):
    return await DiscoverService(db).create_post(
        author_id=author.id,
        content_text=content,
        post_type=post_type,
        location=LocationPoint(latitude=37.7749, longitude=-122.4194),
        expire_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


def _override_required_user(user: User) -> None:
    app.dependency_overrides[get_current_user_id] = lambda: user.id


def _override_optional_user(user: User | None) -> None:
    app.dependency_overrides[get_current_user_id_optional] = lambda: user.id if user else None


@pytest.mark.asyncio
async def test_post_like_creates_and_upserts_notification(
    client: AsyncClient,
    db_session: AsyncSession,
):
    owner = await _create_user(db_session, "notify_owner_like")
    actor = await _create_user(db_session, "notify_actor_like")
    post = await _create_post(db_session, owner, content="owner bubble")

    _override_required_user(actor)
    response = await client.put(f"/api/v1/posts/{post.id}/likes/me")
    assert response.status_code == 200

    result = await db_session.execute(select(Notification))
    notifications = result.scalars().all()
    assert len(notifications) == 1
    assert notifications[0].recipient_user_id == owner.id
    assert notifications[0].actor_user_id == actor.id
    assert notifications[0].type == "post_like"
    assert notifications[0].target_type == "bubble"

    response = await client.delete(f"/api/v1/posts/{post.id}/likes/me")
    assert response.status_code == 200
    response = await client.put(f"/api/v1/posts/{post.id}/likes/me")
    assert response.status_code == 200

    result = await db_session.execute(select(Notification))
    notifications = result.scalars().all()
    assert len(notifications) == 1
    assert notifications[0].read_at is None


@pytest.mark.asyncio
async def test_reply_notification_and_unread_endpoints(
    client: AsyncClient,
    db_session: AsyncSession,
):
    owner = await _create_user(db_session, "notify_owner_reply")
    actor = await _create_user(db_session, "notify_actor_reply")
    post = await _create_post(db_session, owner, post_type="broadcast", content="owner broadcast")

    _override_required_user(actor)
    response = await client.post(
        f"/api/v1/posts/{post.id}/comments",
        json={"content": "reply to broadcast"},
    )
    assert response.status_code == 201

    _override_required_user(owner)
    response = await client.get("/api/v1/notifications/unread-count")
    assert response.status_code == 200
    assert response.json()["unread_count"] == 1

    response = await client.get("/api/v1/notifications")
    assert response.status_code == 200
    payload = response.json()
    assert payload["unread_count"] == 1
    assert len(payload["notifications"]) == 1
    item = payload["notifications"][0]
    assert item["type"] == "post_reply"
    assert item["target_type"] == "broadcast"
    assert item["post_id"] == str(post.id)
    assert item["actor"]["username"] == actor.username
    assert item["target_preview"] == "reply to broadcast"

    response = await client.patch(f"/api/v1/notifications/{item['id']}/read")
    assert response.status_code == 200
    response = await client.get("/api/v1/notifications/unread-count")
    assert response.json()["unread_count"] == 0


@pytest.mark.asyncio
async def test_self_interaction_does_not_create_notification(
    client: AsyncClient,
    db_session: AsyncSession,
):
    owner = await _create_user(db_session, "notify_owner_self")
    post = await _create_post(db_session, owner, content="self bubble")

    _override_required_user(owner)
    response = await client.put(f"/api/v1/posts/{post.id}/likes/me")
    assert response.status_code == 200
    response = await client.post(
        f"/api/v1/posts/{post.id}/comments",
        json={"content": "self reply"},
    )
    assert response.status_code == 201

    result = await db_session.execute(select(Notification))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_broadcast_comments_are_visible_only_to_author_and_commenter(
    client: AsyncClient,
    db_session: AsyncSession,
):
    owner = await _create_user(db_session, "broadcast_owner")
    actor = await _create_user(db_session, "broadcast_actor")
    other = await _create_user(db_session, "broadcast_other")
    post = await _create_post(db_session, owner, post_type="broadcast", content="private broadcast")

    _override_required_user(actor)
    response = await client.post(
        f"/api/v1/posts/{post.id}/comments",
        json={"content": "private reply"},
    )
    assert response.status_code == 201

    _override_optional_user(other)
    response = await client.get(f"/api/v1/posts/{post.id}/comments")
    assert response.status_code == 200
    assert response.json()["comments"] == []

    _override_optional_user(actor)
    response = await client.get(f"/api/v1/posts/{post.id}/comments")
    assert response.status_code == 200
    assert len(response.json()["comments"]) == 1

    _override_optional_user(owner)
    response = await client.get(f"/api/v1/posts/{post.id}/comments")
    assert response.status_code == 200
    assert len(response.json()["comments"]) == 1
