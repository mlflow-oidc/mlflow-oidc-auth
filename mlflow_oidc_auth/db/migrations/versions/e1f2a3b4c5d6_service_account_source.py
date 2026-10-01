"""service account sign-in source

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-10-01 12:00:00.000000

A service account now says how it signs in (``users.service_account_source``): ``internal`` — only
with access tokens this plugin issues — or the id of the one provider whose tokens it accepts. A
person's account carries NULL.

Upgrade makes every existing service account ``internal``, so an IdP token that used to reach one by
naming it no longer does — a deliberate, breaking change: an administrator re-points each account
that a workload reaches with an IdP token to that provider. Kubernetes service accounts, which this
plugin creates for a cluster provider and reaches on their own path, are recorded as
``kubernetes`` rather than ``internal``.

Downgrade drops the column.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None

KUBERNETES_SUFFIX = "@serviceaccount.cluster.local"


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("service_account_source", sa.String(length=255), nullable=True))
    users = sa.table("users", sa.column("username", sa.String), sa.column("is_service_account", sa.Boolean), sa.column("service_account_source", sa.String))
    connection = op.get_bind()
    connection.execute(
        users.update()
        .where(users.c.is_service_account == sa.true(), users.c.username.like(f"%{KUBERNETES_SUFFIX}"))
        .values(service_account_source="kubernetes")
    )
    connection.execute(
        users.update().where(users.c.is_service_account == sa.true(), users.c.service_account_source.is_(None)).values(service_account_source="internal")
    )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("service_account_source")
