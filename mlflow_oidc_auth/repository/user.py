from datetime import datetime, timezone
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
from werkzeug.security import check_password_hash, generate_password_hash

from mlflow_oidc_auth.db.models import SqlAuthSession, SqlGroup, SqlUser
from mlflow_oidc_auth.entities import User
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.ownership import OwnershipDecision, evaluate_write
from mlflow_oidc_auth.repository.utils import get_user

logger = get_logger()


def _audit_ownership_conflict(
    username: str,
    decision,
    written_by: Optional[str],
    *,
    allowed: bool,
    operation: Optional[str] = None,
    actor: Optional[str] = None,
) -> None:
    """Record a write that crossed ownership.

    Emitted in ``report`` mode as well as ``enforce`` — that is what ``report`` is *for*: the
    same event, with ``status`` saying whether it was permitted, so an operator can count what
    enforcement would refuse before enabling it.

    Parameters:
        username: The user row.
        decision: The guard's decision.
        written_by: The source that attempted the write.
        allowed: Whether it went ahead.
        operation: ``delete`` or ``create`` for those writes; omitted for an update.
        actor: Who to name as the actor — an administrator's username, a SCIM token — when the
            caller knows better than ``written_by``.
    """
    from mlflow_oidc_auth.audit import emit_audit_event

    detail = {"owner": decision.owner, "written_by": written_by or "manual", "reason": decision.reason, "permitted": allowed}
    if operation:
        detail["operation"] = operation
    emit_audit_event(
        "user.ownership_conflict",
        actor=actor or written_by or "manual",
        resource_type="user",
        resource_id=username,
        detail=detail,
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


# Hash method for secrets stored in ``users.password_hash`` (issue #336).
#
# Nothing in this plugin stores a human-chosen password. Every value written here comes from
# ``mlflow_oidc_auth.user.generate_token()`` — 24 characters drawn by ``secrets.choice`` from a
# 62-character alphabet, about 143 bits of entropy — and no endpoint accepts an operator-supplied
# password. A memory-hard KDF exists to make brute-forcing *low-entropy* human passwords
# expensive; against 143 bits there is nothing to brute-force, so the ~48 ms that Werkzeug's
# default scrypt costs bought no security while being paid on every basic-authenticated request.
# Verification drops from ~47 ms to ~0.08 ms.
#
# Migration is handled by Werkzeug itself: the method is encoded in the stored hash and
# ``check_password_hash`` dispatches on it, so hashes written before this change keep verifying
# under scrypt, unchanged. Only newly written hashes use this method — a secret moves over when
# its token is rotated. Existing hashes are deliberately never re-hashed in place: a stored
# secret cannot be distinguished from a hypothetical operator-set password, and silently
# re-hashing one at this cost factor would weaken it.
#
# This is intentionally a constant, not configuration. It is a property of what we store, not a
# deployment choice, and the failure mode of setting it wrong is silent.
#
# The entropy premise is not self-enforcing: ``generate_token()`` lives in another module, and
# shortening it or narrowing its alphabet would make this cost factor indefensible without
# anything here changing. ``TestTokenEntropyPremise`` in
# ``tests/repository/test_user_token_hashing.py`` pins the token's length, alphabet and resulting
# entropy, so that change fails a test instead of passing quietly. If one of those tests has to
# be updated, this constant has to be re-justified in the same diff.
TOKEN_HASH_METHOD = "pbkdf2:sha256:1000"

#: "Not supplied", for parameters where None is a meaningful value (clearing an external id).
UNSET = object()


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


def active_admin_ids_for_update(session):
    """Ids of every active administrator, read under a row lock (``SELECT ... FOR UPDATE``).

    The invariant it serves: **there is always at least one active administrator.** Every write
    that could end the last one — deactivation, demotion, deletion — takes this lock inside its
    own transaction before counting, so concurrent writers are serialised on the admin rows.
    """
    return [row[0] for row in active_admin_ids_query(session).all()]


def active_admin_ids_query(session):
    """The locking query behind :func:`active_admin_ids_for_update`, exposed so its SQL can be
    inspected per dialect."""
    return session.query(SqlUser.id).filter(SqlUser.is_admin.is_(True), SqlUser.active.is_(True)).order_by(SqlUser.id).with_for_update()


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
        # Lock every active admin row, this one included, before counting. Without the lock two
        # concurrent transactions deactivating the only two admins each see the other as
        # "remaining", both pass, and the deployment ends with none. With it the second waits for
        # the first to commit and then re-reads the rows (PostgreSQL re-evaluates the WHERE clause
        # of a locking read against the committed version), finds itself alone, and refuses.
        # SQLite has no FOR UPDATE — the dialect drops the clause — but serialises writers anyway.
        remaining = [row_id for row_id in active_admin_ids_for_update(session) if row_id != user.id]
        if not remaining:
            raise MlflowException(
                f"refusing to {action} '{user.username}': they are the only active administrator, and doing so would "
                "leave the deployment with none. Grant admin to another active user first.",
                INVALID_STATE,
            )

    def create(
        self,
        username: str,
        password: str,
        display_name: str,
        is_admin: bool = False,
        is_service_account: bool = False,
        *,
        written_by: Optional[str] = None,
    ) -> User:
        """Create a user row, owned by ``manual``.

        **Create never re-owns (#360).** When the username already exists the create is refused
        with ``RESOURCE_ALREADY_EXISTS`` — whoever asks, in every enforcement mode — and the
        existing row, its owner included, is left exactly as it was. If that row is owned by a
        source other than ``written_by`` the attempt is also recorded as a refused
        ``user.ownership_conflict`` (``operation: create``). This does not depend on the caller
        checking first: the login path refuses a foreign username earlier (#318), but a repository
        that would silently hand an existing row to its caller would be one missing check away from
        an ownership takeover.

        Together with the guard on :meth:`delete`, this is what stops delete-then-create from
        laundering ownership: a source that may not write a row may not delete it either, so it
        cannot clear the name for a create that would come back ``manual``.

        Every row created here is ``manual``, including one a login creates (``docs/scim.md``:
        a first SSO sign-in does not make the provider the owner). A directory creates its rows
        through :meth:`SqlAlchemyStore.create_scim_user`, which writes ``scim``.

        Parameters:
            username: Identity key; folded to lower case.
            password: The initial secret, hashed with :data:`TOKEN_HASH_METHOD`.
            display_name: Display name.
            is_admin: Administrator flag.
            is_service_account: Service-account flag.
            written_by: The source asking, for the audit record of a refused create.

        Returns:
            User: The new user.

        Raises:
            MlflowException: ``RESOURCE_ALREADY_EXISTS`` if the username exists.
        """
        username = normalize_username(username)
        _validate_username(username)
        pwhash = generate_password_hash(password, method=TOKEN_HASH_METHOD)
        with self._Session(read_only=False) as session:
            existing = session.query(SqlUser.managed_by, SqlUser.is_admin).filter(SqlUser.username == username).one_or_none()
            if existing is not None:
                self._refuse_create(username, (existing[0], bool(existing[1])), written_by)
            try:
                u = SqlUser(
                    username=username,
                    password_hash=pwhash,
                    display_name=display_name,
                    is_admin=is_admin,
                    is_service_account=is_service_account,
                )
                session.add(u)
                session.flush()
                return u.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(f"User '{username}' already exists: {e}", RESOURCE_ALREADY_EXISTS) from e

    @staticmethod
    def _refuse_create(username: str, existing, written_by: Optional[str]) -> None:
        owner, is_admin = existing
        decision = evaluate_write(
            owner,
            written_by,
            enforcement=config.MANAGED_BY_ENFORCEMENT,
            fields={"created"},
            target_is_admin=is_admin,
        )
        if decision.conflict:
            # Refused whatever the mode says: a create over an existing row is not a write that
            # ``report`` could let through, because it would replace the row rather than change it.
            refused = OwnershipDecision(
                allowed=False,
                conflict=True,
                owner=decision.owner,
                reason=f"{written_by or 'manual'!r} may not create over a row owned by {decision.owner!r}; create never re-owns",
            )
            _audit_ownership_conflict(username, refused, written_by, allowed=False, operation="create")
        raise MlflowException(f"User '{username}' already exists", RESOURCE_ALREADY_EXISTS)

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
                        SqlUser.password_expiration,
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
                password_hash="REDACTED",
                password_expiration=u.password_expiration,
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

    @staticmethod
    def _changed_fields(user, **supplied) -> set:
        """The fields a write would actually change, for the ownership guard.

        A supplied value equal to the stored one is not a change: a login that re-asserts an
        unchanged admin flag is not writing anything. A new ``password`` or an expiry is always a
        change — secrets are not compared.
        """
        changed = set()
        for name in ("is_admin", "is_service_account", "active", "managed_by", "display_name"):
            value = supplied.get(name)
            if value is not None and value != getattr(user, name):
                changed.add(name)
        external_id = supplied.get("external_id", UNSET)
        if external_id is not UNSET and (external_id or None) != user.external_id:
            changed.add("external_id")
        if supplied.get("password") is not None or supplied.get("password_expiration") is not None:
            changed.add("password")
        return changed

    def update(
        self,
        username: str,
        password: Optional[str] = None,
        password_expiration: Optional[datetime] = None,
        is_admin: Optional[bool] = None,
        is_service_account: Optional[bool] = None,
        active: Optional[bool] = None,
        managed_by: Optional[str] = None,
        written_by: Optional[str] = None,
        admin_override: bool = False,
        display_name: Optional[str] = None,
        external_id=UNSET,
    ) -> User:
        """Update the supplied fields of a user, leaving omitted ones untouched.

        ``None`` means "not supplied" for every parameter but one: the corresponding column is
        left as it is. The defaults for the two flags previously read ``False`` while the guards
        below tested for ``None``, so a caller that omitted them silently cleared ``is_admin``
        and ``is_service_account`` instead of preserving them (issue #338).

        The exception is ``password_expiration``, because expiry is a property of the *secret*
        rather than of the user:

        * When ``password`` is supplied, the secret is being replaced, so it gets a fresh
          lifetime — exactly the one passed in, with ``None`` meaning "does not expire". The
          previous value is never inherited. Inheriting it meant that rotating an already-expired
          token produced a new token that was rejected on its first use, because ``authenticate``
          checks expiry before comparing the hash.
        * When ``password`` is not supplied, the expiry is only changed if one was passed.

        A consequence worth stating: an expiry cannot be cleared without also rotating the
        secret. That is deliberate — extending the life of a credential that has already been
        issued should require issuing a new one.

        Parameters:
            username: Identity key of the user to update.
            password: New secret. Hashed with :data:`TOKEN_HASH_METHOD`.
            password_expiration: Expiry for the stored secret. See the semantics above.
            is_admin: New administrator flag.
            is_service_account: New service-account flag.
            active: Whether the account may authenticate. Setting it False is how a directory
                deprovisions a user (issue #311).
            managed_by: Which source owns this row.
            written_by: Which source is performing this write, for the ownership guard (#319).
                None means an unattributed internal write, treated as ``manual``.
            admin_override: Whether an administrator asked for this explicitly. Break glass:
                always permitted, always audited.
            display_name: New display name.
            external_id: New external id; omit to leave it, None to clear it. Unique when present.

        Returns:
            User: The updated user entity.

        Raises:
            MlflowException: If the user does not exist, if the change would leave the
                deployment with no active administrator, if the ownership guard refuses it, or
                (``RESOURCE_ALREADY_EXISTS``) if ``external_id`` belongs to another user. Nothing
                is written in any of these cases: every field, the session revocation and the
                credential change share one transaction.
        """
        from werkzeug.security import generate_password_hash

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
                fields=self._changed_fields(
                    user,
                    password=password,
                    password_expiration=password_expiration,
                    is_admin=is_admin,
                    is_service_account=is_service_account,
                    active=active,
                    managed_by=managed_by,
                    display_name=display_name,
                    external_id=external_id,
                ),
                target_is_admin=bool(user.is_admin),
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
                    f"User '{username}' is managed by {decision.owner!r} and cannot be changed by {written_by or 'manual'!r}: {decision.reason}.",
                    INVALID_PARAMETER_VALUE,
                )

            if password is not None:
                user.password_hash = generate_password_hash(password, method=TOKEN_HASH_METHOD)
                # A new secret gets the lifetime it was issued with, never the old one's.
                user.password_expiration = password_expiration
            elif password_expiration is not None:
                user.password_expiration = password_expiration
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
            if display_name is not None:
                user.display_name = display_name
            if external_id is not UNSET:
                user.external_id = external_id or None
            try:
                session.flush()
            except IntegrityError as e:
                raise MlflowException(f"external id {external_id!r} is already bound to another user", RESOURCE_ALREADY_EXISTS) from e
            entity = user.to_mlflow_entity()

        # Past the ``with``: the transaction has committed, so the events are true when written.
        if permitted_conflict is not None:
            _audit_ownership_conflict(username, permitted_conflict, written_by, allowed=True)
        if sessions_revoked:
            _audit_sessions_revoked(username, sessions_revoked, "user_deactivated")
        return entity

    @staticmethod
    def _reown_memberships(session, user, managed_by: str) -> list:
        """Set every membership of ``user`` to ``managed_by`` inside ``session``.

        Returns ``(group_name, previous_owner)`` for each row that changed.
        """
        from mlflow_oidc_auth.db.models import SqlUserGroup

        changed = []
        rows = (
            session.query(SqlUserGroup, SqlGroup.group_name)
            .outerjoin(SqlGroup, SqlGroup.id == SqlUserGroup.group_id)
            .filter(SqlUserGroup.user_id == user.id)
            .order_by(SqlUserGroup.id)
            .all()
        )
        for row, group_name in rows:
            previous = row.managed_by or "manual"
            if previous != managed_by:
                row.managed_by = managed_by
                changed.append((group_name if group_name is not None else str(row.group_id), previous))
        return changed

    def hand_over(self, username: str, managed_by: str, *, memberships: bool = False, actor: Optional[str] = None) -> dict:
        """Break glass: hand a user row — and optionally every membership of it — to ``managed_by``.

        One transaction for both halves, so a failure re-owning the memberships leaves the user row
        as it was too: an operator repairing a lockout must never be left with half a repair and no
        record of it. An explicit administrator action, so always permitted; the cross-source
        override is recorded as ``user.ownership_conflict`` once the change has committed.

        Parameters:
            username: The user.
            managed_by: The new owner.
            memberships: Whether to re-own the user's group memberships too.
            actor: The administrator, for the audit record.

        Returns:
            ``{"previous": <old owner>, "memberships": [(group, previous_owner), ...]}``.

        Raises:
            MlflowException: ``RESOURCE_DOES_NOT_EXIST`` for an unknown user. Nothing is written.
        """
        username = normalize_username(username)
        with self._Session(read_only=False) as session:
            user = get_user(session, username)
            previous = user.managed_by
            decision = None
            if (previous or "manual") != managed_by:
                # Only an actual change of the user row's owner is an override worth recording; a
                # call that only re-owns memberships (the row already has this owner) is not.
                decision = evaluate_write(
                    previous,
                    "manual",
                    enforcement=config.MANAGED_BY_ENFORCEMENT,
                    admin_override=True,
                    fields={"managed_by"},
                    target_is_admin=bool(user.is_admin),
                )
                user.managed_by = managed_by
            changed = self._reown_memberships(session, user, managed_by) if memberships else []
            session.flush()
        if decision is not None and decision.conflict:
            _audit_ownership_conflict(username, decision, "manual", allowed=True, actor=actor)
        return {"previous": previous, "memberships": changed}

    def delete(
        self,
        username: str,
        before_cascade: Optional[Callable] = None,
        after_cascade: Optional[Callable] = None,
        *,
        written_by: Optional[str] = None,
        admin_override: bool = False,
        actor: Optional[str] = None,
    ) -> None:
        """Hard-delete a user and every row that references them, through the ownership guard.

        **Ownership (#360).** Deleting a row is the largest write there is, so it goes through
        :func:`evaluate_write` like :meth:`update` does, before anything else — before the
        last-admin check, before the orphan hooks. A source that may not write a row may not delete
        it: under ``enforce`` the delete is refused (``INVALID_PARAMETER_VALUE``) and audited as a
        refused ``user.ownership_conflict`` (``operation: delete``); under ``report`` it proceeds and
        the conflict is recorded once the delete has committed. ``admin_override`` is the break
        glass: always permitted, always recorded. A directory may not delete a hand-made
        administrator under ``enforce``.

        Parameters:
            username: The user.
            before_cascade: Optional ``(session, user) -> None`` run inside the same transaction
                after the last-admin check and before any grant is removed — orphan detection
                (#324) uses it to read the grants the cascade is about to remove.
            after_cascade: Optional ``(session) -> None`` run inside the same transaction once
                the cascade and the user row's delete have been flushed, before the commit — the
                orphan hand-over uses it, so nothing is written for a delete that fails, and a
                savepoint it opens is nested inside an already-begun transaction (on SQLite a
                savepoint opened before any write would itself begin, and its release commit,
                the transaction).
            written_by: The source deleting the row. None is an unattributed write, treated as
                ``manual``.
            admin_override: Break glass for a row another source owns.
            actor: Who to name in the audit event (an administrator, a SCIM token).

        Raises:
            MlflowException: ``RESOURCE_DOES_NOT_EXIST`` for an unknown user;
                ``INVALID_PARAMETER_VALUE`` when the ownership guard refuses; ``INVALID_STATE`` for
                the last active administrator. Nothing is written in any of these cases.
        """
        username = normalize_username(username)
        deleted_sessions = 0
        permitted_conflict = None
        with self._Session(read_only=False) as session:
            user = get_user(session, username)
            if user is None:
                raise MlflowException(f"User '{username}' not found.")

            decision = evaluate_write(
                getattr(user, "managed_by", None),
                written_by,
                enforcement=config.MANAGED_BY_ENFORCEMENT,
                admin_override=admin_override,
                fields={"deleted"},
                target_is_admin=bool(user.is_admin),
            )
            if decision.conflict and not decision.allowed:
                _audit_ownership_conflict(username, decision, written_by, allowed=False, operation="delete", actor=actor)
                raise MlflowException(
                    f"User '{username}' is managed by {decision.owner!r} and cannot be deleted by {written_by or 'manual'!r}: {decision.reason}.",
                    INVALID_PARAMETER_VALUE,
                )
            if decision.conflict:
                permitted_conflict = decision

            self._assert_not_last_active_admin(session, user, "delete")

            if before_cascade is not None:
                before_cascade(session, user)

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

            if after_cascade is not None:
                after_cascade(session)

        # Emitted after the commit, for the same reason as in ``update``.
        if permitted_conflict is not None:
            _audit_ownership_conflict(username, permitted_conflict, written_by, allowed=True, operation="delete", actor=actor)
        if deleted_sessions:
            _audit_sessions_revoked(username, deleted_sessions, "user_deleted")

    def authenticate(self, username: str, password: str) -> bool:
        username = normalize_username(username)
        with self._Session() as session:
            try:
                user = get_user(session, username)
                expiration = user.password_expiration
                if expiration is not None:
                    # Normalize into a local, so the comparison does not mark the
                    # persistent user row dirty and flush an UPDATE on every login.
                    if expiration.tzinfo is None:
                        expiration = expiration.replace(tzinfo=timezone.utc)
                    if expiration < datetime.now(timezone.utc):
                        return False
                return check_password_hash(getattr(user, "password_hash"), password)
            except MlflowException:
                return False
