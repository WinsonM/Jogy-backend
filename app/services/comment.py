"""Comment service with tree structure queries."""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.models.post import Post
from app.schemas.comment import (
    CommentCreate,
    CommentListResponse,
    CommentTreeResponse,
)


class CommentService:
    """Service for comment operations with tree structure."""

    # Default number of replies to include in tree response
    TOP_REPLIES_LIMIT = 2

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_comment(
        self,
        post_id: UUID,
        user_id: UUID,
        data: CommentCreate,
    ) -> Comment:
        """Create a new comment or reply."""
        # Verify post exists
        post_result = await self.db.execute(
            select(Post).where(Post.id == post_id)
        )
        post = post_result.scalar_one_or_none()
        if not post:
            raise ValueError("Post not found")

        reply_to_user_id: Optional[UUID] = None
        root_id: Optional[UUID] = None

        # If replying, verify parent exists and belongs to same post
        if data.parent_id:
            parent_result = await self.db.execute(
                select(Comment).where(
                    Comment.id == data.parent_id,
                    Comment.post_id == post_id,
                )
            )
            parent = parent_result.scalar_one_or_none()
            if not parent:
                raise ValueError("Parent comment not found")

            # Increment parent's reply count
            await self.db.execute(
                update(Comment)
                .where(Comment.id == data.parent_id)
                .values(replies_count=Comment.replies_count + 1)
            )
            root_id = parent.root_id or parent.id
            reply_to_user_id = data.reply_to_user_id or parent.user_id

        # Create comment
        comment = Comment(
            post_id=post_id,
            user_id=user_id,
            content=data.content,
            parent_id=data.parent_id,
            root_id=root_id,
            reply_to_user_id=reply_to_user_id,
        )
        self.db.add(comment)
        await self.db.flush()

        # Root comment points to itself for efficient thread querying
        if comment.parent_id is None:
            comment.root_id = comment.id

        # Increment post's comment count
        await self.db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(comments_count=Post.comments_count + 1)
        )

        await self.db.refresh(comment)
        return comment

    async def get_comments(
        self,
        post_id: UUID,
        parent_id: Optional[UUID] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> CommentListResponse:
        """
        Get comments for a post with pagination.

        If parent_id is None, returns root-level comments.
        Each comment includes top N replies.
        """
        # Base query for comments at this level
        query = (
            select(Comment)
            .where(Comment.post_id == post_id)
            .options(selectinload(Comment.user), selectinload(Comment.reply_to_user))
        )

        if parent_id is None:
            query = query.where(Comment.parent_id.is_(None))
        else:
            query = query.where(Comment.root_id == parent_id, Comment.id != parent_id)

        # Count total
        count_query = (
            select(func.count(Comment.id))
            .where(Comment.post_id == post_id)
        )
        if parent_id is None:
            count_query = count_query.where(Comment.parent_id.is_(None))
        else:
            count_query = count_query.where(Comment.root_id == parent_id, Comment.id != parent_id)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get comments with pagination
        query = query.order_by(Comment.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        comments = result.scalars().all()

        # Build response.
        if parent_id is None:
            # Root comments with top replies preview (batch loaded).
            tree_comments = await self._build_comment_trees_batch(comments)
        else:
            # Flat thread replies view.
            tree_comments = [
                CommentTreeResponse(
                    id=comment.id,
                    post_id=comment.post_id,
                    user_id=comment.user_id,
                    content=comment.content,
                    parent_id=comment.parent_id,
                    root_id=comment.root_id,
                    reply_to_user_id=comment.reply_to_user_id,
                    reply_to_username=comment.reply_to_user.username if comment.reply_to_user else None,
                    created_at=comment.created_at,
                    replies_count=comment.replies_count,
                    likes_count=comment.likes_count,
                    user=comment.user,
                    replies=[],
                    has_more_replies=False,
                )
                for comment in comments
            ]

        return CommentListResponse(
            comments=tree_comments,
            total=total,
            has_more=offset + len(comments) < total,
        )

    async def _build_comment_trees_batch(
        self,
        root_comments: list[Comment],
    ) -> list[CommentTreeResponse]:
        """Build comment trees for multiple root comments in ONE query instead of N.

        Old: 20 root comments = 20 × SELECT replies = 20 queries
        New: 20 root comments = 1 × SELECT replies WHERE root_id IN (...) = 1 query
        """
        if not root_comments:
            return []

        root_ids = [c.id for c in root_comments]

        # Single query: get all replies for all root comments at once
        all_replies_result = await self.db.execute(
            select(Comment)
            .where(Comment.root_id.in_(root_ids), Comment.id.notin_(root_ids))
            .options(selectinload(Comment.user), selectinload(Comment.reply_to_user))
            .order_by(Comment.created_at.asc())
        )
        all_replies = all_replies_result.scalars().all()

        # Group replies by root_id
        replies_by_root: dict[UUID, list[Comment]] = {rid: [] for rid in root_ids}
        for reply in all_replies:
            if reply.root_id in replies_by_root:
                replies_by_root[reply.root_id].append(reply)

        # Build tree for each root
        tree_comments = []
        for comment in root_comments:
            thread_replies = replies_by_root.get(comment.id, [])
            top_replies = thread_replies[: self.TOP_REPLIES_LIMIT]
            total_replies = len(thread_replies)

            reply_responses = [
                CommentTreeResponse(
                    id=reply.id,
                    post_id=reply.post_id,
                    user_id=reply.user_id,
                    content=reply.content,
                    parent_id=reply.parent_id,
                    root_id=reply.root_id,
                    reply_to_user_id=reply.reply_to_user_id,
                    reply_to_username=reply.reply_to_user.username if reply.reply_to_user else None,
                    created_at=reply.created_at,
                    replies_count=reply.replies_count,
                    likes_count=reply.likes_count,
                    user=reply.user,
                    replies=[],
                    has_more_replies=reply.replies_count > 0,
                )
                for reply in top_replies
            ]

            tree_comments.append(
                CommentTreeResponse(
                    id=comment.id,
                    post_id=comment.post_id,
                    user_id=comment.user_id,
                    content=comment.content,
                    parent_id=comment.parent_id,
                    root_id=comment.root_id,
                    reply_to_user_id=comment.reply_to_user_id,
                    reply_to_username=comment.reply_to_user.username if comment.reply_to_user else None,
                    created_at=comment.created_at,
                    replies_count=comment.replies_count,
                    likes_count=comment.likes_count,
                    user=comment.user,
                    replies=reply_responses,
                    has_more_replies=total_replies > len(top_replies),
                )
            )

        return tree_comments

    async def _build_comment_tree(
        self,
        comment: Comment,
    ) -> CommentTreeResponse:
        """Build comment tree response with top N replies."""
        # Get top N replies
        replies_query = (
            select(Comment)
            .where(Comment.root_id == comment.id, Comment.id != comment.id)
            .options(selectinload(Comment.user), selectinload(Comment.reply_to_user))
            .order_by(Comment.created_at.asc())
            .limit(self.TOP_REPLIES_LIMIT)
        )
        replies_result = await self.db.execute(replies_query)
        replies = replies_result.scalars().all()
        replies_total_result = await self.db.execute(
            select(func.count(Comment.id)).where(
                Comment.root_id == comment.id,
                Comment.id != comment.id,
            )
        )
        replies_total = replies_total_result.scalar() or 0

        # Build nested replies (no further nesting for performance)
        reply_responses = [
            CommentTreeResponse(
                id=reply.id,
                post_id=reply.post_id,
                user_id=reply.user_id,
                content=reply.content,
                parent_id=reply.parent_id,
                root_id=reply.root_id,
                reply_to_user_id=reply.reply_to_user_id,
                reply_to_username=reply.reply_to_user.username if reply.reply_to_user else None,
                created_at=reply.created_at,
                replies_count=reply.replies_count,
                likes_count=reply.likes_count,
                user=reply.user,
                replies=[],  # Don't nest further
                has_more_replies=reply.replies_count > 0,
            )
            for reply in replies
        ]

        return CommentTreeResponse(
            id=comment.id,
            post_id=comment.post_id,
            user_id=comment.user_id,
            content=comment.content,
            parent_id=comment.parent_id,
            root_id=comment.root_id,
            reply_to_user_id=comment.reply_to_user_id,
            reply_to_username=comment.reply_to_user.username if comment.reply_to_user else None,
            created_at=comment.created_at,
            replies_count=comment.replies_count,
            likes_count=comment.likes_count,
            user=comment.user,
            replies=reply_responses,
            has_more_replies=replies_total > len(replies),
        )

    async def get_comment_by_id(
        self,
        comment_id: UUID,
    ) -> Optional[Comment]:
        """Get comment by ID."""
        result = await self.db.execute(
            select(Comment)
            .where(Comment.id == comment_id)
            .options(selectinload(Comment.user), selectinload(Comment.reply_to_user))
        )
        return result.scalar_one_or_none()

    async def delete_comment(
        self,
        comment_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Delete a comment (only by author)."""
        result = await self.db.execute(
            select(Comment).where(
                Comment.id == comment_id,
                Comment.user_id == user_id,
            )
        )
        comment = result.scalar_one_or_none()

        if not comment:
            return False

        subtree_count_result = await self.db.execute(
            text(
                """
                WITH RECURSIVE comment_tree AS (
                    SELECT id
                    FROM comments
                    WHERE id = :root_id
                    UNION ALL
                    SELECT c.id
                    FROM comments c
                    JOIN comment_tree ct ON c.parent_id = ct.id
                )
                SELECT COUNT(*) AS total
                FROM comment_tree
                """
            ),
            {"root_id": comment.id},
        )
        subtree_count = subtree_count_result.scalar() or 1

        # Decrement parent's reply count if this is a reply
        if comment.parent_id:
            await self.db.execute(
                update(Comment)
                .where(Comment.id == comment.parent_id)
                .values(replies_count=func.greatest(Comment.replies_count - 1, 0))
            )

        # Decrement post's comment count
        await self.db.execute(
            update(Post)
            .where(Post.id == comment.post_id)
            .values(comments_count=func.greatest(Post.comments_count - subtree_count, 0))
        )

        await self.db.delete(comment)
        return True
