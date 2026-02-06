"""Add social graph, favorites, messaging, and history tables.

Revision ID: 002_social_graph_messaging
Revises: 001_initial
Create Date: 2026-02-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "002_social_graph_messaging"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep user deletion from cascading into posts.
    op.drop_constraint("posts_author_id_fkey", "posts", type_="foreignkey")
    op.create_foreign_key(
        "posts_author_id_fkey",
        "posts",
        "users",
        ["author_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("posts", "author_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)

    # Keep comments after user deletion.
    op.drop_constraint("comments_user_id_fkey", "comments", type_="foreignkey")
    op.create_foreign_key(
        "comments_user_id_fkey",
        "comments",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("comments", "user_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)

    # Post likes should always map to an existing user.
    op.execute("DELETE FROM likes WHERE user_id IS NULL")
    op.drop_constraint("likes_user_id_fkey", "likes", type_="foreignkey")
    op.alter_column("likes", "user_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.create_foreign_key(
        "likes_user_id_fkey",
        "likes",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Extend user profile fields.
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("gender", sa.String(length=20), server_default="保密", nullable=False))
    op.add_column("users", sa.Column("birthday", sa.Date(), nullable=True))

    # Extend post fields.
    op.add_column("posts", sa.Column("title", sa.String(length=100), nullable=True))
    op.add_column(
        "posts",
        sa.Column("post_type", sa.String(length=20), server_default="bubble", nullable=False),
    )
    op.add_column("posts", sa.Column("expire_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "posts",
        sa.Column("favorites_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index("idx_posts_expire_at", "posts", ["expire_at"])

    # Extend comment fields.
    op.add_column(
        "comments",
        sa.Column("likes_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "comments",
        sa.Column("root_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "comments",
        sa.Column("reply_to_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "comments_root_id_fkey",
        "comments",
        "comments",
        ["root_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "comments_reply_to_user_id_fkey",
        "comments",
        "users",
        ["reply_to_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_comments_root_id", "comments", ["root_id"])
    op.create_index("ix_comments_reply_to_user_id", "comments", ["reply_to_user_id"])
    op.create_index(
        "idx_comments_post_root_parent",
        "comments",
        ["post_id", "root_id", "parent_id"],
    )
    op.execute(
        """
        WITH RECURSIVE comment_tree AS (
            SELECT id, parent_id, id AS root_comment_id
            FROM comments
            WHERE parent_id IS NULL
            UNION ALL
            SELECT c.id, c.parent_id, ct.root_comment_id
            FROM comments c
            JOIN comment_tree ct ON c.parent_id = ct.id
        )
        UPDATE comments c
        SET root_id = ct.root_comment_id
        FROM comment_tree ct
        WHERE c.id = ct.id
        """
    )
    op.execute(
        """
        UPDATE comments child
        SET reply_to_user_id = parent.user_id
        FROM comments parent
        WHERE child.parent_id = parent.id
          AND child.reply_to_user_id IS NULL
        """
    )

    # Favorites for posts.
    op.create_table(
        "post_favorites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "post_id", name="uq_post_favorites_user_post"),
    )
    op.create_index("ix_post_favorites_user_id", "post_favorites", ["user_id"])
    op.create_index("ix_post_favorites_post_id", "post_favorites", ["post_id"])

    # Likes for comments.
    op.create_table(
        "comment_likes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "comment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "comment_id", name="uq_comment_likes_user_comment"),
    )
    op.create_index("ix_comment_likes_user_id", "comment_likes", ["user_id"])
    op.create_index("ix_comment_likes_comment_id", "comment_likes", ["comment_id"])

    # Follow graph.
    op.create_table(
        "follows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "follower_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "followee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("follower_id <> followee_id", name="ck_follows_no_self_follow"),
        sa.UniqueConstraint("follower_id", "followee_id", name="uq_follows_follower_followee"),
    )
    op.create_index("ix_follows_follower_id", "follows", ["follower_id"])
    op.create_index("ix_follows_followee_id", "follows", ["followee_id"])

    # Conversations.
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_type",
            sa.String(length=20),
            server_default="direct",
            nullable=False,
        ),
        sa.Column("last_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_conversations_last_message_id", "conversations", ["last_message_id"])
    op.create_index("idx_conversations_last_message_at", "conversations", ["last_message_at"])

    op.create_table(
        "conversation_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_muted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_read_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "conversation_id",
            "user_id",
            name="uq_conversation_members_conversation_user",
        ),
    )
    op.create_index("ix_conversation_members_conversation_id", "conversation_members", ["conversation_id"])
    op.create_index("ix_conversation_members_user_id", "conversation_members", ["user_id"])
    op.create_index(
        "idx_conversation_members_user_pin_read",
        "conversation_members",
        ["user_id", "is_pinned", "last_read_message_id"],
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("message_type", sa.String(length=20), server_default="text", nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"])
    op.create_index(
        "idx_messages_conversation_created_at",
        "messages",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "message_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_url", sa.String(length=500), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_message_attachments_message_id", "message_attachments", ["message_id"])

    # Browsing history.
    op.create_table(
        "user_browsing_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "viewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "post_id", name="uq_user_browsing_history_user_post"),
    )
    op.create_index("ix_user_browsing_history_user_id", "user_browsing_history", ["user_id"])
    op.create_index("ix_user_browsing_history_post_id", "user_browsing_history", ["post_id"])
    op.create_index(
        "idx_user_browsing_history_user_viewed_at",
        "user_browsing_history",
        ["user_id", "viewed_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_user_browsing_history_user_viewed_at", table_name="user_browsing_history")
    op.drop_index("ix_user_browsing_history_post_id", table_name="user_browsing_history")
    op.drop_index("ix_user_browsing_history_user_id", table_name="user_browsing_history")
    op.drop_table("user_browsing_history")

    op.drop_index("ix_message_attachments_message_id", table_name="message_attachments")
    op.drop_table("message_attachments")

    op.drop_index("idx_messages_conversation_created_at", table_name="messages")
    op.drop_index("ix_messages_sender_id", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")

    op.drop_index(
        "idx_conversation_members_user_pin_read",
        table_name="conversation_members",
    )
    op.drop_index("ix_conversation_members_user_id", table_name="conversation_members")
    op.drop_index("ix_conversation_members_conversation_id", table_name="conversation_members")
    op.drop_table("conversation_members")

    op.drop_index("idx_conversations_last_message_at", table_name="conversations")
    op.drop_index("ix_conversations_last_message_id", table_name="conversations")
    op.drop_table("conversations")

    op.drop_index("ix_follows_followee_id", table_name="follows")
    op.drop_index("ix_follows_follower_id", table_name="follows")
    op.drop_table("follows")

    op.drop_index("ix_comment_likes_comment_id", table_name="comment_likes")
    op.drop_index("ix_comment_likes_user_id", table_name="comment_likes")
    op.drop_table("comment_likes")

    op.drop_index("ix_post_favorites_post_id", table_name="post_favorites")
    op.drop_index("ix_post_favorites_user_id", table_name="post_favorites")
    op.drop_table("post_favorites")

    op.drop_index("idx_comments_post_root_parent", table_name="comments")
    op.drop_index("ix_comments_reply_to_user_id", table_name="comments")
    op.drop_index("ix_comments_root_id", table_name="comments")
    op.drop_constraint("comments_reply_to_user_id_fkey", "comments", type_="foreignkey")
    op.drop_constraint("comments_root_id_fkey", "comments", type_="foreignkey")
    op.drop_column("comments", "reply_to_user_id")
    op.drop_column("comments", "root_id")
    op.drop_column("comments", "likes_count")

    op.drop_index("idx_posts_expire_at", table_name="posts")
    op.drop_column("posts", "favorites_count")
    op.drop_column("posts", "expire_at")
    op.drop_column("posts", "post_type")
    op.drop_column("posts", "title")

    op.drop_column("users", "birthday")
    op.drop_column("users", "gender")
    op.drop_column("users", "bio")

    op.drop_constraint("likes_user_id_fkey", "likes", type_="foreignkey")
    op.alter_column("likes", "user_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.create_foreign_key(
        "likes_user_id_fkey",
        "likes",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint("comments_user_id_fkey", "comments", type_="foreignkey")
    op.create_foreign_key(
        "comments_user_id_fkey",
        "comments",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("comments", "user_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)

    op.drop_constraint("posts_author_id_fkey", "posts", type_="foreignkey")
    op.create_foreign_key(
        "posts_author_id_fkey",
        "posts",
        "users",
        ["author_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("posts", "author_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
