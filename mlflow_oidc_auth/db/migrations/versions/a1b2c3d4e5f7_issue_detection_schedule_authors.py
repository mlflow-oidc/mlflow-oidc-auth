"""issue detection schedule authors

Revision ID: a1b2c3d4e5f7
Revises: f2a3b4c5d6e7
Create Date: 2026-11-18 12:00:00.000000

Records who wrote each MLflow 3.18 issue-detection schedule, so the schedule guard can pause one
whose writer lost the access it needed. A new table only: nothing existing is touched, nothing is
backfilled (a schedule written before this has no recorded writer, which the guard treats as
unknown rather than inventing one), and the downgrade is a plain drop.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "issue_detection_schedule_authors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("experiment_id", sa.String(length=64), nullable=False),
        sa.Column("workspace", sa.String(length=255), nullable=True),
        # A username, not a foreign key: a deleted writer must leave the row for the guard to see.
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("model_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("guard_paused_at", sa.DateTime(), nullable=True),
        sa.Column("guard_reason", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id", name="uq_issue_detection_schedule_authors_experiment"),
    )


def downgrade() -> None:
    op.drop_table("issue_detection_schedule_authors")
