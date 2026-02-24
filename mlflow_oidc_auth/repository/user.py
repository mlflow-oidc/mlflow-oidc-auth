from typing import Callable, List, Optional

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import (
    INVALID_PARAMETER_VALUE,
    INVALID_STATE,
    RESOURCE_ALREADY_EXISTS,
    RESOURCE_DOES_NOT_EXIST,
)
from mlflow.utils.validation import _validate_username
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import load_only, noload, selectinload
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlAuthSession, SqlGroup, SqlUser
from mlflow_oidc_auth.entities import User
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.ownership import evaluate_write
from mlflow_oidc_auth.repository.utils import get_user

logger = get_logger()


def _audit_ownership_conflict(username: str, decision, written_by: Optional[str], *, allowed: bool) -> None:
    """Record a write that crossed ownership.

    Emitted in ``report`` mode as well as ``enforce`` — that is what ``report`` is *for*: the
    same event, with ``status`` saying whether it was permitted, so an operator can count what
    enforcement would refuse before enabling it.
    """
    from mlflow_oidc_auth.audit import emit_audit_event

    emit_audit_event(
        "user.ownership_conflict",
        actor=written_by or "manual",
        resource_type="user",
        resource_id=username,
        detail={"owner": decision.owner, "written_by": written_by or "manual", "reason": decision.reason, "permitted": allowed},
        status="success" if allowed else "denied",
    )


def _audit_sessions_revoked(username: str, count: int, reason: str) -> None:
    """Record that a user's live sessions were ended.

    Emitted from the repository rather than a router so every caller is covered — the admin API
    today, a SCIM sync later. This is the event an operator looks for when asking whether a
    deprovisioned account still had access: before server-side sessions there was nothing to
    revoke, so there was nothing to record (#310).
    """
    from mlflow_oidc_auth.audit import emit_audit_event

    emit_audit_event(
        "session.revoked",
        actor=username,
        resource_type="user",
        resource_id=username,
        detail={"sessions": count, "reason": reason},
    )


def normalize_username(username: str) -> str:
    """Fold a username to its canonical (lowercase) form.

    Usernames are case-insensitive identity keys — emails, or admin-chosen
    service-account names. OIDC providers may return an email in mixed case
    (issue #145) and admins may create service accounts with capitals
    (issue #219). Normalizing to lowercase at the store boundary keeps creation
    and every lookup (OIDC, basic, bearer, token) consistent, so a user can
    authenticate regardless of the case they or the IdP present. Only the
    identity key is folded; the human-readable ``display_name`` is left intact.
    """
    return username.lower() if isinstance(username, str) else username


class UserRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    @staticmethod
    def _assert_not_last_active_admin(session, user, action: str) -> None:
        """Refuse an operation that would leave the deployment with no active administrator.

        Enforced here rather than in the routers so that every caller inherits it — the admin
        API, a future SCIM sync, the reconcile job in #319 and anything else that reaches the
        store. A check in one router is a check the next caller forgets.

        Recovery from a full admin lockout cannot be done from inside the system: with no active
        admin nobody can restore one over HTTP. The way back is the break-glass CLI
        (``mlflow-oidc-auth db restore-admin``), which needs database access. That asymmetry —
        cheap to prevent, expensive to undo — is why this refuses rather than warns.

        Args:
            session: The open session, so the count sees this transaction's own changes.
            user: The ``SqlUser`` about to be removed, deactivated or demoted.
            action: Verb for the error message.

        Raises:
            MlflowException: If ``user`` is the only remaining active administrator.
        """
        if not (user.is_admin and user.active):
            # Not an active admin, so removing them cannot change the count.
            return
        remaining = session.query(SqlUser).filter(SqlUser.is_admin.is_(True), SqlUser.active.is_(True), SqlUser.id != user.id).count()
        if remaining == 0:
            raise MlflowException(
                f"refusing to {action} '{user.username}': they are the only active administrator, and doing so would "
                "leave the deployment with none. Grant admin to another active user first.",
                INVALID_STATE,
            )

    def create(
        self,
        username: str,
        display_name: str,
        is_admin: bool = False,
        is_service_account: bool = False,
    ) -> User:
        username = normalize_username(username)
        _validate_username(username)
        with self._Session(read_only=False) as session:
            try:
                u = SqlUser(
                    username=username,
                    display_name=display_name,
                    is_admin=is_admin,
                    is_service_account=is_service_account,
                )
                session.add(u)
                session.flush()
                return u.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(f"User '{username}' already exists: {e}", RESOURCE_ALREADY_EXISTS) from e

    def get(self, username: str) -> User:
        username = normalize_username(username)
        with self._Session() as session:
            u = session.query(SqlUser).filter(SqlUser.username == username).one_or_none()
            if u is None:
                raise MlflowException(f"User '{username}' not found", RESOURCE_DOES_NOT_EXIST)
            return u.to_mlflow_entity()

    def get_profile(self, username: str) -> User:
        """Fetch a lightweight user entity without loading permission relationships.

        This is intended for common operations (e.g. "who am I" and admin checks)
        where loading experiment/model/scorer permission collections would be
        unnecessarily expensive.

        Returns:
            User: A User entity with groups populated and permission lists empty.

        Raises:
            MlflowException: If the user does not exist.
        """

        username = normalize_username(username)
        with self._Session() as session:
            u = (
                session.query(SqlUser)
                .options(
                    load_only(
                        SqlUser.id,
                        SqlUser.username,
                        SqlUser.display_name,
                        SqlUser.is_admin,
                        SqlUser.is_service_account,
                        # Widening the existing select rather than adding a query: this row is
                        # already fetched on every authenticated request, so #311 and #319 get
                        # these for free and the #305 budget of 2 statements is unchanged.
                        SqlUser.active,
                        SqlUser.managed_by,
                    ),
                    selectinload(SqlUser.groups).load_only(SqlGroup.id, SqlGroup.group_name),
                    noload(SqlUser.experiment_permissions),
                    noload(SqlUser.registered_model_permissions),
                    noload(SqlUser.scorer_permissions),
                    noload(SqlUser.gateway_endpoint_permissions),
                    noload(SqlUser.gateway_model_definition_permissions),
                    noload(SqlUser.gateway_secret_permissions),
                )
                .filter(SqlUser.username == username)
                .one_or_none()
            )
            if u is None:
                raise MlflowException(f"User '{username}' not found", RESOURCE_DOES_NOT_EXIST)

            return User(
                id_=u.id,
                username=u.username,
                display_name=u.display_name,
                is_admin=u.is_admin,
                is_service_account=u.is_service_account,
                active=u.active,
                managed_by=u.managed_by,
                experiment_permissions=[],
                registered_model_permissions=[],
                scorer_permissions=[],
                groups=[g.to_mlflow_entity() for g in u.groups],
            )

    def exist(self, username: str) -> bool:
        username = normalize_username(username)
        with self._Session() as session:
            return session.query(SqlUser).filter(SqlUser.username == username).first() is not None

    def list(self, is_service_account: bool = False, all: bool = False) -> List[User]:
        with self._Session() as session:
            q = session.query(SqlUser)
            if not all:
                q = q.filter(SqlUser.is_service_account == is_service_account)
            return [u.to_mlflow_entity() for u in q.all()]

    def list_usernames(self, is_service_account: bool = False) -> List[str]:
        """Return only usernames without loading any relationships.

        This is much cheaper than ``list()`` because it avoids loading
        experiment/model/scorer/gateway permission collections and groups
        for every user row.
        """
        with self._Session() as session:
            rows = session.query(SqlUser.username).filter(SqlUser.is_service_account == is_service_account).all()
            return [r[0] for r in rows]

    def update(
        self,
        username: str,
        is_admin: Optional[bool] = None,
        is_service_account: Optional[bool] = None,
        active: Optional[bool] = None,
        managed_by: Optional[str] = None,
        written_by: Optional[str] = None,
        admin_override: bool = False,
    ) -> User:
        """Update the supplied fields of a user, leaving omitted ones untouched.

        ``None`` means "not supplied": the corresponding column is left as it is. The defaults
        for the two flags previously read ``False`` while the guards
        below tested for ``None``, so a caller that omitted them silently cleared ``is_admin``
        and ``is_service_account`` instead of preserving them (issue #338).

        Parameters:
            username: Identity key of the user to update.
            is_admin: New administrator flag.
            is_service_account: New service-account flag.
            active: Whether the account may authenticate. Setting it False is how a directory
                deprovisions a user (issue #311).
            managed_by: Which source owns this row.
            written_by: Which source is performing this write, for the ownership guard (#319).
                None means an unattributed internal write, treated as ``manual``.
            admin_override: Whether an administrator asked for this explicitly. Break glass:
                always permitted, always audited.

        Returns:
            User: The updated user entity.

        Raises:
            MlflowException: If the user does not exist, or if the change would leave the
                deployment with no active administrator.
        """
        username = normalize_username(username)
        sessions_revoked = 0
        permitted_conflict = None
        with self._Session(read_only=False) as session:
            user = get_user(session, username)
            # A write from one source must not silently overwrite a row another source owns.
            # Evaluated before anything is changed, so ``enforce`` refuses rather than
            # half-applies, and ``report`` records the conflict without altering the outcome.
            decision = evaluate_write(
                getattr(user, "managed_by", None),
                written_by,
                enforcement=config.MANAGED_BY_ENFORCEMENT,
                admin_override=admin_override,
            )
            if decision.conflict and not decision.allowed:
                # Refusals are recorded immediately: nothing was written, so there is no commit
                # for the record to outlive.
                _audit_ownership_conflict(username, decision, written_by, allowed=False)
            elif decision.conflict:
                # A permitted conflict is recorded *after* the commit, further down. Written
                # here it would claim a cross-source write that a later rollback undid — and
                # this event is the one thing an operator reads to decide whether to enforce.
                permitted_conflict = decision
            if not decision.allowed:
                raise MlflowException(
                    f"User '{username}' is managed by {decision.owner!r} and cannot be changed by {written_by or 'manual'!r}.",
                    INVALID_PARAMETER_VALUE,
                )

            # Deactivating or demoting the last active admin locks everyone out just as surely
            # as deleting them, so both go through the same guard — checked before the change
            # is applied, since afterwards the user would no longer count as an active admin
            # and the query would happily report zero.
            if active is False or is_admin is False:
                self._assert_not_last_active_admin(session, user, "deactivate" if active is False else "demote")
            if is_admin is not None:
                user.is_admin = is_admin
            if is_service_account is not None:
                user.is_service_account = is_service_account
            if active is not None:
                user.active = active
                if active is False:
                    # Deprovisioning that leaves live sessions running is cosmetic — the whole
                    # point of #310. Revoked here rather than in the router so every caller
                    # inherits it, including a future SCIM sync (#324).
                    revoked = (
                        session.query(SqlAuthSession)
                        .filter(SqlAuthSession.user_id == user.id, SqlAuthSession.revoked_at.is_(None))
                        .update({SqlAuthSession.revoked_at: datetime.now(timezone.utc).replace(tzinfo=None)}, synchronize_session=False)
                    )
                    if revoked:
                        logger.info("Deactivating %s revoked %d live session(s)", username, revoked)
                        # Recorded, not emitted: an audit line written inside the transaction
                        # would claim the sessions were revoked even if the commit then failed,
                        # and that claim is exactly what an operator relies on.
                        sessions_revoked = revoked
            if managed_by is not None:
                user.managed_by = managed_by
            session.flush()
            entity = user.to_mlflow_entity()

        # Past the ``with``: the transaction has committed, so the events are true when written.
        if permitted_conflict is not None:
            _audit_ownership_conflict(username, permitted_conflict, written_by, allowed=True)
        if sessions_revoked:
            _audit_sessions_revoked(username, sessions_revoked, "user_deactivated")
        return entity

    def delete(self, username: str) -> None:
        username = normalize_username(username)
        deleted_sessions = 0
        with self._Session(read_only=False) as session:
            user = get_user(session, username)
            if user is None:
                raise MlflowException(f"User '{username}' not found.")

            self._assert_not_last_active_admin(session, user, "delete")

            # Delete dependent rows first.
            # Without this, SQLAlchemy may try to NULL-out non-nullable FKs
            # (e.g. experiment_permissions.user_id), causing IntegrityError.
            from mlflow_oidc_auth.db.models import (
                SqlExperimentPermission,
                SqlExperimentRegexPermission,
                SqlGatewayEndpointPermission,
                SqlGatewayEndpointRegexPermission,
                SqlGatewayModelDefinitionPermission,
                SqlGatewayModelDefinitionRegexPermission,
                SqlGatewaySecretPermission,
                SqlGatewaySecretRegexPermission,
                SqlRegisteredModelPermission,
                SqlRegisteredModelRegexPermission,
                SqlScorerPermission,
                SqlScorerRegexPermission,
                SqlAuthSession,
                SqlUserGroup,
                SqlUserIdentity,
                SqlWorkspacePermission,
                SqlWorkspaceRegexPermission,
            )

            user_id = user.id

            # Server-side sessions (#310). Same foreign-key requirement as the identities below:
            # a user holding a live session could not otherwise be deleted at all.
            live_sessions = session.query(SqlAuthSession).filter(SqlAuthSession.user_id == user_id, SqlAuthSession.revoked_at.is_(None)).count()
            session.query(SqlAuthSession).filter(SqlAuthSession.user_id == user_id).delete(synchronize_session=False)
            deleted_sessions = live_sessions

            # External identities (#309/#333). The Phase 0 backfill gave *every* pre-existing
            # user a row here, so without this every account that predates that migration is
            # undeletable: the FK on user_identities.user_id refuses the DELETE.
            session.query(SqlUserIdentity).filter(SqlUserIdentity.user_id == user_id).delete(synchronize_session=False)

            # Experiment permissions
            session.query(SqlExperimentPermission).filter(SqlExperimentPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlExperimentRegexPermission).filter(SqlExperimentRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Registered model permissions
            session.query(SqlRegisteredModelPermission).filter(SqlRegisteredModelPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlRegisteredModelRegexPermission).filter(SqlRegisteredModelRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Scorer permissions
            session.query(SqlScorerPermission).filter(SqlScorerPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlScorerRegexPermission).filter(SqlScorerRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Gateway endpoint permissions
            session.query(SqlGatewayEndpointPermission).filter(SqlGatewayEndpointPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlGatewayEndpointRegexPermission).filter(SqlGatewayEndpointRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Gateway secret permissions
            session.query(SqlGatewaySecretPermission).filter(SqlGatewaySecretPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlGatewaySecretRegexPermission).filter(SqlGatewaySecretRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Gateway model definition permissions
            session.query(SqlGatewayModelDefinitionPermission).filter(SqlGatewayModelDefinitionPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlGatewayModelDefinitionRegexPermission).filter(SqlGatewayModelDefinitionRegexPermission.user_id == user_id).delete(
                synchronize_session=False
            )

            # Workspace permissions
            session.query(SqlWorkspacePermission).filter(SqlWorkspacePermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlWorkspaceRegexPermission).filter(SqlWorkspaceRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Group memberships
            session.query(SqlUserGroup).filter(SqlUserGroup.user_id == user_id).delete(synchronize_session=False)

            session.delete(user)
            session.flush()
        # Emitted after the commit, for the same reason as in ``update``.
        if deleted_sessions:
            _audit_sessions_revoked(username, deleted_sessions, "user_deleted")
