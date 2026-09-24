"""scim activity

Revision ID: d3a4b5c6e7f8
Revises: c2f3a4b56789
Create Date: 2026-09-23 12:00:00.000000

A log of ``/scim/v2`` requests for the admin UI's provisioning status (issue #325): one row per
request, swept after ``SCIM_ACTIVITY_RETENTION_DAYS``. A new table only — nothing existing is
touched, a deployment that never issues a SCIM token never writes a row, and the downgrade is a
plain drop.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d3a4b5c6e7f8"
down_revision = "c2f3a4b56789"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scim_activity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        # Not a foreign key: the row names its token by id and by a snapshot of its name.
        sa.Column("token_id", sa.Integer(), nullable=True),
        sa.Column("token_name", sa.String(length=255), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=False),
        # The route template, e.g. "/Users/{user_id}" — never the concrete path.
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scim_activity_at", "scim_activity", ["at"])
    op.create_index("ix_scim_activity_token_id_at", "scim_activity", ["token_id", "at"])


def downgrade() -> None:
    op.drop_index("ix_scim_activity_token_id_at", table_name="scim_activity")
    op.drop_index("ix_scim_activity_at", table_name="scim_activity")
    op.drop_table("scim_activity")
