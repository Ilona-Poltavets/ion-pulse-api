"""Add author application review fields.

Revision ID: 0004_review_author_applications
Revises: 0003_author_applications
Create Date: 2026-07-23
"""
# ruff: noqa: E501
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_review_author_applications"
down_revision: str | Sequence[str] | None = "0003_author_applications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.add_column("author_applications", sa.Column("review_note", sa.String(length=1000)))
    op.add_column("author_applications", sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.add_column("author_applications", sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key("fk_author_applications_reviewer", "author_applications", "users", ["reviewed_by_user_id"], ["id"], ondelete="SET NULL")

def downgrade() -> None:
    op.drop_constraint("fk_author_applications_reviewer", "author_applications", type_="foreignkey")
    op.drop_column("author_applications", "reviewed_by_user_id")
    op.drop_column("author_applications", "reviewed_at")
    op.drop_column("author_applications", "review_note")
