"""Persistence for external identities bound to local users (issue #309).

The table and its constraints landed with the Phase 0 migration (#333); this is the data access
over it. Resolution policy lives in :mod:`mlflow_oidc_auth.identity_resolution` — this layer only
reads and writes rows.
"""

from datetime import datetime, timezone
from typing import Callable, List, Optional

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlUser, SqlUserIdentity
from mlflow_oidc_auth.repository.user import normalize_username


class UserIdentityRepository:
    """Reads and writes ``user_identities`` rows."""

    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def get_username_by_identity(self, provider_id: str, subject: str) -> Optional[str]:
        """Return the username bound to ``(provider_id, subject)``, or None.

        The pair is unique, so this is the exact-match path: an identity that already exists
        resolves to its user without consulting any claim, which is what makes ``subject``
        binding immune to anything the token asserts about email.

        Parameters:
            provider_id: Registry id of the asserting provider.
            subject: The provider's stable identifier for the principal.

        Returns:
            The bound username, or None when the pair is unknown.
        """
        with self._Session() as session:
            row = (
                session.query(SqlUser.username)
                .join(SqlUserIdentity, SqlUserIdentity.user_id == SqlUser.id)
                .filter(SqlUserIdentity.provider_id == provider_id, SqlUserIdentity.subject == subject)
                .one_or_none()
            )
            return row[0] if row else None

    def list_providers_for_username(self, username: str) -> List[str]:
        """Return the provider ids that have an identity bound to ``username``.

        Used to reason about a user who has arrived through more than one provider.
        """
        username = normalize_username(username)
        with self._Session() as session:
            rows = session.query(SqlUserIdentity.provider_id).join(SqlUser, SqlUserIdentity.user_id == SqlUser.id).filter(SqlUser.username == username).all()
            return [row[0] for row in rows]

    def link(self, provider_id: str, subject: str, username: str, *, allow_additional_provider: bool = False) -> bool:
        """Bind ``(provider_id, subject)`` to an existing user.

        Idempotent: re-linking an identity that already points at this user is a no-op rather
        than an error, so a repeated login does not fail on the unique constraint.

        **Refuses by default to add a second provider to a user another provider already owns.**
        That rule is also applied when resolving (:mod:`mlflow_oidc_auth.identity_resolution`),
        but checking it only there left it advisory: this repository is public on the store, so
        any caller reaching it directly bypassed the check, and even a correct caller had a
        window between resolving and writing in which a concurrent login could bind a different
        provider. Enforcing it at the write closes both.

        ``allow_additional_provider`` exists for the deliberate account-linking case — a person
        who genuinely holds identities at two IdPs — so that becomes an explicit decision at the
        call site rather than something that happens by omission.

        Returns:
            True when a new row was written, False when the binding already existed.

        Raises:
            MlflowException: If the user does not exist, if the pair is already bound to a
                *different* user, or if another provider already owns this user and
                ``allow_additional_provider`` was not set. The middle case is an attempted
                takeover and must never be silently re-pointed.

                MlflowException rather than a bare ValueError because the managed session
                wraps every other exception into one anyway — raising it directly keeps the
                error code meaningful instead of collapsing to INTERNAL_ERROR.
        """
        username = normalize_username(username)
        with self._Session(read_only=False) as session:
            user = session.query(SqlUser).filter(SqlUser.username == username).one_or_none()
            if user is None:
                raise MlflowException(f"cannot bind an identity to unknown user '{username}'", RESOURCE_DOES_NOT_EXIST)

            existing = session.query(SqlUserIdentity).filter(SqlUserIdentity.provider_id == provider_id, SqlUserIdentity.subject == subject).one_or_none()
            if existing is not None:
                if existing.user_id != user.id:
                    raise MlflowException(f"identity ({provider_id}, {subject}) is already bound to a different user", RESOURCE_ALREADY_EXISTS)
                return False

            if not allow_additional_provider:
                foreign = (
                    session.query(SqlUserIdentity.provider_id).filter(SqlUserIdentity.user_id == user.id, SqlUserIdentity.provider_id != provider_id).first()
                )
                if foreign is not None:
                    raise MlflowException(
                        f"user '{username}' is already bound to provider '{foreign[0]}'; refusing to bind provider "
                        f"'{provider_id}' as well. Pass allow_additional_provider=True to link deliberately.",
                        INVALID_STATE,
                    )

            session.add(SqlUserIdentity(provider_id=provider_id, subject=subject, user_id=user.id))
            session.flush()
            return True

    def touch_last_login(self, provider_id: str, subject: str) -> None:
        """Record that this identity was just used.

        Best-effort by design: an identity that has gone missing between resolution and this
        call is not worth failing a login over.
        """
        with self._Session(read_only=False) as session:
            identity = session.query(SqlUserIdentity).filter(SqlUserIdentity.provider_id == provider_id, SqlUserIdentity.subject == subject).one_or_none()
            if identity is not None:
                identity.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
                session.flush()
