"""add user tokens

Revision ID: a1b2c3d4e5f6
Revises: 3c3272527ade
Create Date: 2026-01-21 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "3c3272527ade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_tokens",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_token_user_id"),
        sa.UniqueConstraint("user_id", "name", name="unique_user_token_name"),
    )


def downgrade() -> None:
    op.drop_table("user_tokens")
