"""add_workspace_permissions

Revision ID: 7b8c9d0ef123
Revises: 6a7b8c9def01
Create Date: 2026-03-23 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "7b8c9d0ef123"
down_revision = "6a7b8c9def01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_permissions",
        sa.Column("workspace", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_workspace_perm_user_id"
        ),
        sa.PrimaryKeyConstraint(
            "workspace", "user_id", name="pk_workspace_permissions"
        ),
    )

    op.create_table(
        "workspace_group_permissions",
        sa.Column("workspace", sa.String(length=255), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"], ["groups.id"], name="fk_workspace_group_perm_group_id"
        ),
        sa.PrimaryKeyConstraint(
            "workspace", "group_id", name="pk_workspace_group_permissions"
        ),
    )


def downgrade() -> None:
    op.drop_table("workspace_group_permissions")
    op.drop_table("workspace_permissions")
