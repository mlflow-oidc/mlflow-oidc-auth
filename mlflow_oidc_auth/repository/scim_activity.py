"""The ``/scim/v2`` request log behind the admin UI's provisioning status (issue #325).

Directories fail quietly: a rotated-away token, a schema the endpoint refuses, a 409 on every
sync. The token list's ``last_used_at`` says a token authenticated, not that anything it sent
worked. This log records one row per request — route template, status, outcome class and the
short SCIM error — so an administrator can see *when provisioning last worked* and *why it stopped*.

Written once per request by ``routers.scim.ScimRoute`` (best effort, never on the per-request
authentication path of the rest of the application) and swept after
``SCIM_ACTIVITY_RETENTION_DAYS``.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlScimActivity, SqlScimToken

OUTCOME_OK = "ok"
OUTCOME_CLIENT_ERROR = "client_error"
OUTCOME_SERVER_ERROR = "server_error"
OUTCOME_AUTH_FAILED = "auth_failed"
OUTCOMES = (OUTCOME_OK, OUTCOME_CLIENT_ERROR, OUTCOME_SERVER_ERROR, OUTCOME_AUTH_FAILED)
ERROR_OUTCOMES = (OUTCOME_CLIENT_ERROR, OUTCOME_SERVER_ERROR, OUTCOME_AUTH_FAILED)

MAX_ERROR_LENGTH = 500
MAX_PAGE_SIZE = 200


def _now() -> datetime:
    """Naive UTC, matching how every other timestamp in this schema is stored."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def _clip(value: Optional[str], length: int) -> Optional[str]:
    if value is None:
        return None
    return value[:length]


@dataclass(frozen=True)
class ScimActivityEntry:
    """One recorded request, as the admin API returns it."""

    id: int
    at: datetime
    token_id: Optional[int]
    token_name: Optional[str]
    method: str
    path: str
    resource_id: Optional[str]
    status: int
    outcome: str
    error: Optional[str]
    duration_ms: Optional[int]

    def to_json(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "at": _iso(self.at),
            "token_id": self.token_id,
            "token_name": self.token_name,
            "method": self.method,
            "path": self.path,
            "resource_id": self.resource_id,
            "status": self.status,
            "outcome": self.outcome,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


def _entry(row: SqlScimActivity) -> ScimActivityEntry:
    return ScimActivityEntry(
        id=row.id,
        at=row.at,
        token_id=row.token_id,
        token_name=row.token_name,
        method=row.method,
        path=row.path,
        resource_id=row.resource_id,
        status=row.status,
        outcome=row.outcome,
        error=row.error,
        duration_ms=row.duration_ms,
    )


def outcome_for(status: int, authenticated: bool) -> str:
    """Classify a response. An unauthenticated request is ``auth_failed`` whatever its status."""
    if not authenticated:
        return OUTCOME_AUTH_FAILED
    if status >= 500:
        return OUTCOME_SERVER_ERROR
    if status >= 400:
        return OUTCOME_CLIENT_ERROR
    return OUTCOME_OK


class ScimActivityRepository:
    """Reads and writes ``scim_activity``."""

    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def record(
        self,
        *,
        token_id: Optional[int],
        token_name: Optional[str],
        method: str,
        path: str,
        resource_id: Optional[str],
        status: int,
        outcome: str,
        error: Optional[str],
        duration_ms: Optional[int],
        at: Optional[datetime] = None,
    ) -> None:
        """Insert one row. Every free-text field is clipped to its column."""
        with self._Session(read_only=False) as session:
            session.add(
                SqlScimActivity(
                    at=at or _now(),
                    token_id=token_id,
                    token_name=_clip(token_name, 255),
                    method=_clip(method, 16) or "",
                    path=_clip(path, 255) or "",
                    resource_id=_clip(resource_id, 255),
                    status=int(status),
                    outcome=outcome,
                    error=_clip(error, MAX_ERROR_LENGTH),
                    duration_ms=duration_ms,
                )
            )
            session.flush()

    def delete_older_than(self, cutoff: datetime) -> int:
        """Delete rows recorded before ``cutoff``. Returns how many."""
        if cutoff.tzinfo:
            cutoff = cutoff.astimezone(timezone.utc).replace(tzinfo=None)
        with self._Session(read_only=False) as session:
            return int(session.query(SqlScimActivity).filter(SqlScimActivity.at < cutoff).delete(synchronize_session=False))

    def list(
        self,
        limit: int = 50,
        before: Optional[int] = None,
        outcome: Optional[str] = None,
        token_id: Optional[int] = None,
    ) -> List[ScimActivityEntry]:
        """Newest first.

        Parameters:
            limit: At most this many rows, capped at ``MAX_PAGE_SIZE``.
            before: Only rows whose ``id`` is lower — the cursor for the next page is the last
                row's ``id``. Ids are monotonic, timestamps are not unique.
            outcome: Only this outcome.
            token_id: Only this token's requests.
        """
        limit = max(1, min(int(limit), MAX_PAGE_SIZE))
        with self._Session() as session:
            query = session.query(SqlScimActivity)
            if before is not None:
                query = query.filter(SqlScimActivity.id < before)
            if outcome is not None:
                query = query.filter(SqlScimActivity.outcome == outcome)
            if token_id is not None:
                query = query.filter(SqlScimActivity.token_id == token_id)
            return [_entry(row) for row in query.order_by(SqlScimActivity.id.desc()).limit(limit).all()]

    def status(self, healthy_window_seconds: int, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Provisioning health, overall and per token.

        ``provisioning_healthy`` is True when a request succeeded within the window, False when
        none did, and None when SCIM has never been used at all — no token ever authenticated and
        nothing was ever recorded — so a deployment that does not use SCIM is not "unhealthy".
        """
        now = now or _now()
        day_ago = now - timedelta(hours=24)
        is_error = SqlScimActivity.outcome.in_(ERROR_OUTCOMES)
        with self._Session() as session:
            tokens = (
                session.query(SqlScimToken.id, SqlScimToken.name, SqlScimToken.last_used_at, SqlScimToken.expires_at, SqlScimToken.revoked_at)
                .order_by(SqlScimToken.id)
                .all()
            )
            aggregates = {
                row[0]: row
                for row in session.query(
                    SqlScimActivity.token_id,
                    func.max(case((SqlScimActivity.outcome == OUTCOME_OK, SqlScimActivity.at))),
                    func.max(case((is_error, SqlScimActivity.at))),
                    func.sum(case((SqlScimActivity.at >= day_ago, 1), else_=0)),
                    func.sum(case(((SqlScimActivity.at >= day_ago) & is_error, 1), else_=0)),
                )
                .group_by(SqlScimActivity.token_id)
                .all()
            }
            # The message of each token's latest error: one row per token, by the highest id.
            latest_error_ids = session.query(func.max(SqlScimActivity.id)).filter(is_error).group_by(SqlScimActivity.token_id)
            latest_errors = {
                row.token_id: row
                for row in session.query(SqlScimActivity.id, SqlScimActivity.token_id, SqlScimActivity.status, SqlScimActivity.error)
                .filter(SqlScimActivity.id.in_(latest_error_ids.scalar_subquery()))
                .all()
            }

        def _bucket(token_id):
            row = aggregates.get(token_id)
            error_row = latest_errors.get(token_id)
            return {
                "last_success_at": row[1] if row else None,
                "last_error_at": row[2] if row else None,
                "last_error": (error_row.error or f"HTTP {error_row.status}") if error_row else None,
                "last_error_status": error_row.status if error_row else None,
                "requests_24h": int(row[3] or 0) if row else 0,
                "errors_24h": int(row[4] or 0) if row else 0,
            }

        per_token = []
        for token in tokens:
            bucket = _bucket(token.id)
            live = token.revoked_at is None and (token.expires_at is None or token.expires_at > now)
            per_token.append(
                {
                    "token_id": token.id,
                    "name": token.name,
                    "active": live,
                    "last_used_at": _iso(token.last_used_at),
                    "last_success_at": _iso(bucket["last_success_at"]),
                    "last_error_at": _iso(bucket["last_error_at"]),
                    "last_error": bucket["last_error"],
                    "last_error_status": bucket["last_error_status"],
                    "requests_24h": bucket["requests_24h"],
                    "errors_24h": bucket["errors_24h"],
                }
            )

        unauthenticated = _bucket(None)
        successes = [row[1] for row in aggregates.values() if row[1] is not None]
        errors = [row[2] for row in aggregates.values() if row[2] is not None]
        last_success_at = max(successes) if successes else None
        last_error_at = max(errors) if errors else None
        last_error = None
        if latest_errors:
            newest = max(latest_errors.values(), key=lambda row: row.id)
            last_error = newest.error or f"HTTP {newest.status}"

        ever_used = bool(aggregates) or any(token.last_used_at is not None for token in tokens)
        if last_success_at is not None and (now - last_success_at).total_seconds() <= healthy_window_seconds:
            healthy: Optional[bool] = True
        elif ever_used:
            healthy = False
        else:
            healthy = None

        return {
            "provisioning_healthy": healthy,
            "last_success_at": _iso(last_success_at),
            "last_error_at": _iso(last_error_at),
            "last_error": last_error,
            "requests_24h": sum(int(row[3] or 0) for row in aggregates.values()),
            "errors_24h": sum(int(row[4] or 0) for row in aggregates.values()),
            "auth_failures_24h": unauthenticated["errors_24h"],
            "last_auth_failure_at": _iso(unauthenticated["last_error_at"]),
            "tokens": per_token,
        }
