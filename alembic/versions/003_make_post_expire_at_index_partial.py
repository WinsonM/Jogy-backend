"""Make posts.expire_at index partial.

Revision ID: 003_make_post_expire_at_index_partial
Revises: 002_social_graph_messaging
Create Date: 2026-04-27
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_make_post_expire_at_index_partial"
down_revision: Union[str, None] = "002_social_graph_messaging"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("idx_posts_expire_at", table_name="posts")
    op.create_index(
        "idx_posts_expire_at",
        "posts",
        ["expire_at"],
        postgresql_where=sa.text("expire_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_posts_expire_at", table_name="posts")
    op.create_index("idx_posts_expire_at", "posts", ["expire_at"])
