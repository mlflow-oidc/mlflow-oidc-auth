"""token expiration

Revision ID: 0565cf04c12e
Revises: 1ddf23934b63
Create Date: 2025-05-22 23:41:23.392286

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0565cf04c12e"
down_revision = "1ddf23934b63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_expiration", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column(
        "users",
        "password_expiration",
    )
