"""add_quota

Revision ID: a1b2c3d4e5f6
Revises: 6a7b8c9def01
Create Date: 2026-03-11 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "6a7b8c9def01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_quotas",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("quota_bytes", sa.BigInteger(), nullable=True),
        sa.Column("used_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("soft_cap_fraction", sa.Float(), nullable=False, server_default="0.9"),
        sa.Column("last_reconciled_at", sa.DateTime(), nullable=True),
        sa.Column("soft_notified_at", sa.DateTime(), nullable=True),
        sa.Column("hard_blocked", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("email", sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_quota_user_id"),
        sa.UniqueConstraint("user_id", name="unique_user_quota"),
    )


def downgrade() -> None:
    op.drop_table("user_quotas")
