"""Add GIF and sticker media to comments.

Revision ID: 0031_comment_media
Revises: 0030_journal_layout
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031_comment_media"
down_revision: str | Sequence[str] | None = "0030_journal_layout"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("publication_comments", sa.Column("media_kind", sa.String(20), nullable=True))
    op.add_column("publication_comments", sa.Column("media_value", sa.String(2000), nullable=True))


def downgrade() -> None:
    op.drop_column("publication_comments", "media_value")
    op.drop_column("publication_comments", "media_kind")
