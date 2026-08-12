"""In-flight authorization state, server-side (issue #316).

A login is a round trip: the browser leaves for the provider and comes back with ``code`` and
``state``, and the server has to remember what it started. That memory used to be a single
``oauth_state`` key in the cookie, which two problems follow from:

* **Two tabs clobber each other.** One key holds one attempt, so starting a second login
  overwrites the first, and whichever comes back second fails a CSRF check it should have passed.
* **Nothing records which provider started it.** With one provider that is answerable by
  assumption. With several it is the [RFC 9207](https://www.rfc-editor.org/rfc/rfc9207.html)
  mix-up question — an authorization response says nothing about who sent it, and ``code`` and
  ``state`` look identical whichever authorization server produced them.

A row per attempt answers both. The row names the issuer the transaction began with, which is
what ``validate_response_issuer`` (#307) compares the returned ``iss`` against.

**Single use.** ``consume`` claims the row with the delete itself and reports the attempt only to
the caller whose delete matched, so two callbacks racing one state cannot both proceed and a replay
finds nothing.
"""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlAuthState

#: 256 bits. The value is a CSRF token: it must be unguessable, and it is the only thing tying a
#: callback to the login attempt that started it.
STATE_BYTES = 32

#: How long an attempt may take. Long enough for a real login — including an MFA prompt and a
#: password reset — and short enough that an abandoned row is not a lasting replay target.
DEFAULT_STATE_LIFETIME_SECONDS = 15 * 60


@dataclass(frozen=True)
class AuthAttempt:
    """What a login attempt recorded before leaving for the provider.

    Attributes:
        state: The CSRF value echoed back on the callback.
        provider_id: Registry id of the provider the attempt went to. The issuer to compare the
            response against is read from the registry under this id rather than copied here:
            the registry is the authority on a provider's issuer, and a provider repointed at a
            different one mid-flight *should* fail the comparison rather than pass it against a
            stale copy.
        redirect_after_login: Where to send the browser once it is authenticated.
    """

    state: str
    provider_id: str
    redirect_after_login: Optional[str] = None


def _now() -> datetime:
    """Naive UTC, matching the DateTime columns the migration created."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuthStateRepository:
    """Creates, consumes and sweeps in-flight authorization state."""

    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def create(
        self,
        provider_id: str,
        *,
        redirect_after_login: Optional[str] = None,
        lifetime_seconds: int = DEFAULT_STATE_LIFETIME_SECONDS,
    ) -> str:
        """Start an attempt and return its ``state``.

        Parameters:
            provider_id: Registry id of the provider this attempt goes to.
            redirect_after_login: Validated relative path to return the browser to.
            lifetime_seconds: How long the attempt may take.

        Returns:
            The state value to send to the authorization endpoint.
        """
        state = secrets.token_urlsafe(STATE_BYTES)
        with self._Session(read_only=False) as session:
            session.add(
                SqlAuthState(
                    state=state,
                    provider_id=provider_id,
                    relay_state=redirect_after_login,
                    expires_at=_now() + timedelta(seconds=lifetime_seconds),
                )
            )
            session.flush()
        return state

    def consume(self, state: str) -> Optional[AuthAttempt]:
        """Take the attempt named by ``state``, removing it.

        Single use by construction: the row is deleted as it is read, so a callback replayed with
        the same ``state`` — from a browser history entry, a proxy log, an attacker who captured
        the redirect — finds nothing and is refused.

        Returns None when the state is unknown, already used, or expired. The caller cannot tell
        which, deliberately.
        """
        if not state:
            return None
        with self._Session(read_only=False) as session:
            row = session.query(SqlAuthState).filter(SqlAuthState.state == state).one_or_none()
            if row is None:
                return None

            attempt = AuthAttempt(
                state=row.state,
                provider_id=row.provider_id or "",
                redirect_after_login=row.relay_state,
            )
            expired = row.expires_at is not None and row.expires_at <= _now()

            # The delete is what claims the attempt, and its row count is what says whether *this*
            # caller claimed it. Deleting the ORM object instead would let two concurrent callbacks
            # with the same state both see the row and both proceed: the second delete matches
            # nothing and SQLAlchemy only warns. Whoever's delete matched has the attempt.
            claimed = session.query(SqlAuthState).filter(SqlAuthState.state == state).delete(synchronize_session=False)
            session.flush()

        if not claimed:
            return None
        return None if expired else attempt

    def delete_expired(self, before: Optional[datetime] = None) -> int:
        """Delete attempts that were never completed.

        Housekeeping: ``consume`` already refuses an expired row. Abandoned logins would
        otherwise accumulate one row per browser that changed its mind.
        """
        cutoff = before or _now()
        if cutoff.tzinfo:
            cutoff = cutoff.replace(tzinfo=None)
        with self._Session(read_only=False) as session:
            return int(session.query(SqlAuthState).filter(SqlAuthState.expires_at <= cutoff).delete(synchronize_session=False))
