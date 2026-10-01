"""mcp server permissions

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-30 21:00:00.000000

Adds the user and group grant tables for MLflow's MCP server registry. MLflow keeps MCP servers
unique per ``(workspace, name)``, so — like the workspace-scoped grant tables of
``b8c9d0e1f2a3`` — each grant records the workspace of the server it names, and the unique
constraint is ``(workspace, name, principal)``. The column is nullable only so the shared
workspace-scoped grant code treats these tables like the others; the plugin always writes it.

There are no regex tables: MCP server permissions resolve from user and group grants, then the
caller's workspace permission.

Downgrade drops both tables and every grant in them. MCP server access then reverts to what the
previous release enforces (registry writes admin-only), so a downgrade never widens access.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_server_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.Column("workspace", sa.String(length=63), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_mcp_server_perm_user_id"),
        sa.UniqueConstraint("workspace", "name", "user_id", name="uq_mcp_server_perm_workspace_name_user"),
    )
    op.create_table(
        "mcp_server_group_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.Column("workspace", sa.String(length=63), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_mcp_server_group_perm_group_id"),
        sa.UniqueConstraint("workspace", "name", "group_id", name="uq_mcp_server_group_perm_workspace_name_group"),
    )


def downgrade() -> None:
    op.drop_table("mcp_server_group_permissions")
    op.drop_table("mcp_server_permissions")
