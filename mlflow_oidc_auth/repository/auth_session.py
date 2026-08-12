"""Server-side sessions (issue #310).

The session used to live entirely in the browser cookie: Starlette signed a dict with
``SECRET_KEY`` and the server kept nothing, so a valid cookie stayed valid until it expired and
there was nothing to revoke. Sessions are now rows, and the cookie carries only an opaque
identifier.

The table landed with the Phase 0 migration (#333); this is the data access over it.

**The lookup is one statement.** ``resolve`` joins ``auth_sessions`` to ``users`` and returns
everything the authentication path needs — session validity, username, admin and active flags —
because that path runs on every request and its statement count is a budget (#305), not an
implementation detail. A second round trip for the user would double it.
"""

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, List, Optional

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlAuthSession, SqlUser
from mlflow_oidc_auth.repository.user import normalize_username

# 256 bits, per the issue. ``token_urlsafe`` returns ~43 characters for 32 bytes; the column is
# sized to 255 so the encoding is not a constraint.
SESSION_ID_BYTES = 32


@dataclass(frozen=True)
class ResolvedSession:
    """Everything the auth path needs about a session, from one lookup.

    Attributes:
        username: The session's user.
        is_admin: Whether that user is an administrator.
        is_active: Whether the account may authenticate.
        expires_at: When the session stops being valid.
    """

    username: str
    is_admin: bool
    is_active: bool
    expires_at: Optional[datetime] = None


def _now() -> datetime:
    """Naive UTC, matching the DateTime columns the migration created."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuthSessionRepository:
    """Creates, resolves and revokes server-side sessions."""

    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def create(self, username: str, expires_at: datetime, provider_id: Optional[str] = None) -> str:
        """Open a session for ``username`` and return its opaque identifier.

        The identifier is generated here rather than derived from anything about the user: it is
        the only thing the cookie will carry, so it must not encode identity or be guessable.

        Parameters:
            username: Identity key of the user logging in.
            expires_at: When the session should stop being valid.
            provider_id: Registry id of the provider that authenticated them, when known.

        Returns:
            The session id to place in the cookie.

        Raises:
            MlflowException: If the user does not exist. Raised with a proper error code rather
                than a bare ``ValueError``, which the managed session would rewrite into an
                opaque ``INTERNAL_ERROR``.
        """
        username = normalize_username(username)
        session_id = secrets.token_urlsafe(SESSION_ID_BYTES)
        with self._Session(read_only=False) as session:
            user = session.query(SqlUser.id).filter(SqlUser.username == username).one_or_none()
            if user is None:
                raise MlflowException(f"cannot open a session for unknown user '{username}'", RESOURCE_DOES_NOT_EXIST)
            session.add(
                SqlAuthSession(
                    session_id=session_id,
                    user_id=user[0],
                    provider_id=provider_id,
                    expires_at=expires_at.replace(tzinfo=None) if expires_at.tzinfo else expires_at,
                )
            )
            session.flush()
        return session_id

    def resolve(self, session_id: str) -> Optional[ResolvedSession]:
        """Resolve a session id to its user, in a single statement.

        Returns None when the session is unknown, revoked or expired — the three ways a cookie
        can be presented and not be honoured. The caller cannot distinguish them, which is
        deliberate: a revoked session and a forged one should look identical from outside.

        Expiry is part of this statement rather than a Python check on the returned row, so an
        expired session is never materialised and cannot be honoured by a caller that forgets to
        look. The cutoff is the application clock, matching the naive-UTC values ``create``
        writes — the database clock is deliberately not involved, since mixing the two is what
        makes expiry behave differently on a replica.
        """
        if not session_id:
            return None
        with self._Session() as session:
            row = (
                session.query(SqlUser.username, SqlUser.is_admin, SqlUser.active, SqlAuthSession.expires_at)
                .join(SqlAuthSession, SqlAuthSession.user_id == SqlUser.id)
                .filter(
                    SqlAuthSession.session_id == session_id,
                    SqlAuthSession.revoked_at.is_(None),
                    SqlAuthSession.expires_at > _now(),
                )
                .one_or_none()
            )
            if row is None:
                return None
            return ResolvedSession(username=row[0], is_admin=bool(row[1]), is_active=bool(row[2]), expires_at=row[3])

    def revoke(self, session_id: str) -> bool:
        """Revoke one session. Returns True if it was live until now.

        Idempotent: revoking an already-revoked session reports False rather than raising, so a
        double logout is not an error.
        """
        with self._Session(read_only=False) as session:
            updated = (
                session.query(SqlAuthSession)
                .filter(SqlAuthSession.session_id == session_id, SqlAuthSession.revoked_at.is_(None))
                .update({SqlAuthSession.revoked_at: _now()}, synchronize_session=False)
            )
            return bool(updated)

    def revoke_all_for_user(self, username: str) -> int:
        """Revoke every live session belonging to ``username``.

        This is what makes deprovisioning real: deactivating an account (#311) or deleting it
        can now end the sessions it already has, rather than waiting out their cookies.

        Returns:
            How many sessions were revoked.
        """
        username = normalize_username(username)
        with self._Session(read_only=False) as session:
            user = session.query(SqlUser.id).filter(SqlUser.username == username).one_or_none()
            if user is None:
                return 0
            return int(
                session.query(SqlAuthSession)
                .filter(SqlAuthSession.user_id == user[0], SqlAuthSession.revoked_at.is_(None))
                .update({SqlAuthSession.revoked_at: _now()}, synchronize_session=False)
            )

    def list_live_for_user(self, username: str) -> List[str]:
        """Session ids currently live for ``username``. Intended for tests and administration."""
        username = normalize_username(username)
        with self._Session() as session:
            rows = (
                session.query(SqlAuthSession.session_id)
                .join(SqlUser, SqlAuthSession.user_id == SqlUser.id)
                .filter(SqlUser.username == username, SqlAuthSession.revoked_at.is_(None), SqlAuthSession.expires_at > _now())
                .all()
            )
            return [row[0] for row in rows]

    def delete_expired(self, before: Optional[datetime] = None) -> int:
        """Delete sessions that expired before ``before`` (default: now).

        Housekeeping, not correctness — ``resolve`` already refuses an expired session. Provided
        so a deployment can keep the table from growing without reaching into it by hand.
        """
        cutoff = before or _now()
        if cutoff.tzinfo:
            cutoff = cutoff.replace(tzinfo=None)
        with self._Session(read_only=False) as session:
            return int(session.query(SqlAuthSession).filter(SqlAuthSession.expires_at <= cutoff).delete(synchronize_session=False))
