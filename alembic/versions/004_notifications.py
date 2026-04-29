"""Add activity notifications.

Revision ID: 004_notifications
Revises: 003_make_post_expire_at_index_partial
Create Date: 2026-04-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "004_notifications"
down_revision: Union[str, None] = "003_make_post_expire_at_index_partial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recipient_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "comment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("target_preview", sa.Text(), server_default="", nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_notifications_recipient_user_id", "notifications", ["recipient_user_id"])
    op.create_index("ix_notifications_actor_user_id", "notifications", ["actor_user_id"])
    op.create_index("ix_notifications_post_id", "notifications", ["post_id"])
    op.create_index("ix_notifications_comment_id", "notifications", ["comment_id"])
    op.create_index("ix_notifications_read_at", "notifications", ["read_at"])
    op.create_index(
        "idx_notifications_recipient_created",
        "notifications",
        ["recipient_user_id", "created_at"],
    )
    op.create_index(
        "idx_notifications_recipient_unread",
        "notifications",
        ["recipient_user_id", "read_at"],
    )
    op.create_index(
        "uq_notifications_post_like",
        "notifications",
        ["recipient_user_id", "actor_user_id", "type", "post_id"],
        unique=True,
        postgresql_where=sa.text("type = 'post_like'"),
    )


def downgrade() -> None:
    op.drop_index("uq_notifications_post_like", table_name="notifications")
    op.drop_index("idx_notifications_recipient_unread", table_name="notifications")
    op.drop_index("idx_notifications_recipient_created", table_name="notifications")
    op.drop_index("ix_notifications_read_at", table_name="notifications")
    op.drop_index("ix_notifications_comment_id", table_name="notifications")
    op.drop_index("ix_notifications_post_id", table_name="notifications")
    op.drop_index("ix_notifications_actor_user_id", table_name="notifications")
    op.drop_index("ix_notifications_recipient_user_id", table_name="notifications")
    op.drop_table("notifications")
