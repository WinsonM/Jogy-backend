"""Periodic cleanup tasks."""

from sqlalchemy import delete, func, select

from app.core.database import get_db_context
from app.models.post import Post


async def delete_expired_posts() -> int:
    """Hard delete posts whose expire_at has passed.

    Dependent rows such as comments, likes, favorites, and browsing history are
    removed by database/ORM cascade rules.
    """
    async with get_db_context() as db:
        expired_filter = (Post.expire_at.isnot(None), Post.expire_at < func.now())
        count = (await db.execute(select(func.count(Post.id)).where(*expired_filter))).scalar() or 0
        if count == 0:
            return 0

        await db.execute(delete(Post).where(*expired_filter))
        return count
