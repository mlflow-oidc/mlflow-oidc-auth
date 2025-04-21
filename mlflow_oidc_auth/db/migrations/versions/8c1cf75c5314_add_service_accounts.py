"""add_service_accounts

Revision ID: 8c1cf75c5314
Revises: 913635c83867
Create Date: 2025-04-17 12:04:03.949749

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8c1cf75c5314"
down_revision = "913635c83867"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_service_account", sa.Boolean(), nullable=True))
    op.execute("UPDATE users SET is_service_account = FALSE")


def downgrade() -> None:
    op.execute("DELETE FROM users WHERE is_service_account = TRUE")
    op.drop_column("users", "is_service_account")
