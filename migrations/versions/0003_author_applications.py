"""Create author applications.

Revision ID: 0003_author_applications
Revises: 0002_user_sessions
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_author_applications"
down_revision: str | Sequence[str] | None = "0002_user_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "author_applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("motivation", sa.String(length=2000), nullable=False),
        sa.Column("portfolio_url", sa.String(length=2048)),
        sa.Column("status", sa.String(length=20), server_default="submitted", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_author_applications_user_id", "author_applications", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_author_applications_user_id", table_name="author_applications")
    op.drop_table("author_applications")
