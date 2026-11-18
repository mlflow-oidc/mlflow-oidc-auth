"""skill permissions

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-11-16 12:00:00.000000

Adds the user and group grant tables for MLflow's skill registry (MLflow 3.18+). MLflow keeps
skills unique per ``(workspace, organization, name)``; a grant names a skill by its key — the bare
name, or ``@<organization>/<name>`` — and, like the MCP server grant tables of ``d0e1f2a3b4c5``,
records the workspace of the skill it names, with ``(workspace, name, principal)`` unique. The
column is nullable only so the shared workspace-scoped grant code treats these tables like the
others; the plugin always writes it.

There are no regex tables: skill permissions resolve from user and group grants, then the caller's
workspace permission.

Downgrade drops both tables and every grant in them. The previous release does not serve the skill
registry at all, so a downgrade never widens access.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skill_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.Column("workspace", sa.String(length=63), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_skill_perm_user_id"),
        sa.UniqueConstraint("workspace", "name", "user_id", name="uq_skill_perm_workspace_name_user"),
    )
    op.create_table(
        "skill_group_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.Column("workspace", sa.String(length=63), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_skill_group_perm_group_id"),
        sa.UniqueConstraint("workspace", "name", "group_id", name="uq_skill_group_perm_workspace_name_group"),
    )


def downgrade() -> None:
    op.drop_table("skill_group_permissions")
    op.drop_table("skill_permissions")
