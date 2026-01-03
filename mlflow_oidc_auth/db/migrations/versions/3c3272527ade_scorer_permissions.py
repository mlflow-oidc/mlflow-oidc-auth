"""scorer permissions

Revision ID: 3c3272527ade
Revises: 0565cf04c12e
Create Date: 2026-01-02 23:22:08.199671

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3c3272527ade"
down_revision = "0565cf04c12e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Upstream MLflow adds only the user-scoped table `scorer_permissions`.
    # This project also supports group + regex-based scorer permissions, so we
    # create those additional tables here.

    op.create_table(
        "scorer_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("experiment_id", sa.String(length=255), nullable=False),
        sa.Column("scorer_name", sa.String(length=256), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_scorer_perm_user_id"),
        sa.UniqueConstraint("experiment_id", "scorer_name", "user_id", name="unique_scorer_user"),
    )

    op.create_table(
        "scorer_group_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("experiment_id", sa.String(length=255), nullable=False),
        sa.Column("scorer_name", sa.String(length=256), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_scorer_group_perm_group_id"),
        sa.UniqueConstraint("experiment_id", "scorer_name", "group_id", name="unique_scorer_group"),
    )

    op.create_table(
        "scorer_regex_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("regex", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_scorer_regex_perm_user_id"),
        sa.UniqueConstraint("regex", "user_id", name="unique_scorer_user_regex"),
    )

    op.create_table(
        "scorer_group_regex_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("regex", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_scorer_group_regex_perm_group_id"),
        sa.UniqueConstraint("regex", "group_id", name="unique_scorer_group_regex"),
    )


def downgrade() -> None:
    # Drop in reverse order of creation.
    op.drop_table("scorer_group_regex_permissions")
    op.drop_table("scorer_regex_permissions")
    op.drop_table("scorer_group_permissions")
    op.drop_table("scorer_permissions")
