"""add_prompt

Revision ID: 913635c83867
Revises: 4ab210836965
Create Date: 2025-03-27 20:36:22.505270

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "913635c83867"
down_revision = "4ab210836965"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("registered_model_group_permissions", sa.Column("prompt", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("registered_model_group_permissions", "prompt")
