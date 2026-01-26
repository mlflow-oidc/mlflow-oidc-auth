"""add_group_permissions

Revision ID: 4ab210836965
Revises: 2d5d40dd803f
Create Date: 2024-04-30 10:01:10.515598

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "4ab210836965"
down_revision = "2d5d40dd803f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registered_model_group_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_group_id_registered_model_group_permissions"),
        sa.UniqueConstraint("name", "group_id", name="unique_name_group"),
    )
    op.create_table(
        "experiment_group_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("experiment_id", sa.String(length=255), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_group_id_experiment_group_permissions"),
        sa.UniqueConstraint("experiment_id", "group_id", name="unique_experiment_group"),
    )


def downgrade() -> None:
    op.drop_table("experiment_group_permissions")
    op.drop_table("registered_model_group_permissions")
