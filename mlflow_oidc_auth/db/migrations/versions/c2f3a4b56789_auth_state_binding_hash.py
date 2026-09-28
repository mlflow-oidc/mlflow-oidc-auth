"""auth state binding hash

Revision ID: c2f3a4b56789
Revises: e4f5a6b7c8d9
Create Date: 2026-09-23 00:00:00.000000

Binds a SAML login to the browser that started it (issue #374): ``auth_state`` gains a nullable
``binding_hash`` — the SHA-256 of the nonce set in a cookie on ``/login``, compared on the ACS.
Nullable, so every existing row (and every OIDC attempt, which never sets it) is unaffected, and
the downgrade is a plain column drop. ``batch_alter_table`` because SQLite cannot drop a column
in place on every version the plugin supports.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c2f3a4b56789"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("auth_state") as batch_op:
        batch_op.add_column(sa.Column("binding_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("auth_state") as batch_op:
        batch_op.drop_column("binding_hash")
