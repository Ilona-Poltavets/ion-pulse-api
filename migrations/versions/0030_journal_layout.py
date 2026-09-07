"""Monthly magazine layouts and publication views."""

import sqlalchemy as sa
from alembic import op

revision = "0030_journal_layout"
down_revision = "0029_user_role_audit"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "journal_issues", sa.Column("pages", sa.JSON(), nullable=False, server_default="[]")
    )
    op.add_column(
        "publications", sa.Column("view_count", sa.Integer(), nullable=False, server_default="0")
    )


def downgrade():
    op.drop_column("publications", "view_count")
    op.drop_column("journal_issues", "pages")
