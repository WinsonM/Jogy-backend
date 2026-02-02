"""Comment service with tree structure queries."""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
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

        # Create comment
        comment = Comment(
            post_id=post_id,
            user_id=user_id,
            content=data.content,
            parent_id=data.parent_id,
        )
        self.db.add(comment)

        # Increment post's comment count
        await self.db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(comments_count=Post.comments_count + 1)
        )

        await self.db.flush()
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
            .options(selectinload(Comment.user))
        )

        if parent_id is None:
            query = query.where(Comment.parent_id.is_(None))
        else:
            query = query.where(Comment.parent_id == parent_id)

        # Count total
        count_query = (
            select(func.count(Comment.id))
            .where(Comment.post_id == post_id)
        )
        if parent_id is None:
            count_query = count_query.where(Comment.parent_id.is_(None))
        else:
            count_query = count_query.where(Comment.parent_id == parent_id)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get comments with pagination
        query = query.order_by(Comment.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        comments = result.scalars().all()

        # Build tree response with top replies
        tree_comments = []
        for comment in comments:
            tree_comment = await self._build_comment_tree(comment)
            tree_comments.append(tree_comment)

        return CommentListResponse(
            comments=tree_comments,
            total=total,
            has_more=offset + len(comments) < total,
        )

    async def _build_comment_tree(
        self,
        comment: Comment,
    ) -> CommentTreeResponse:
        """Build comment tree response with top N replies."""
        # Get top N replies
        replies_query = (
            select(Comment)
            .where(Comment.parent_id == comment.id)
            .options(selectinload(Comment.user))
            .order_by(Comment.created_at.asc())
            .limit(self.TOP_REPLIES_LIMIT)
        )
        replies_result = await self.db.execute(replies_query)
        replies = replies_result.scalars().all()

        # Build nested replies (no further nesting for performance)
        reply_responses = [
            CommentTreeResponse(
                id=reply.id,
                post_id=reply.post_id,
                user_id=reply.user_id,
                content=reply.content,
                parent_id=reply.parent_id,
                created_at=reply.created_at,
                replies_count=reply.replies_count,
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
            created_at=comment.created_at,
            replies_count=comment.replies_count,
            user=comment.user,
            replies=reply_responses,
            has_more_replies=comment.replies_count > len(replies),
        )

    async def get_comment_by_id(
        self,
        comment_id: UUID,
    ) -> Optional[Comment]:
        """Get comment by ID."""
        result = await self.db.execute(
            select(Comment)
            .where(Comment.id == comment_id)
            .options(selectinload(Comment.user))
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

        # Decrement parent's reply count if this is a reply
        if comment.parent_id:
            await self.db.execute(
                update(Comment)
                .where(Comment.id == comment.parent_id)
                .values(replies_count=Comment.replies_count - 1)
            )

        # Decrement post's comment count
        await self.db.execute(
            update(Post)
            .where(Post.id == comment.post_id)
            .values(comments_count=Post.comments_count - 1)
        )

        await self.db.delete(comment)
        return True
