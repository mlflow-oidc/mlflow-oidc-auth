"""Who wrote each MLflow 3.18 issue-detection schedule, for the schedule guard.

MLflow's scheduler runs a stored schedule (the ``mlflow.issueDetection.schedule`` experiment tag)
with no identity, so revoking its writer's access does not stop it. The plugin records the writer
when the tag is written and ``mlflow_oidc_auth.issue_detection_guard`` pauses any schedule
whose writer could no longer write it. One row per experiment.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base


class SqlIssueDetectionScheduleAuthor(Base):
    """The last writer of an experiment's detection schedule, and the guard's last pause of it.

    ``author`` is a username, not a foreign key: a deleted user must leave the row behind so the
    guard can see the schedule's writer is gone. It is empty on a row the guard created for a
    schedule nobody was recorded writing (one written before the plugin recorded writers).
    ``model_fingerprint`` identifies the model the writer stored, so a schedule whose model no
    longer matches is not credited to them.
    """

    __tablename__ = "issue_detection_schedule_authors"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    guard_paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(), nullable=True)
    guard_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    __table_args__ = (UniqueConstraint("experiment_id", name="uq_issue_detection_schedule_authors_experiment"),)
