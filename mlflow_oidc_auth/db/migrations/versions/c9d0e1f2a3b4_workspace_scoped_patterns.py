"""workspace-scoped resource patterns

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-30 23:00:00.000000

Resource patterns (regex grants on experiments, registered models and prompts, scorers and AI
Gateway resources) matched names in every workspace. Upgrade adds a ``workspace`` column to their
twelve user and group tables: the workspace a pattern applies in, or ``*`` for every workspace.
Every existing pattern gets ``*`` and keeps applying everywhere, so nothing changes on upgrade.
Each table's unique constraint is widened to include the column, so one pattern may be recorded
once per workspace.

Downgrade drops the column and restores the old constraints, under which a pattern applies in
every workspace. So that a downgrade never widens access, only patterns for every workspace are
kept; patterns recorded for one workspace are deleted and counted in the log. It never refuses.

``batch_alter_table`` because SQLite cannot change a table's constraints in place.
"""

import sqlalchemy as sa
from alembic import op

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

# revision identifiers, used by Alembic.
revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None

EVERY_WORKSPACE = "*"

#: (table, columns of the old unique constraint, old name, new name)
TABLES = (
    ("experiment_regex_permissions", ("regex", "user_id"), "unique_experiment_user_regex", "uq_experiment_user_regex_ws"),
    ("experiment_group_regex_permissions", ("regex", "group_id"), "unique_experiment_group_regex", "uq_experiment_group_regex_ws"),
    ("registered_model_regex_permissions", ("regex", "user_id", "prompt"), "unique_name_user_regex", "uq_name_user_regex_ws"),
    ("registered_model_group_regex_permissions", ("regex", "group_id", "prompt"), "unique_name_group_regex", "uq_name_group_regex_ws"),
    ("scorer_regex_permissions", ("regex", "user_id"), "unique_scorer_user_regex", "uq_scorer_user_regex_ws"),
    ("scorer_group_regex_permissions", ("regex", "group_id"), "unique_scorer_group_regex", "uq_scorer_group_regex_ws"),
    ("gateway_endpoint_regex_permissions", ("regex", "user_id"), "unique_endpoint_user_regex", "uq_endpoint_user_regex_ws"),
    ("gateway_endpoint_group_regex_permissions", ("regex", "group_id"), "unique_endpoint_group_regex", "uq_endpoint_group_regex_ws"),
    ("gateway_secret_regex_permissions", ("regex", "user_id"), "unique_secret_user_regex", "uq_secret_user_regex_ws"),
    ("gateway_secret_group_regex_permissions", ("regex", "group_id"), "unique_secret_group_regex", "uq_secret_group_regex_ws"),
    ("gateway_model_definition_regex_permissions", ("regex", "user_id"), "unique_model_def_user_regex", "uq_model_def_user_regex_ws"),
    ("gateway_model_definition_group_regex_permissions", ("regex", "group_id"), "unique_model_def_group_regex", "uq_model_def_group_regex_ws"),
)


def upgrade() -> None:
    for table, columns, old_unique, new_unique in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("workspace", sa.String(length=63), nullable=False, server_default=EVERY_WORKSPACE))
            batch_op.drop_constraint(old_unique, type_="unique")
            batch_op.create_unique_constraint(new_unique, [*columns, "workspace"])


def downgrade() -> None:
    connection = op.get_bind()
    removed = 0
    for table, columns, old_unique, new_unique in TABLES:
        t = sa.table(table, sa.column("workspace", sa.String))
        removed += connection.execute(t.delete().where(t.c.workspace != EVERY_WORKSPACE)).rowcount or 0
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(new_unique, type_="unique")
            batch_op.drop_column("workspace")
            batch_op.create_unique_constraint(old_unique, list(columns))
    if removed:
        logger.warning("workspace-scoped patterns downgrade: removed %d pattern(s) recorded for a single workspace", removed)
