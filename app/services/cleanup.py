"""Periodic cleanup tasks."""

from sqlalchemy import delete, func, select

from app.core.database import get_db_context
from app.models.post import Post


async def delete_expired_posts() -> int:
    """Hard delete expired non-broadcast posts.

    Expired broadcasts are retained so notification recipients can still open
    their own broadcast detail in a read-only state.
    """
    async with get_db_context() as db:
        expired_filter = (
            Post.expire_at.isnot(None),
            Post.expire_at < func.now(),
            Post.post_type != "broadcast",
        )
        count = (await db.execute(select(func.count(Post.id)).where(*expired_filter))).scalar() or 0
        if count == 0:
            return 0

        await db.execute(delete(Post).where(*expired_filter))
        return count
