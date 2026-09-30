"""add_service_accounts

Revision ID: 8c1cf75c5314
Revises: 913635c83867
Create Date: 2025-04-17 12:04:03.949749

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "8c1cf75c5314"
down_revision = "913635c83867"
branch_labels = None
depends_on = None


# Lightweight table view used only to build dialect-portable UPDATE/DELETE statements below.
# A raw "= TRUE"/"= FALSE" literal is valid on SQLite and PostgreSQL but not on SQL Server,
# which has no boolean literal keywords; going through SQLAlchemy Core lets each backend's
# dialect render the bound value the way it expects (BIT 0/1, PostgreSQL true/false, ...).
users_table = sa.table("users", sa.column("is_service_account", sa.Boolean()))


def upgrade() -> None:
    op.add_column("users", sa.Column("is_service_account", sa.Boolean(), nullable=True))
    op.execute(users_table.update().values(is_service_account=False))


def downgrade() -> None:
    op.execute(users_table.delete().where(users_table.c.is_service_account == True))  # noqa: E712
    op.drop_column("users", "is_service_account")
