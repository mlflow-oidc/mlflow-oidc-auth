"""Persistence for external identities bound to local users (issue #309).

The table and its constraints landed with the Phase 0 migration (#333); this is the data access
over it. Resolution policy lives in :mod:`mlflow_oidc_auth.identity_resolution` — this layer only
reads and writes rows.
"""

from datetime import datetime, timezone
from typing import Callable, List, Optional, Set

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy import func, true
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

    def list_identities_for_username(self, username: str) -> List[tuple]:
        """``[(provider_id, subject), ...]`` bound to ``username``, oldest first."""
        username = normalize_username(username)
        with self._Session() as session:
            rows = (
                session.query(SqlUserIdentity.provider_id, SqlUserIdentity.subject)
                .join(SqlUser, SqlUserIdentity.user_id == SqlUser.id)
                .filter(SqlUser.username == username)
                .order_by(SqlUserIdentity.id)
                .all()
            )
            return [(row[0], row[1]) for row in rows]

    def has_real_binding(self, username: str) -> bool:
        """Whether an identity a login (or bearer provisioning) bound names ``username``.

        The placeholder the identity migration recorded for every account that existed then —
        ``default`` with the username as its subject — does not count: it says nothing about
        which identity the account belongs to.
        """
        from mlflow_oidc_auth.provider_registry import DEFAULT_PROVIDER_ID

        name = normalize_username(username)
        return any(not (provider == DEFAULT_PROVIDER_ID and subject == name) for provider, subject in self.list_identities_for_username(name))

    def unlink(self, provider_id: str, subject: str, username: str) -> bool:
        """Remove the binding of ``(provider_id, subject)`` to ``username``. Returns whether one was removed."""
        username = normalize_username(username)
        with self._Session(read_only=False) as session:
            removed = (
                session.query(SqlUserIdentity)
                .filter(
                    SqlUserIdentity.provider_id == provider_id,
                    SqlUserIdentity.subject == subject,
                    SqlUserIdentity.user_id.in_(session.query(SqlUser.id).filter(SqlUser.username == username)),
                )
                .delete(synchronize_session=False)
            )
        from mlflow_oidc_auth.utils.bearer_identity_cache import flush_bearer_identity_cache

        flush_bearer_identity_cache()
        return bool(removed)

    def providers_in_email_domain(self, domain: str, exclude_username: Optional[str] = None) -> Set[str]:
        """The providers whose identities own accounts named by an address in ``domain``.

        An account with no identity bound counts as the ``default`` provider's: it is from before
        identities were recorded, or was created by an administrator or SCIM — either way not by
        another provider's login.

        Parameters:
            domain: The email domain, compared case-insensitively.

        Returns:
            The provider ids; empty when no account is named in the domain.
        """
        from mlflow_oidc_auth.provider_registry import DEFAULT_PROVIDER_ID

        suffix = "@" + domain.strip().lower()
        with self._Session() as session:
            rows = (
                session.query(SqlUser.id, SqlUserIdentity.provider_id)
                .outerjoin(SqlUserIdentity, SqlUserIdentity.user_id == SqlUser.id)
                # Lowered in SQL too: LIKE is case-sensitive on PostgreSQL, and rows from before
                # usernames were normalised may be mixed case.
                .filter(func.lower(SqlUser.username).endswith(suffix, autoescape=True))
                .filter(SqlUser.username != normalize_username(exclude_username) if exclude_username else true())
                .all()
            )
            return {provider_id or DEFAULT_PROVIDER_ID for _, provider_id in rows}

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
        # A new binding changes what a bearer token of either provider may reach.
        from mlflow_oidc_auth.utils.bearer_identity_cache import flush_bearer_identity_cache

        flush_bearer_identity_cache()
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
