"""Replay protection for SAML assertions (issue #328).

``record`` is the check: it inserts the assertion ID under a unique index, and a duplicate —
the same Response presented twice, by the same browser or by someone who copied the POST body —
fails the insert. Checking with a SELECT first would leave a window in which two concurrent
presentations both find nothing; the unique constraint has no such window.
"""

from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlSamlAssertion


def _now() -> datetime:
    """Naive UTC, matching the DateTime columns the migration created."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SamlAssertionRepository:
    """Records accepted assertion IDs and sweeps the expired ones."""

    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def record(self, assertion_id: str, provider_id: str, not_on_or_after: datetime) -> bool:
        """Record an assertion as consumed.

        Parameters:
            assertion_id: The assertion's ``ID``.
            provider_id: The provider it came from, for the audit trail.
            not_on_or_after: When the assertion stops being acceptable; the row is kept until then.

        Returns:
            True the first time; False if this assertion ID was already recorded — a replay.
        """
        if not assertion_id:
            return False
        if not_on_or_after.tzinfo:
            not_on_or_after = not_on_or_after.astimezone(timezone.utc).replace(tzinfo=None)
        try:
            with self._Session(read_only=False) as session:
                session.add(SqlSamlAssertion(assertion_id=assertion_id, provider_id=provider_id, not_on_or_after=not_on_or_after))
                session.flush()
        except Exception as exc:
            # The managed session rewrites driver errors into MlflowException; a unique violation
            # is still a replay. Anything else propagates — failing to record must not pass.
            if _is_unique_violation(exc):
                return False
            raise
        return True

    def release(self, assertion_id: str) -> bool:
        """Forget one recorded ID, so the same message can be processed again.

        For an IdP-initiated LogoutRequest whose revocation failed after it was recorded: the IdP
        retries a refused logout, and a retry refused as a replay would leave the session live.
        Never used for an assertion that logged someone in.

        Returns:
            Whether a record was removed.
        """
        if not assertion_id:
            return False
        with self._Session(read_only=False) as session:
            return bool(session.query(SqlSamlAssertion).filter(SqlSamlAssertion.assertion_id == assertion_id).delete(synchronize_session=False))

    def delete_expired(self, before: Optional[datetime] = None) -> int:
        """Delete records of assertions that can no longer pass validation. Returns the count."""
        cutoff = before or _now()
        if cutoff.tzinfo:
            cutoff = cutoff.astimezone(timezone.utc).replace(tzinfo=None)
        with self._Session(read_only=False) as session:
            return int(session.query(SqlSamlAssertion).filter(SqlSamlAssertion.not_on_or_after <= cutoff).delete(synchronize_session=False))


def _is_unique_violation(exc: BaseException) -> bool:
    """Whether ``exc`` is, or was caused by, an ``IntegrityError``.

    On this insert the only constraint a well-formed row can violate is the unique index on
    ``assertion_id``; the managed session wraps the driver error in an ``MlflowException``.
    """
    seen = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, IntegrityError):
            return True
        current = current.__cause__ or current.__context__
    return False
