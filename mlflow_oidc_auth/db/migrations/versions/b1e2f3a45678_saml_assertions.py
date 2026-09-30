"""saml assertions

Revision ID: b1e2f3a45678
Revises: a0d1e2f34567
Create Date: 2026-09-22 00:00:00.000000

Replay protection for SAML 2.0 SSO (issue #328): one row per accepted assertion ID, unique, kept
until the assertion expires. A new table only — no existing row is touched, so a deployment that
never configures a SAML provider is unaffected, and the downgrade is a plain drop.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b1e2f3a45678"
down_revision = "a0d1e2f34567"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saml_assertions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assertion_id", sa.String(length=255), nullable=False),
        sa.Column("provider_id", sa.String(length=255), nullable=False),
        # Naive UTC, like every other timestamp in this schema. The sweep deletes past it.
        sa.Column("not_on_or_after", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # The unique index is the replay check: a second insert of one assertion ID fails.
    op.create_index("ix_saml_assertions_assertion_id", "saml_assertions", ["assertion_id"], unique=True)
    op.create_index("ix_saml_assertions_not_on_or_after", "saml_assertions", ["not_on_or_after"])


def downgrade() -> None:
    op.drop_index("ix_saml_assertions_not_on_or_after", table_name="saml_assertions")
    op.drop_index("ix_saml_assertions_assertion_id", table_name="saml_assertions")
    op.drop_table("saml_assertions")
