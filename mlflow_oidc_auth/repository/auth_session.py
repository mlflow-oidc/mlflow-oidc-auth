"""Server-side sessions (issue #310).

The session used to live entirely in the browser cookie: Starlette signed a dict with
``SECRET_KEY`` and the server kept nothing, so a valid cookie stayed valid until it expired and
there was nothing to revoke. Sessions are now rows, and the cookie carries only an opaque
identifier.

The table landed with the Phase 0 migration (#333); this is the data access over it.

**The lookup is one statement.** ``resolve`` joins ``auth_sessions`` to ``users`` and returns
everything the authentication path needs — session validity, username, admin and active flags —
because that path runs on every request and its statement count is a budget (#305), not an
implementation detail. A second round trip for the user would double it. The encrypted provider
tokens (#367) ride along in the same row for the same reason.

**Refreshes are single-flight.** ``refresh_guard`` serialises refreshes of one session so that
concurrent requests hitting an expired session exchange its refresh token exactly once. Under
refresh-token rotation with reuse detection, a second exchange of the same token is read by the
IdP as theft and ends the session (#367).
"""

import secrets
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, Iterator, List, Optional, Tuple

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST
from sqlalchemy import text
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlAuthSession, SqlUser
from mlflow_oidc_auth.repository.user import normalize_username

# 256 bits, per the issue. ``token_urlsafe`` returns ~43 characters for 32 bytes; the column is
# sized to 255 so the encoding is not a constraint.
SESSION_ID_BYTES = 32

# How long a refresh waits for another in-flight refresh of the same session before giving up.
# Bounded so a hung IdP cannot pin request handlers forever; the waiter then re-reads the row.
REFRESH_GUARD_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class ResolvedSession:
    """Everything the auth path needs about a session, from one lookup.

    Attributes:
        username: The session's user.
        is_admin: Whether that user is an administrator.
        is_active: Whether the account may authenticate.
        expires_at: When the session stops being valid.
        session_pk: The row's primary key.
        session_id: The opaque id the cookie carries.
        provider_id: Registry id of the provider that authenticated the session, when recorded.
        encrypted_tokens: The session's provider tokens, encrypted (see ``session.token_vault``).
            Kept out of ``repr`` so it cannot reach a log line by accident.
    """

    username: str
    is_admin: bool
    is_active: bool
    expires_at: Optional[datetime] = None
    session_pk: Optional[int] = None
    session_id: Optional[str] = None
    provider_id: Optional[str] = None
    encrypted_tokens: Optional[str] = field(default=None, repr=False)


class _KeyedLocks:
    """Process-wide, per-key mutual exclusion with entries dropped when nobody holds or awaits them.

    ``threading.Lock`` rather than ``asyncio.Lock``: the repository is synchronous, and an asyncio
    lock is bound to one event loop, while a process may run several (worker threads, test
    clients). Callers on an event loop acquire through a worker thread so the loop never blocks.
    """

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: Dict[str, List] = {}

    @contextmanager
    def hold(self, key: str, timeout: float) -> Iterator[None]:
        with self._guard:
            entry = self._locks.setdefault(key, [threading.Lock(), 0])
            entry[1] += 1
        acquired = False
        try:
            acquired = entry[0].acquire(timeout=timeout)
            if not acquired:
                raise TimeoutError("timed out waiting for a concurrent refresh of this session")
            yield
        finally:
            if acquired:
                entry[0].release()
            with self._guard:
                entry[1] -= 1
                if entry[1] == 0 and self._locks.get(key) is entry:
                    del self._locks[key]

    def __len__(self) -> int:
        with self._guard:
            return len(self._locks)


_REFRESH_LOCKS = _KeyedLocks()


class RefreshGuard:
    """What a caller holding ``refresh_guard`` may do with the row.

    Attributes:
        encrypted_tokens: The row's token blob as read *after* the guard was acquired — so a
            caller that waited sees what the previous holder wrote.
        live: Whether the session was live (known, unrevoked) when read.
    """

    def __init__(self, encrypted_tokens: Optional[str], live: bool, reread: Callable[[], Optional[str]], write: Callable[[Optional[str]], bool]):
        self.encrypted_tokens = encrypted_tokens
        self.live = live
        self._reread = reread
        self._write = write

    def reread(self) -> Optional[str]:
        """Read the blob again, and remember it."""
        self.encrypted_tokens = self._reread()
        return self.encrypted_tokens

    def write(self, encrypted_tokens: Optional[str]) -> bool:
        """Store a new blob on the row. Returns True if the session was live to receive it."""
        written = self._write(encrypted_tokens)
        if written:
            self.encrypted_tokens = encrypted_tokens
        return written

    def __repr__(self) -> str:
        return f"RefreshGuard(live={self.live}, has_tokens={bool(self.encrypted_tokens)})"


def _now() -> datetime:
    """Naive UTC, matching the DateTime columns the migration created."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuthSessionRepository:
    """Creates, resolves and revokes server-side sessions."""

    def __init__(self, session_maker, row_locks: Optional[bool] = None):
        """
        Parameters:
            session_maker: The managed session factory.
            row_locks: Whether the database takes row locks (``SELECT ... FOR UPDATE``). None
                detects it from the dialect on first use. SQLite has none, so the refresh guard
                falls back to a process-wide lock there.
        """
        self._Session: Callable[[], Session] = session_maker
        self._row_locks = row_locks

    def create(self, username: str, expires_at: datetime, provider_id: Optional[str] = None, encrypted_tokens: Optional[str] = None) -> str:
        """Open a session for ``username`` and return its opaque identifier.

        The identifier is generated here rather than derived from anything about the user: it is
        the only thing the cookie will carry, so it must not encode identity or be guessable.

        Parameters:
            username: Identity key of the user logging in.
            expires_at: When the session should stop being valid.
            provider_id: Registry id of the provider that authenticated them, when known.
            encrypted_tokens: The provider tokens, already encrypted, so they are on the row
                before the cookie ever names it.

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
                    encrypted_tokens=encrypted_tokens,
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
                session.query(
                    SqlUser.username,
                    SqlUser.is_admin,
                    SqlUser.active,
                    SqlAuthSession.expires_at,
                    SqlAuthSession.id,
                    SqlAuthSession.session_id,
                    SqlAuthSession.provider_id,
                    SqlAuthSession.encrypted_tokens,
                )
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
            return ResolvedSession(
                username=row[0],
                is_admin=bool(row[1]),
                is_active=bool(row[2]),
                expires_at=row[3],
                session_pk=row[4],
                session_id=row[5],
                provider_id=row[6],
                encrypted_tokens=row[7],
            )

    def store_tokens(self, session_id: str, encrypted_tokens: Optional[str]) -> bool:
        """Replace a live session's encrypted provider tokens.

        Parameters:
            session_id: The session to update.
            encrypted_tokens: The new blob, or None to drop the tokens.

        Returns:
            True if a live (unrevoked, unexpired) session was updated.
        """
        if not session_id:
            return False
        with self._Session(read_only=False) as session:
            updated = (
                session.query(SqlAuthSession)
                .filter(SqlAuthSession.session_id == session_id, SqlAuthSession.revoked_at.is_(None), SqlAuthSession.expires_at > _now())
                .update({SqlAuthSession.encrypted_tokens: encrypted_tokens}, synchronize_session=False)
            )
            return bool(updated)

    def _read_tokens(self, session_id: str) -> tuple[bool, Optional[str]]:
        """(live, encrypted_tokens) for a session, in one statement."""
        with self._Session() as session:
            row = (
                session.query(SqlAuthSession.encrypted_tokens)
                .filter(SqlAuthSession.session_id == session_id, SqlAuthSession.revoked_at.is_(None), SqlAuthSession.expires_at > _now())
                .one_or_none()
            )
            return (row is not None, row[0] if row is not None else None)

    def _uses_row_locks(self) -> bool:
        if self._row_locks is None:
            with self._Session() as session:
                self._row_locks = session.get_bind().dialect.name != "sqlite"
        return self._row_locks

    @contextmanager
    def refresh_guard(self, session_id: str, timeout: float = REFRESH_GUARD_TIMEOUT_SECONDS) -> Iterator[RefreshGuard]:
        """Hold exclusive refresh rights over one session.

        Two layers. A process-wide lock per session id serialises refreshes within this process
        on every database. Where the database has row locks, the row is additionally locked with
        ``SELECT ... FOR UPDATE`` for the duration, which serialises replicas too; the yielded
        guard then reads and writes inside that same transaction — a write from another
        connection would wait on the lock this one holds. SQLite has no row locks, so there the
        guard is process-wide only and reads and writes use short transactions of their own.

        Either way the blob yielded is read *after* acquiring, so a caller that queued behind a
        refresh sees its result and can adopt it instead of exchanging again.

        Parameters:
            session_id: The session to guard.
            timeout: Seconds to wait for the process-wide lock.

        Yields:
            A ``RefreshGuard`` over the row.

        Raises:
            TimeoutError: If another refresh of this session held the lock for ``timeout``.
        """
        with _REFRESH_LOCKS.hold(session_id, timeout):
            if not self._uses_row_locks():
                live, blob = self._read_tokens(session_id)
                yield RefreshGuard(
                    blob,
                    live,
                    reread=lambda: self._read_tokens(session_id)[1],
                    write=lambda new_blob: self.store_tokens(session_id, new_blob),
                )
                return

            with self._Session(read_only=False) as session:
                if session.get_bind().dialect.name == "postgresql":
                    # Bound the wait on another replica's lock the same way as the local one.
                    session.execute(text(f"SET LOCAL lock_timeout = '{int(timeout)}s'"))

                def _select():
                    return (
                        session.query(SqlAuthSession)
                        .filter(SqlAuthSession.session_id == session_id, SqlAuthSession.revoked_at.is_(None), SqlAuthSession.expires_at > _now())
                        .with_for_update()
                        .one_or_none()
                    )

                row = _select()

                def _reread() -> Optional[str]:
                    session.expire_all()
                    current = _select()
                    return current.encrypted_tokens if current is not None else None

                def _write(new_blob: Optional[str]) -> bool:
                    if row is None:
                        return False
                    row.encrypted_tokens = new_blob
                    session.flush()
                    return True

                yield RefreshGuard(row.encrypted_tokens if row is not None else None, row is not None, reread=_reread, write=_write)

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

    def list_live_for_provider(self, username: str, provider_id: str) -> List[Tuple[str, Optional[str]]]:
        """``(session_id, encrypted_tokens)`` for each live session ``provider_id`` opened for ``username``.

        What IdP-initiated single logout (#329) works from: the IdP names a subject and, usually,
        one of its sessions; the caller decrypts each blob to find the one whose ``SessionIndex``
        matches. Scoped to the provider so a SAML logout never reaches a session another
        provider opened.
        """
        username = normalize_username(username)
        with self._Session() as session:
            rows = (
                session.query(SqlAuthSession.session_id, SqlAuthSession.encrypted_tokens)
                .join(SqlUser, SqlAuthSession.user_id == SqlUser.id)
                .filter(
                    SqlUser.username == username,
                    SqlAuthSession.provider_id == provider_id,
                    SqlAuthSession.revoked_at.is_(None),
                    SqlAuthSession.expires_at > _now(),
                )
                .all()
            )
            return [(row[0], row[1]) for row in rows]

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
