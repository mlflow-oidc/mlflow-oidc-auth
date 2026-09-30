"""workspace group rules

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-30 12:00:00.000000

Admin-managed rules that attach a group to a workspace by the group's name (issue #418).

Upgrade:

* creates ``workspace_group_rules``;
* adds a nullable ``rule_id`` to ``workspace_group_permissions``, a foreign key to the rule that
  created the grant. Every existing grant keeps ``rule_id IS NULL``: it was made by hand, and a
  rule never touches a manual grant.

Downgrade deletes the grants rules created first — without the column they would read as manual
grants nobody made — then drops the column and the table. The count is logged. It never refuses.

``batch_alter_table`` because SQLite cannot add a foreign key to an existing table in place: it
rebuilds the table from the reflected schema, so the composite primary key and the group foreign
key survive; on PostgreSQL it is a plain ALTER.
"""

import sqlalchemy as sa
from alembic import op

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

# revision identifiers, used by Alembic.
revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None

_grants = sa.table("workspace_group_permissions", sa.column("rule_id", sa.Integer))


def upgrade() -> None:
    op.create_table(
        "workspace_group_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("pattern", sa.String(length=256), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_workspace_group_rules_name"),
    )
    with op.batch_alter_table("workspace_group_permissions") as batch_op:
        batch_op.add_column(sa.Column("rule_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_workspace_group_permissions_rule_id", "workspace_group_rules", ["rule_id"], ["id"])
        batch_op.create_index("ix_workspace_group_permissions_rule_id", ["rule_id"])


def downgrade() -> None:
    connection = op.get_bind()
    removed = connection.execute(_grants.delete().where(_grants.c.rule_id.isnot(None))).rowcount
    if removed:
        logger.warning("workspace_group_rules downgrade: removed %d grant(s) created by rules", removed)

    with op.batch_alter_table("workspace_group_permissions") as batch_op:
        batch_op.drop_index("ix_workspace_group_permissions_rule_id")
        batch_op.drop_constraint("fk_workspace_group_permissions_rule_id", type_="foreignkey")
        batch_op.drop_column("rule_id")

    op.drop_table("workspace_group_rules")
