"""workspace-scoped resource grants

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-30 18:00:00.000000

MLflow keeps registered models (prompts included), gateway endpoints, gateway secrets and gateway
model definitions unique per ``(workspace, name)``, but the grants on them were keyed by name
alone, so a grant on one workspace's resource applied to every workspace's resource of that name.

Upgrade adds a nullable ``workspace`` column to the eight user and group grant tables of those
resources and widens each table's unique constraint to include it. Existing grants keep
``workspace IS NULL``: the auth database does not know which workspace a name belongs to, so the
application assigns one at startup (``mlflow_oidc_auth.grant_workspace_backfill``), where MLflow's
stores are available. Until then, with workspaces enabled, such a grant matches nothing; with
workspaces disabled nothing is filtered, so a deployment that never enabled workspaces is unaffected.

Downgrade drops the column and restores the name-only unique constraints, under which a grant
applies to every workspace's resource of that name — the old release's behaviour, which a
downgrade brings back for the grants it keeps. Only grants of the ``default`` workspace (and
unassigned ones) are kept; grants recorded for any other workspace are deleted and counted in the
log, so a grant made for one tenant's resource is not handed every tenant's. A kept ``default``
grant does again reach same-named resources in other workspaces. A deployment that never enabled
workspaces has only ``default`` grants and loses nothing. The downgrade never refuses.

``batch_alter_table`` because SQLite cannot change a table's constraints in place: it rebuilds the
table from the reflected schema; on PostgreSQL these are plain ALTERs.
"""

import sqlalchemy as sa
from alembic import op

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

# revision identifiers, used by Alembic.
revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None

#: (table, resource column, principal column, old unique constraint, new unique constraint)
TABLES = (
    ("registered_model_permissions", "name", "user_id", "unique_name_user", "uq_rm_perm_workspace_name_user"),
    ("registered_model_group_permissions", "name", "group_id", "unique_name_group", "uq_rm_group_perm_workspace_name_group"),
    ("gateway_endpoint_permissions", "endpoint_id", "user_id", "unique_endpoint_user", "uq_gw_endpoint_perm_workspace_user"),
    ("gateway_endpoint_group_permissions", "endpoint_id", "group_id", "unique_endpoint_group", "uq_gw_endpoint_group_perm_workspace_group"),
    ("gateway_secret_permissions", "secret_id", "user_id", "unique_secret_user", "uq_gw_secret_perm_workspace_user"),
    ("gateway_secret_group_permissions", "secret_id", "group_id", "unique_secret_group", "uq_gw_secret_group_perm_workspace_group"),
    ("gateway_model_definition_permissions", "model_definition_id", "user_id", "unique_model_def_user", "uq_gw_model_def_perm_workspace_user"),
    (
        "gateway_model_definition_group_permissions",
        "model_definition_id",
        "group_id",
        "unique_model_def_group",
        "uq_gw_model_def_group_perm_workspace_group",
    ),
)

DEFAULT_WORKSPACE = "default"


def upgrade() -> None:
    for table, resource, principal, old_unique, new_unique in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("workspace", sa.String(length=63), nullable=True))
            batch_op.drop_constraint(old_unique, type_="unique")
            batch_op.create_unique_constraint(new_unique, ["workspace", resource, principal])


def _collapse(connection, table: str, resource: str, principal: str) -> int:
    """Leave at most one grant per (resource, principal), never one from a non-default workspace.

    Deletes every grant recorded for a workspace other than ``default``, then any unassigned grant
    that duplicates a ``default`` one, then all but the oldest of unassigned grants that duplicate
    one another. Returns how many rows were deleted.
    """
    t = sa.table(table, sa.column("id", sa.Integer), sa.column(resource, sa.String), sa.column(principal, sa.Integer), sa.column("workspace", sa.String))
    removed = connection.execute(t.delete().where(t.c.workspace.isnot(None), t.c.workspace != DEFAULT_WORKSPACE)).rowcount or 0
    kept = sa.alias(t, "kept")
    duplicate = sa.exists().where(kept.c[resource] == t.c[resource], kept.c[principal] == t.c[principal], kept.c.workspace == DEFAULT_WORKSPACE)
    removed += connection.execute(t.delete().where(t.c.workspace.is_(None), duplicate)).rowcount or 0
    # Unassigned grants that duplicate one another (a rolling upgrade can write those): keep the
    # oldest of each, so the name-only constraint can be restored.
    oldest = sa.select(sa.func.min(t.c.id)).where(t.c.workspace.is_(None)).group_by(t.c[resource], t.c[principal])
    removed += connection.execute(t.delete().where(t.c.workspace.is_(None), t.c.id.not_in(oldest.scalar_subquery()))).rowcount or 0
    return removed


def downgrade() -> None:
    connection = op.get_bind()
    removed = 0
    for table, resource, principal, old_unique, new_unique in TABLES:
        removed += _collapse(connection, table, resource, principal)
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(new_unique, type_="unique")
            batch_op.drop_column("workspace")
            batch_op.create_unique_constraint(old_unique, [resource, principal])
    if removed:
        logger.warning("workspace-scoped grants downgrade: removed %d grant(s) recorded for a workspace other than default", removed)
