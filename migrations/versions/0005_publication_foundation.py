"""Create publication foundation.

Revision ID: 0005_publication_foundation
Revises: 0004_review_author_applications
Create Date: 2026-07-23
"""
# ruff: noqa: E501
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_publication_foundation"
down_revision: str | Sequence[str] | None = "0004_review_author_applications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
def upgrade() -> None:
    op.create_table("categories", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("slug", sa.String(length=80), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("slug"))
    op.create_table("publications", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("source_locale", sa.String(length=5), nullable=False), sa.Column("status", sa.String(length=30), server_default="draft", nullable=False), sa.Column("published_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_publications_author_id", "publications", ["author_id"])
    op.create_index("ix_publications_category_id", "publications", ["category_id"])
    op.create_table("publication_localizations", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("publication_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("locale", sa.String(length=5), nullable=False), sa.Column("title", sa.String(length=240), nullable=False), sa.Column("summary", sa.String(length=500), nullable=False), sa.Column("body", sa.Text(), nullable=False), sa.Column("origin", sa.String(length=20), server_default="original", nullable=False), sa.Column("source_revision", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.ForeignKeyConstraint(["publication_id"], ["publications.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("publication_id", "locale"))
    op.create_index("ix_publication_localizations_publication_id", "publication_localizations", ["publication_id"])
def downgrade() -> None:
    op.drop_table("publication_localizations")
    op.drop_table("publications")
    op.drop_table("categories")
