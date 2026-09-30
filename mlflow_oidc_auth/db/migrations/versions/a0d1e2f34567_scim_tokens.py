"""scim tokens

Revision ID: a0d1e2f34567
Revises: 9c0d1e2f3456
Create Date: 2026-09-22 00:00:00.000000

Dedicated bearer tokens for the SCIM 2.0 endpoint (issue #321). A new table only: no existing
row is touched, so a deployment that never issues a SCIM token is unaffected, and the
downgrade is a plain drop.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a0d1e2f34567"
down_revision = "9c0d1e2f3456"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scim_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        # Werkzeug hash string, method-prefixed, so a later change of method keeps verifying.
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        # Random, non-secret lookup handle embedded in the token itself.
        sa.Column("token_prefix", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_scim_tokens_name"),
    )
    op.create_index("ix_scim_tokens_token_prefix", "scim_tokens", ["token_prefix"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_scim_tokens_token_prefix", table_name="scim_tokens")
    op.drop_table("scim_tokens")
