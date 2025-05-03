"""add_regex_permissions

Revision ID: 1ddf23934b63
Revises: 8c1cf75c5314
Create Date: 2025-04-22 14:09:04.425567

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1ddf23934b63"
down_revision = "8c1cf75c5314"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registered_model_group_regex_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("regex", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.Column("prompt", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_group_id_registered_model_group_regex_permissions"),
        sa.UniqueConstraint("regex", "group_id", name="unique_name_group_regex"),
    )
    op.create_table(
        "experiment_group_regex_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("regex", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_group_id_experiment_group_regex_permissions"),
        sa.UniqueConstraint("regex", "group_id", name="unique_experiment_group_regex"),
    )
    op.create_table(
        "registered_model_regex_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("regex", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.Column("prompt", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_id_registered_model_regex_permissions"),
        sa.UniqueConstraint("regex", "user_id", name="unique_name_user_regex"),
    )
    op.create_table(
        "experiment_regex_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("regex", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_id_experiment_regex_permissions"),
        sa.UniqueConstraint("regex", "user_id", name="unique_experiment_user_regex"),
    )


def downgrade() -> None:
    op.drop_table("experiment_regex_permissions")
    op.drop_table("registered_model_regex_permissions")
    op.drop_table("experiment_group_regex_permissions")
    op.drop_table("registered_model_group_regex_permissions")
