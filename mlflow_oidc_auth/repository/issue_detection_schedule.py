"""Recorded writers of MLflow 3.18 issue-detection schedules (see ``mlflow_oidc_auth.issue_detection_guard``)."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlIssueDetectionScheduleAuthor


def _now() -> datetime:
    """Naive UTC, matching how every other timestamp in this schema is stored."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


@dataclass(frozen=True)
class ScheduleAuthorRecord:
    """One experiment's recorded schedule writer and the guard's last pause of its schedule."""

    experiment_id: str
    workspace: Optional[str]
    author: Optional[str]
    model_fingerprint: Optional[str]
    recorded_at: datetime
    guard_paused_at: Optional[datetime]
    guard_reason: Optional[str]

    def to_json(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "workspace": self.workspace,
            "author": self.author,
            "recorded_at": _iso(self.recorded_at),
            "guard_paused_at": _iso(self.guard_paused_at),
            "guard_reason": self.guard_reason,
        }


def _record(row: SqlIssueDetectionScheduleAuthor) -> ScheduleAuthorRecord:
    return ScheduleAuthorRecord(
        experiment_id=row.experiment_id,
        workspace=row.workspace,
        author=row.author,
        model_fingerprint=row.model_fingerprint,
        recorded_at=row.recorded_at,
        guard_paused_at=row.guard_paused_at,
        guard_reason=row.guard_reason,
    )


class IssueDetectionScheduleRepository:
    def __init__(self, session_maker: Callable[[], Session]):
        self._Session = session_maker

    def _row(self, session: Session, experiment_id: str) -> Optional[SqlIssueDetectionScheduleAuthor]:
        return session.query(SqlIssueDetectionScheduleAuthor).filter(SqlIssueDetectionScheduleAuthor.experiment_id == str(experiment_id)).one_or_none()

    def record_author(self, experiment_id: str, workspace: Optional[str], author: str, model_fingerprint: str) -> None:
        """Credit the schedule now stored on ``experiment_id`` to ``author``, clearing any guard pause."""
        with self._Session(read_only=False) as session:
            row = self._row(session, experiment_id)
            if row is None:
                row = SqlIssueDetectionScheduleAuthor(experiment_id=str(experiment_id))
                session.add(row)
            row.workspace = workspace
            row.author = author
            row.model_fingerprint = model_fingerprint
            row.recorded_at = _now()
            row.guard_paused_at = None
            row.guard_reason = None
            session.flush()

    def mark_guard_paused(self, experiment_id: str, workspace: Optional[str], reason: str) -> None:
        """Note that the guard paused the schedule on ``experiment_id``, keeping its recorded writer."""
        with self._Session(read_only=False) as session:
            row = self._row(session, experiment_id)
            now = _now()
            if row is None:
                row = SqlIssueDetectionScheduleAuthor(experiment_id=str(experiment_id), workspace=workspace, recorded_at=now)
                session.add(row)
            row.guard_paused_at = now
            row.guard_reason = reason
            session.flush()

    def get(self, experiment_id: str) -> Optional[ScheduleAuthorRecord]:
        with self._Session() as session:
            row = self._row(session, experiment_id)
            return _record(row) if row is not None else None

    def list(self) -> List[ScheduleAuthorRecord]:
        with self._Session() as session:
            rows = session.query(SqlIssueDetectionScheduleAuthor).order_by(SqlIssueDetectionScheduleAuthor.experiment_id).all()
            return [_record(row) for row in rows]

    def delete(self, experiment_id: str) -> None:
        with self._Session(read_only=False) as session:
            session.query(SqlIssueDetectionScheduleAuthor).filter(SqlIssueDetectionScheduleAuthor.experiment_id == str(experiment_id)).delete()
            session.flush()
