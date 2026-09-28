"""group ownership

Revision ID: e4f5a6b7c8d9
Revises: b1e2f3a45678
Create Date: 2026-09-23 00:00:00.000000

Records which source created each group (``groups.managed_by``), so SCIM may be limited to the
groups it owns (#323). Every existing row becomes ``manual`` through the server default — the
same label every pre-existing user and membership got in Phase 0 — so a deployment that changes
no configuration sees no change. The downgrade drops the column and nothing else.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e4f5a6b7c8d9"
down_revision = "b1e2f3a45678"
branch_labels = None
depends_on = None

MANUAL = "manual"


def upgrade() -> None:
    op.add_column("groups", sa.Column("managed_by", sa.String(length=255), nullable=False, server_default=MANUAL))


def downgrade() -> None:
    op.drop_column("groups", "managed_by")
