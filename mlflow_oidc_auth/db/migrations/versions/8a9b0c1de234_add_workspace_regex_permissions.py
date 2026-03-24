"""add_workspace_regex_permissions

Revision ID: 8a9b0c1de234
Revises: 7b8c9d0ef123
Create Date: 2026-03-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "8a9b0c1de234"
down_revision = "7b8c9d0ef123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_regex_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("regex", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_workspace_regex_perm_user_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("regex", "user_id", name="uq_workspace_regex_user"),
    )

    op.create_table(
        "workspace_group_regex_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("regex", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"], ["groups.id"], name="fk_workspace_group_regex_perm_group_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("regex", "group_id", name="uq_workspace_regex_group"),
    )


def downgrade() -> None:
    op.drop_table("workspace_group_regex_permissions")
    op.drop_table("workspace_regex_permissions")
