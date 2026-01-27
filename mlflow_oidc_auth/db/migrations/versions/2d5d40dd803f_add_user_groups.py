"""add_user_groups

Revision ID: 2d5d40dd803f
Revises: 8606fa83a998
Create Date: 2024-04-29 20:26:21.803801

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "2d5d40dd803f"
down_revision = "8606fa83a998"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("group_name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("group_name"),
    )
    op.create_table(
        "user_groups",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_id_user_groups"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_group_id_user_groups"),
        sa.UniqueConstraint("user_id", "group_id", name="unique_user_group"),
    )


def downgrade() -> None:
    op.drop_table("user_groups")
    op.drop_table("groups")
