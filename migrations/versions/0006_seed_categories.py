"""Seed initial categories.

Revision ID: 0006_seed_categories
Revises: 0005_publication_foundation
Create Date: 2026-07-23
"""
# ruff: noqa: E501
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_seed_categories"
down_revision: str | Sequence[str] | None = "0005_publication_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    categories = sa.table("categories", sa.column("slug", sa.String))
    op.bulk_insert(categories, [{"slug": slug} for slug in ("reviews", "news", "guides", "esports")])


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM categories WHERE slug IN ('reviews', 'news', 'guides', 'esports')"))
