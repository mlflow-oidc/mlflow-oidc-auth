"""Groups and group membership.

**Membership ownership (#360).** Every ``user_groups`` row records which source granted it in
``managed_by``: ``manual`` (unattributed, or an administrator), ``scim`` (the directory, #323), or
``oidc:<provider>`` / ``saml:<provider>`` (a login's claims). Group membership is the privilege
carrier, so the ``managed_by`` guard (:mod:`mlflow_oidc_auth.ownership`) covers it row by row:

* **Adding** a membership is never a cross-source write. It creates a row the writer owns. A row
  that already exists keeps its owner — nothing here re-owns a membership.
* **Removing** one depends on who owns the row and on the kind of write. ``manual`` rows are
  removable by any source (they are what every membership written before #360 is, so an
  authoritative login keeps revoking them exactly as it did), and a source's own rows by it.
* A **sync** (:meth:`GroupRepository.set_groups_for_user`, a SCIM ``PUT``) states the whole
  membership the writer wants, and **never removes another source's row, in any mode**; it is
  recorded as a conflict under ``report`` and ``enforce``. Refusing the whole sync would stop a
  directory or an IdP from ever updating that user or group again, and removing the row would
  undo the other source's decision at every sign-in.
* A **targeted** removal (SCIM ``PATCH`` ``remove``) of another source's row goes through
  :func:`~mlflow_oidc_auth.ownership.evaluate_write`: removed and recorded under ``report``,
  refused atomically under ``enforce``, removed silently under ``off``.

**Group ownership.** Groups carry ``managed_by`` too. Every group-centric write here (SCIM
``/Groups``) checks the group's owner with
:func:`~mlflow_oidc_auth.ownership.evaluate_group_write` before anything else: only the owning
source writes a group under ``enforce``.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST, INVALID_STATE
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.db.models import SqlGroup, SqlUser, SqlUserGroup
from mlflow_oidc_auth.entities import User
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.ownership import MANUAL, Enforcement, OwnershipDecision, evaluate_group_write, evaluate_write
from mlflow_oidc_auth.repository.utils import get_group, get_user

logger = get_logger()

#: What a membership removal changes, for :func:`evaluate_write`. Not in ``LOGIN_WRITABLE_FIELDS``:
#: a login may re-assert a directory-owned user's admin flag, never remove the directory's grants.
MEMBERSHIP_FIELD = "membership"

#: "Not supplied", where None is a meaningful value (clearing an external id).
UNSET = object()


@dataclass
class MembershipConflict:
    """One membership row a write crossed ownership on.

    Attributes:
        username: The member.
        group_name: The group.
        decision: What :func:`evaluate_write` decided.
    """

    username: str
    group_name: str
    decision: OwnershipDecision
    #: A sync left this row in place because another source owns it. Nothing was refused — a sync
    #: never removes another source's row — so it is recorded as ``membership.sync_kept`` with
    #: ``status="success"`` rather than as a denial.
    kept: bool = False


@dataclass
class MembershipOutcome:
    """What a membership write did.

    Attributes:
        added: ``(username, group_name)`` rows created, owned by the writer.
        removed: ``(username, group_name)`` rows deleted.
        conflicts: Cross-source rows. ``decision.allowed`` says whether each was removed (``report``,
            an override) or kept (``enforce``).
    """

    added: List[Tuple[str, str]] = field(default_factory=list)
    removed: List[Tuple[str, str]] = field(default_factory=list)
    conflicts: List[MembershipConflict] = field(default_factory=list)

    @property
    def refused(self) -> List[MembershipConflict]:
        return [c for c in self.conflicts if not c.decision.allowed]

    @property
    def changed(self) -> bool:
        return bool(self.added or self.removed)


def audit_membership_conflicts(
    outcome: MembershipOutcome, written_by: Optional[str], *, actor: Optional[str] = None, operation: str = "membership.remove"
) -> None:
    """Record every cross-source membership row as ``user.ownership_conflict``.

    The same event the user-row guard emits, with ``detail.operation`` and ``detail.group``, so one
    query over the audit log counts everything ``enforce`` would refuse before it is turned on.
    Called only once the write has committed (or, for a refused targeted write, once nothing was
    written): the record must not claim a removal a rollback undid.
    """
    from mlflow_oidc_auth.audit import emit_audit_event

    for conflict in outcome.conflicts:
        decision = conflict.decision
        emit_audit_event(
            "user.ownership_conflict",
            actor=actor or written_by or MANUAL,
            resource_type="user",
            resource_id=conflict.username,
            detail={
                "owner": decision.owner,
                "written_by": written_by or MANUAL,
                "reason": decision.reason,
                "permitted": decision.allowed,
                "operation": "membership.sync_kept" if conflict.kept else operation,
                "group": conflict.group_name,
            },
            # A kept row is the sync working as designed, not a refusal: counting it as denied would
            # inflate every denial count by one per foreign membership per sign-in.
            status="success" if (decision.allowed or conflict.kept) else "denied",
        )


def _evaluate_removal(row: SqlUserGroup, user: SqlUser, written_by: Optional[str], admin_override: bool) -> OwnershipDecision:
    """Whether ``written_by`` may remove this membership row.

    ``target_is_admin`` carries the user's admin flag, so the directory may not strip a hand-made
    administrator's hand-made memberships under ``enforce`` — the same rule as for the user row.
    """
    return evaluate_write(
        row.managed_by,
        written_by,
        enforcement=config.MANAGED_BY_ENFORCEMENT,
        admin_override=admin_override,
        fields={MEMBERSHIP_FIELD},
        target_is_admin=bool(user.is_admin),
    )


def _refusal(conflicts: Sequence[MembershipConflict], written_by: Optional[str]) -> MlflowException:
    first = conflicts[0]
    return MlflowException(
        f"Membership of '{first.username}' in '{first.group_name}' is managed by {first.decision.owner!r} and cannot be removed by "
        f"{written_by or MANUAL!r}: {first.decision.reason}.",
        INVALID_PARAMETER_VALUE,
    )


class UnknownMember(MlflowException):
    """A membership write named a user that does not exist (or that the writer may not see)."""

    def __init__(self, username: str):
        super().__init__(f"User '{username}' not found", RESOURCE_DOES_NOT_EXIST)
        self.username = username


class MembershipRefused(MlflowException):
    """A targeted membership write refused by the ownership guard. Nothing was written.

    Carries the outcome so the caller can audit the refusals after the rollback.
    """

    def __init__(self, outcome: MembershipOutcome, written_by: Optional[str]):
        base = _refusal(outcome.refused, written_by)
        super().__init__(base.message, INVALID_PARAMETER_VALUE)
        self.outcome = outcome


class GroupWriteRefused(MlflowException):
    """A SCIM (or other source's) write to a group another source owns, refused. Nothing was written."""

    def __init__(self, group_name: str, decision: OwnershipDecision, written_by: Optional[str]):
        super().__init__(
            f"Group '{group_name}' is managed by {decision.owner!r} and cannot be changed by {written_by or MANUAL!r}: {decision.reason}.",
            INVALID_PARAMETER_VALUE,
        )
        self.group_name = group_name
        self.decision = decision


def audit_group_conflict(group_name: str, decision: OwnershipDecision, written_by: Optional[str], *, actor: Optional[str], operation: str) -> None:
    """Record a write to a group owned by another source as ``group.ownership_conflict``."""
    from mlflow_oidc_auth.audit import emit_audit_event

    emit_audit_event(
        "group.ownership_conflict",
        actor=actor or written_by or MANUAL,
        resource_type="group",
        resource_id=group_name,
        detail={
            "owner": decision.owner,
            "written_by": written_by or MANUAL,
            "reason": decision.reason,
            "permitted": decision.allowed,
            "operation": operation,
        },
        status="success" if decision.allowed else "denied",
    )


def _foreign_sync_row(row: SqlUserGroup, written_by: Optional[str], admin_override: bool) -> Optional[OwnershipDecision]:
    """The decision for a sync meeting a membership another source owns, or None if it is not one.

    **A sync never removes another source's membership, in any mode** — only its own and unowned
    (``manual``) ones. Every membership that predates ownership is ``manual``, so a deployment that
    changes nothing sees no change, while a directory's memberships stop vanishing at each sign-in
    (Entra and Okta do not re-send a membership they believe exists). The skipped row is recorded in
    **every** mode as ``membership.sync_kept`` — a success, not a denial — and under ``off`` it is
    also logged, because ``off`` otherwise evaluates nothing. An administrator override is the one
    exception: it removes, and is recorded.
    """
    owner = row.managed_by or MANUAL
    if owner in (MANUAL, written_by or MANUAL):
        return None
    if admin_override:
        return OwnershipDecision(allowed=True, conflict=True, owner=owner, reason=f"administrator override: removing a membership owned by {owner!r}")
    return OwnershipDecision(
        allowed=False,
        conflict=True,
        owner=owner,
        reason=f"a sync by {written_by or MANUAL!r} removes only its own and unowned memberships, not one owned by {owner!r}; left in place",
    )


def _log_kept_under_off(subject: str, outcome: MembershipOutcome, written_by: Optional[str]) -> None:
    """Once per sync under ``off``: say which foreign memberships were left in place.

    ``off`` evaluates nothing else, so without this a sync keeping another source's rows would be
    visible only in the audit log. The usual cause is a renamed provider (``oidc:kc`` →
    ``oidc:keycloak``) or an OIDC → SAML migration: the old rows now look foreign, and
    ``reconcile-ownership --memberships --from-owner <old> --set-owner <new>`` is the fix.
    """
    if config.MANAGED_BY_ENFORCEMENT != Enforcement.OFF:
        return
    kept = [c for c in outcome.conflicts if c.kept]
    if kept:
        logger.info(
            "Sync by %s kept %d membership(s) of %s owned by other sources: %s",
            written_by or MANUAL,
            len(kept),
            subject,
            sorted({c.decision.owner for c in kept}),
        )


class GroupRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def create_group(self, group_name: str) -> None:
        """
        Create a new group.
        :param group_name: The name of the group to be created.
        :raises MlflowException: If the group already exists.
        """
        with self._Session(read_only=False) as session:
            try:
                grp = SqlGroup(group_name=group_name)
                session.add(grp)
                session.flush()
            except IntegrityError as e:
                raise MlflowException(f"Group '{group_name}' exists: {e}", RESOURCE_ALREADY_EXISTS)

    def create_groups(self, group_names: List[str], written_by: Optional[str] = None) -> None:
        """Create whichever of ``group_names`` do not exist yet, owned by ``written_by``.

        An existing group keeps its owner. A login passes its source (``oidc:<id>`` /
        ``saml:<id>``), so the groups its claims bring into existence are the provider's and a SCIM
        token may not write them under ``enforce``.

        :param group_names: A list of group names to be created.
        :param written_by: The creating source; None means ``manual``.
        """
        with self._Session(read_only=False) as session:
            for group_name in group_names:
                group = session.query(SqlGroup).filter(SqlGroup.group_name == group_name).first()
                if group is None:
                    group = SqlGroup(group_name=group_name, managed_by=written_by or MANUAL)
                    session.add(group)
            session.flush()

    def list_groups(self) -> List[str]:
        """
        List all groups.
        :return: A list of group names.
        """
        with self._Session() as session:
            return [g.group_name for g in session.query(SqlGroup).all()]

    def delete_group(self, group_name: str) -> None:
        """
        Delete a group by its name.
        :param group_name: The name of the group to be deleted.
        :raises MlflowException: If the group does not exist or if multiple groups with the same name exist.
        """
        with self._Session(read_only=False) as session:
            try:
                grp = session.query(SqlGroup).filter(SqlGroup.group_name == group_name).one()
                session.delete(grp)
                session.flush()
            except NoResultFound:
                raise MlflowException(f"Group '{group_name}' not found", RESOURCE_DOES_NOT_EXIST)
            except MultipleResultsFound:
                raise MlflowException(f"Multiple groups named '{group_name}'", INVALID_STATE)

    def add_user_to_group(self, username: str, group_name: str, *, written_by: Optional[str] = None) -> None:
        """Add a user to a group, as a membership ``written_by`` owns.

        Parameters:
            username: The member.
            group_name: The group.
            written_by: The source granting it, recorded as the row's ``managed_by``. None means
                ``manual``.
        """
        with self._Session(read_only=False) as session:
            user = get_user(session, username)
            grp = get_group(session, group_name)
            link = SqlUserGroup(user_id=user.id, group_id=grp.id, managed_by=written_by or MANUAL)
            session.add(link)
            session.flush()

    def remove_user_from_group(
        self,
        username: str,
        group_name: str,
        *,
        written_by: Optional[str] = None,
        admin_override: bool = False,
        actor: Optional[str] = None,
    ) -> None:
        """Remove one membership, through the ownership guard.

        A targeted removal: under ``enforce`` a row another source owns is refused and nothing is
        written. Every cross-source removal is audited.

        Raises:
            MlflowException: ``INVALID_PARAMETER_VALUE`` when the guard refuses it; the lookup
                errors when the user, group or membership does not exist.
        """
        outcome = MembershipOutcome()
        try:
            with self._Session(read_only=False) as session:
                user = get_user(session, username)
                grp = get_group(session, group_name)
                ug = session.query(SqlUserGroup).filter(SqlUserGroup.user_id == user.id, SqlUserGroup.group_id == grp.id).one()
                self._remove_rows(session, [(ug, user, grp.group_name)], outcome, written_by=written_by, admin_override=admin_override, strict=True)
                session.flush()
        except MembershipRefused as refused:
            audit_membership_conflicts(MembershipOutcome(conflicts=refused.outcome.refused), written_by, actor=actor)
            raise
        audit_membership_conflicts(outcome, written_by, actor=actor)

    # ------------------------------------------------------------------------------------------
    # Ownership-aware membership writes (#360)
    # ------------------------------------------------------------------------------------------

    @staticmethod
    def _remove_rows(session, rows, outcome: MembershipOutcome, *, written_by: Optional[str], admin_override: bool, strict: bool, sync: bool = False) -> None:
        """Delete the membership rows the guard permits, recording every conflict in ``outcome``.

        ``rows`` are ``(SqlUserGroup, SqlUser, group_name)``. With ``strict`` a refusal raises
        :class:`MembershipRefused` after every row has been evaluated — the caller's transaction
        then rolls back, so a targeted write is all-or-nothing. Without it a refused row is left in
        place and the rest proceeds. With ``sync`` another source's rows are never removed, in any
        mode (see :func:`_foreign_sync_row`).
        """
        refused_here = False
        for row, user, group_name in rows:
            decision = _foreign_sync_row(row, written_by, admin_override) if sync else None
            if decision is None:
                decision = _evaluate_removal(row, user, written_by, admin_override)
            # Outside a strict (targeted) write, a row the guard does not permit removing is simply
            # left in place and the request succeeds — including a hand-made administrator's
            # membership a SCIM sync may not strip. That is "kept", never "denied": only a refused
            # targeted removal is a denial.
            kept = not decision.allowed and not strict
            if decision.conflict:
                outcome.conflicts.append(MembershipConflict(user.username, group_name, decision, kept=kept))
            if decision.allowed:
                session.delete(row)
                outcome.removed.append((user.username, group_name))
            else:
                refused_here = True
        if strict and refused_here:
            raise MembershipRefused(outcome, written_by)

    def set_groups_for_user(
        self,
        username: str,
        group_names: List[str],
        *,
        written_by: Optional[str] = None,
        admin_override: bool = False,
        actor: Optional[str] = None,
    ) -> MembershipOutcome:
        """Make ``group_names`` the user's membership as far as ``written_by`` may — a sync.

        Called with the membership a login's claims produce (``provisioning_policy.groups_to_apply``),
        a bearer or service-account first authentication, or an administrator.

        * A group in ``group_names`` the user is not in: a membership is created, owned by
          ``written_by``.
        * A group the user is already in: left as it is, including its owner. A login re-asserting
          a membership the directory granted does not take it over.
        * A membership not in ``group_names``: removed if it is ``written_by``'s own or unowned
          (``manual``). So an ``authoritative`` provider keeps revoking what its claims no longer
          assert, including every membership written before #360, and ``group_sync_mode:
          additive`` — which passes the current membership back in — still never removes
          anything. A row another source owns is **never removed, in any mode** (see
          :func:`_foreign_sync_row`); it is recorded under ``report`` and ``enforce``.

        The sync never raises for an ownership refusal: refusing a login because the directory also
        grants the user a group would lock every directory-provisioned user out of SSO under
        ``enforce``. The refusal is the row that was not removed, and its audit event.

        Duplicates in ``group_names`` are ignored: some IdPs (Microsoft Entra ID) emit the same
        group more than once when a user holds several app roles backed by one group.

        Parameters:
            username: The user.
            group_names: The full membership ``written_by`` asserts. Every group must exist.
            written_by: The source performing the sync — ``oidc:<id>``, ``saml:<id>``, ``scim`` or
                ``manual``. None is an unattributed write, treated as ``manual``.
            admin_override: Break glass: remove other sources' memberships too, audited.
            actor: Who to name in audit events; defaults to ``written_by``.

        Returns:
            MembershipOutcome: What was added and removed, and every cross-source row.
        """
        group_names = list(dict.fromkeys(group_names))
        outcome = MembershipOutcome()
        with self._Session(read_only=False) as session:
            user = get_user(session, username)
            wanted: Dict[int, str] = {}
            for group_name in group_names:
                group = get_group(session, group_name)
                wanted[group.id] = group.group_name
            existing = (
                session.query(SqlUserGroup, SqlGroup.group_name)
                .outerjoin(SqlGroup, SqlGroup.id == SqlUserGroup.group_id)
                .filter(SqlUserGroup.user_id == user.id)
                .order_by(SqlUserGroup.id)
                .all()
            )
            held = {row.group_id for row, _ in existing}
            stale = [(row, user, name if name is not None else str(row.group_id)) for row, name in existing if row.group_id not in wanted]
            self._remove_rows(session, stale, outcome, written_by=written_by, admin_override=admin_override, strict=False, sync=True)
            for group_id, group_name in wanted.items():
                if group_id not in held:
                    session.add(SqlUserGroup(user_id=user.id, group_id=group_id, managed_by=written_by or MANUAL))
                    outcome.added.append((user.username, group_name))
            session.flush()
        # After the commit: the events describe what the database now holds.
        audit_membership_conflicts(outcome, written_by, actor=actor)
        _log_kept_under_off(f"user {username}", outcome, written_by)
        return outcome

    def list_group_members(self, group_name: str) -> List[User]:
        """
        List all users in a group.
        :param group_name: The name of the group.
        :return: A list of users in the group.
        """
        with self._Session() as session:
            grp = get_group(session, group_name)
            user_ids = [ug.user_id for ug in session.query(SqlUserGroup).filter(SqlUserGroup.group_id == grp.id)]
            users = session.query(SqlUser).filter(SqlUser.id.in_(user_ids)).all()
            return [user.to_mlflow_entity() for user in users]

    def list_groups_for_user(self, username: str) -> List[str]:
        """
        List all groups for a user.
        :param username: The username of the user.
        :return: A list of group names for the user.

        Resolved in a single JOIN. This runs on every group-scoped permission check,
        so the round-trips matter more than the (tiny) per-query cost — see issue #253.
        """
        with self._Session() as session:
            rows = (
                session.query(SqlGroup.group_name)
                .join(SqlUserGroup, SqlGroup.id == SqlUserGroup.group_id)
                .join(SqlUser, SqlUser.id == SqlUserGroup.user_id)
                .filter(SqlUser.username == username)
                .order_by(SqlGroup.id)
                .all()
            )
            return [r[0] for r in rows]

    def list_group_ids_for_user(self, username: str) -> List[int]:
        """
        List all group IDs for a user.
        :param username: The username of the user.
        :return: A list of group IDs for the user.

        Deliberately joins user_groups directly rather than through groups: routing via
        SqlGroup would silently drop membership rows whose group no longer exists, which
        would change behaviour rather than just the query count.
        """
        with self._Session() as session:
            rows = session.query(SqlUserGroup.group_id).join(SqlUser, SqlUser.id == SqlUserGroup.user_id).filter(SqlUser.username == username).all()
            return [r[0] for r in rows]

    def set_membership_owner(self, username: str, managed_by: str) -> List[Tuple[str, str]]:
        """Hand every membership of ``username`` to ``managed_by``. Break glass, not guarded (#360).

        The membership half of ``PATCH /api/2.0/mlflow/users/ownership``: when a source is
        decommissioned, the memberships it owns can no longer be removed by any other source under
        ``enforce``. The caller is an administrator and audits the change.

        Returns:
            ``(group_name, previous_owner)`` for every row that changed.
        """
        changed: List[Tuple[str, str]] = []
        with self._Session(read_only=False) as session:
            user = get_user(session, username)
            rows = (
                session.query(SqlUserGroup, SqlGroup.group_name)
                .outerjoin(SqlGroup, SqlGroup.id == SqlUserGroup.group_id)
                .filter(SqlUserGroup.user_id == user.id)
                .order_by(SqlUserGroup.id)
                .all()
            )
            for row, group_name in rows:
                previous = row.managed_by or MANUAL
                if previous != managed_by:
                    row.managed_by = managed_by
                    changed.append((group_name if group_name is not None else str(row.group_id), previous))
            session.flush()
        return changed

    # ------------------------------------------------------------------------------------------
    # Directory-managed groups: SCIM /Groups (#323)
    # ------------------------------------------------------------------------------------------

    @staticmethod
    def _group_detail(group: SqlGroup) -> dict:
        return {
            "group_name": group.group_name,
            "external_id": group.external_id,
            "managed_by": group.managed_by or MANUAL,
            "created_at": group.created_at,
            "updated_at": group.updated_at,
        }

    @staticmethod
    def _members_by_group(session, group_ids: Sequence[int], *, include_service_accounts: bool) -> Dict[int, List[dict]]:
        """Members of each group in one statement, in membership order."""
        members: Dict[int, List[dict]] = {group_id: [] for group_id in group_ids}
        if not group_ids:
            return members
        q = (
            session.query(SqlUserGroup.group_id, SqlUser.username, SqlUser.display_name, SqlUserGroup.managed_by)
            .join(SqlUser, SqlUser.id == SqlUserGroup.user_id)
            .filter(SqlUserGroup.group_id.in_(list(group_ids)))
        )
        if not include_service_accounts:
            q = q.filter(SqlUser.is_service_account.is_(False))
        for group_id, username, display_name, managed_by in q.order_by(SqlUserGroup.id).all():
            members[group_id].append({"username": username, "display_name": display_name, "managed_by": managed_by or MANUAL})
        return members

    def list_group_details_page(
        self,
        *,
        group_name: Optional[str] = None,
        external_id: Optional[str] = None,
        offset: int = 0,
        limit: Optional[int] = None,
        with_members: bool = True,
        include_service_accounts: bool = False,
    ) -> Tuple[int, List[dict]]:
        """A page of groups as plain dicts, optionally with their members.

        Three statements at most: the total, the page, and the members of the page's groups.

        Parameters:
            group_name: Exact name filter.
            external_id: Exact external id filter.
            offset: Rows to skip.
            limit: Maximum rows; None for all.
            with_members: Whether to load members (``excludedAttributes=members`` skips it).
            include_service_accounts: Whether service-account members are listed. SCIM never sees
                them.

        Returns:
            ``(total, rows)``; each row has ``group_name``, ``external_id``, ``created_at``,
            ``updated_at`` and, with ``with_members``, ``members`` as
            ``[{"username", "display_name", "managed_by"}]``.
        """
        with self._Session() as session:
            q = session.query(SqlGroup)
            if group_name is not None:
                q = q.filter(SqlGroup.group_name == group_name)
            if external_id is not None:
                q = q.filter(SqlGroup.external_id == external_id)
            total = q.count()
            q = q.order_by(SqlGroup.id).offset(max(0, offset))
            if limit is not None:
                q = q.limit(max(0, limit))
            groups = q.all()
            rows = [self._group_detail(g) for g in groups]
            if with_members:
                members = self._members_by_group(session, [g.id for g in groups], include_service_accounts=include_service_accounts)
                for group, row in zip(groups, rows):
                    row["members"] = members[group.id]
            return total, rows

    def get_group_detail(self, group_name: str, *, with_members: bool = True, include_service_accounts: bool = False) -> Optional[dict]:
        """One group (see :meth:`list_group_details_page`), or None."""
        _, rows = self.list_group_details_page(group_name=group_name, limit=1, with_members=with_members, include_service_accounts=include_service_accounts)
        return rows[0] if rows else None

    @staticmethod
    def _resolve_members(session, usernames: Iterable[str], *, include_service_accounts: bool) -> List[SqlUser]:
        """The user rows for ``usernames``, in order, deduplicated. Raises :class:`UnknownMember`."""
        from mlflow_oidc_auth.repository.user import normalize_username

        users: List[SqlUser] = []
        seen = set()
        for raw in usernames:
            username = normalize_username(raw)
            if username in seen:
                continue
            seen.add(username)
            user = session.query(SqlUser).filter(SqlUser.username == username).one_or_none()
            if user is None or (user.is_service_account and not include_service_accounts):
                raise UnknownMember(username)
            users.append(user)
        return users

    @staticmethod
    def _assert_external_id_free(session, external_id: Optional[str], group_id: Optional[int]) -> None:
        if not external_id:
            return
        holder = session.query(SqlGroup.id).filter(SqlGroup.external_id == external_id).one_or_none()
        if holder is not None and holder[0] != group_id:
            raise MlflowException(f"external id {external_id!r} is already bound to another group", RESOURCE_ALREADY_EXISTS)

    def create_directory_group(self, group_name: str, external_id: Optional[str], members: Sequence[str], *, written_by: str) -> dict:
        """Create a group and its initial members in one transaction.

        Every membership is owned by ``written_by``. Nothing is written if any member is unknown or
        the name or external id is taken.

        Raises:
            MlflowException: ``RESOURCE_ALREADY_EXISTS`` for a taken name or external id;
                :class:`UnknownMember` for a member that does not exist or is a service account.
        """
        with self._Session(read_only=False) as session:
            if session.query(SqlGroup.id).filter(SqlGroup.group_name == group_name).first() is not None:
                raise MlflowException(f"Group '{group_name}' exists", RESOURCE_ALREADY_EXISTS)
            self._assert_external_id_free(session, external_id, None)
            users = self._resolve_members(session, members, include_service_accounts=False)
            group = SqlGroup(group_name=group_name, external_id=external_id or None, managed_by=written_by)
            session.add(group)
            try:
                session.flush()
            except IntegrityError as e:
                raise MlflowException(f"Group '{group_name}' or its external id already exists", RESOURCE_ALREADY_EXISTS) from e
            for user in users:
                session.add(SqlUserGroup(user_id=user.id, group_id=group.id, managed_by=written_by))
            session.flush()
            detail = self._group_detail(group)
            detail["members"] = self._members_by_group(session, [group.id], include_service_accounts=False)[group.id]
            return detail

    def apply_group_changes(
        self,
        group_name: str,
        operations: Sequence[Tuple[str, Optional[Sequence[str]]]],
        *,
        written_by: str,
        external_id=UNSET,
        admin_override: bool = False,
        actor: Optional[str] = None,
    ) -> Tuple[MembershipOutcome, dict]:
        """Apply one directory change set to a group, in order, in a single transaction.

        ``operations`` are ``(kind, usernames)``:

        ``("add", [...])``
            Add each user; an existing membership keeps its owner. Never a cross-source write.
        ``("remove", [...])`` / ``("remove", None)``
            Targeted: remove those users (``None``: every member). A row another source owns is
            refused under ``enforce`` and the **whole change set** is rolled back.
        ``("replace", [...])``
            A sync: add the missing, remove the rest through the guard, and leave a row another
            source owns in place under ``enforce`` — refusing it would stop the directory from ever
            updating the group again.

        Service-account memberships are outside the directory's view and never touched.

        Returns:
            ``(outcome, detail)`` — what changed, and the group as it now is.

        Raises:
            MlflowException: ``RESOURCE_DOES_NOT_EXIST`` for an unknown group; :class:`UnknownMember`;
                :class:`MembershipRefused` (``INVALID_PARAMETER_VALUE``) when a targeted removal is
                refused; ``RESOURCE_ALREADY_EXISTS`` for an external id another group holds.
        """
        from datetime import datetime, timezone

        outcome = MembershipOutcome()
        group_decision = None
        try:
            with self._Session(read_only=False) as session:
                group = get_group(session, group_name)
                group_decision = evaluate_group_write(group.managed_by, written_by, enforcement=config.MANAGED_BY_ENFORCEMENT, admin_override=admin_override)
                if not group_decision.allowed:
                    raise GroupWriteRefused(group.group_name, group_decision, written_by)
                if external_id is not UNSET:
                    self._assert_external_id_free(session, external_id, group.id)
                    group.external_id = external_id or None

                def current():
                    return {
                        user.id: (row, user)
                        for row, user in session.query(SqlUserGroup, SqlUser)
                        .join(SqlUser, SqlUser.id == SqlUserGroup.user_id)
                        .filter(SqlUserGroup.group_id == group.id, SqlUser.is_service_account.is_(False))
                        .order_by(SqlUserGroup.id)
                        .all()
                    }

                for kind, usernames in operations:
                    members = current()
                    if kind == "add":
                        for user in self._resolve_members(session, usernames or [], include_service_accounts=False):
                            if user.id not in members:
                                session.add(SqlUserGroup(user_id=user.id, group_id=group.id, managed_by=written_by))
                                outcome.added.append((user.username, group.group_name))
                    elif kind == "remove":
                        if usernames is None:
                            targets = list(members.values())
                        else:
                            ids = {user.id for user in self._resolve_members(session, usernames, include_service_accounts=False)}
                            targets = [members[i] for i in members if i in ids]
                        rows = [(row, user, group.group_name) for row, user in targets]
                        self._remove_rows(session, rows, outcome, written_by=written_by, admin_override=admin_override, strict=True)
                    elif kind == "replace":
                        wanted = self._resolve_members(session, usernames or [], include_service_accounts=False)
                        wanted_ids = {user.id for user in wanted}
                        rows = [(row, user, group.group_name) for uid, (row, user) in members.items() if uid not in wanted_ids]
                        self._remove_rows(session, rows, outcome, written_by=written_by, admin_override=admin_override, strict=False, sync=True)
                        for user in wanted:
                            if user.id not in members:
                                session.add(SqlUserGroup(user_id=user.id, group_id=group.id, managed_by=written_by))
                                outcome.added.append((user.username, group.group_name))
                    else:
                        raise MlflowException(f"Unknown membership operation {kind!r}", INVALID_PARAMETER_VALUE)
                    try:
                        session.flush()
                    except IntegrityError as e:
                        # A concurrent write added the same membership first. Refused, and rolled
                        # back with the rest of the change set; the directory retries.
                        raise MlflowException(f"Membership of '{group_name}' changed concurrently; retry", RESOURCE_ALREADY_EXISTS) from e
                if outcome.changed:
                    group.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                try:
                    session.flush()
                except IntegrityError as e:
                    raise MlflowException(f"external id {external_id!r} is already bound to another group", RESOURCE_ALREADY_EXISTS) from e
                detail = self._group_detail(group)
                detail["members"] = self._members_by_group(session, [group.id], include_service_accounts=False)[group.id]
        except GroupWriteRefused as refused:
            audit_group_conflict(refused.group_name, refused.decision, written_by, actor=actor, operation="group.write")
            raise
        except MembershipRefused as refused:
            audit_membership_conflicts(MembershipOutcome(conflicts=refused.outcome.refused), written_by, actor=actor)
            raise
        if group_decision is not None and group_decision.conflict:
            audit_group_conflict(detail["group_name"], group_decision, written_by, actor=actor, operation="group.write")
        audit_membership_conflicts(outcome, written_by, actor=actor)
        _log_kept_under_off(f"group {detail['group_name']}", outcome, written_by)
        return outcome, detail

    def delete_directory_group(
        self, group_name: str, *, written_by: str, admin_override: bool = False, actor: Optional[str] = None
    ) -> Tuple[List[Tuple[str, str]], Dict[str, int]]:
        """Delete a group, its memberships and every permission granted to it, through the guard.

        Every membership row is evaluated with :func:`~mlflow_oidc_auth.ownership.evaluate_group_delete`:
        a membership ``written_by`` does not own — ``manual`` included, service accounts included —
        is a conflict. Under ``enforce`` any conflict refuses the delete and nothing is written;
        under ``report`` the delete proceeds and each conflict is recorded.

        Returns:
            ``(memberships, grants)``: the ``(username, group_name)`` memberships removed, and the
            number of grant rows deleted per permission table — for the audit record, since the
            grants cannot be rebuilt from anything else.

        Raises:
            MlflowException: ``RESOURCE_DOES_NOT_EXIST`` for an unknown group;
                :class:`MembershipRefused` when the guard refuses it.
        """
        from mlflow_oidc_auth.db.models import (
            SqlExperimentGroupPermission,
            SqlExperimentGroupRegexPermission,
            SqlGatewayEndpointGroupPermission,
            SqlGatewayEndpointGroupRegexPermission,
            SqlGatewayModelDefinitionGroupPermission,
            SqlGatewayModelDefinitionGroupRegexPermission,
            SqlGatewaySecretGroupPermission,
            SqlGatewaySecretGroupRegexPermission,
            SqlRegisteredModelGroupPermission,
            SqlRegisteredModelGroupRegexPermission,
            SqlScorerGroupPermission,
            SqlScorerGroupRegexPermission,
            SqlWorkspaceGroupPermission,
            SqlWorkspaceGroupRegexPermission,
        )
        from mlflow_oidc_auth.ownership import evaluate_group_delete

        outcome = MembershipOutcome()
        grants: Dict[str, int] = {}
        group_decision = None
        try:
            with self._Session(read_only=False) as session:
                group = get_group(session, group_name)
                # The group's own owner first: a source may not delete a group it does not own.
                group_decision = evaluate_group_write(group.managed_by, written_by, enforcement=config.MANAGED_BY_ENFORCEMENT, admin_override=admin_override)
                if not group_decision.allowed:
                    raise GroupWriteRefused(group.group_name, group_decision, written_by)
                rows = (
                    session.query(SqlUserGroup, SqlUser)
                    .join(SqlUser, SqlUser.id == SqlUserGroup.user_id)
                    .filter(SqlUserGroup.group_id == group.id)
                    .order_by(SqlUserGroup.id)
                    .all()
                )
                for row, user in rows:
                    decision = evaluate_group_delete(row.managed_by, written_by, enforcement=config.MANAGED_BY_ENFORCEMENT, admin_override=admin_override)
                    if decision.conflict:
                        outcome.conflicts.append(MembershipConflict(user.username, group.group_name, decision))
                if outcome.refused:
                    raise MembershipRefused(outcome, written_by)

                group_id = group.id
                for model in (
                    SqlExperimentGroupPermission,
                    SqlExperimentGroupRegexPermission,
                    SqlRegisteredModelGroupPermission,
                    SqlRegisteredModelGroupRegexPermission,
                    SqlScorerGroupPermission,
                    SqlScorerGroupRegexPermission,
                    SqlGatewayEndpointGroupPermission,
                    SqlGatewayEndpointGroupRegexPermission,
                    SqlGatewayModelDefinitionGroupPermission,
                    SqlGatewayModelDefinitionGroupRegexPermission,
                    SqlGatewaySecretGroupPermission,
                    SqlGatewaySecretGroupRegexPermission,
                    SqlWorkspaceGroupPermission,
                    SqlWorkspaceGroupRegexPermission,
                ):
                    count = session.query(model).filter(model.group_id == group_id).delete(synchronize_session=False)
                    if count:
                        grants[model.__tablename__] = int(count)
                session.query(SqlUserGroup).filter(SqlUserGroup.group_id == group_id).delete(synchronize_session=False)
                outcome.removed.extend((user.username, group.group_name) for _, user in rows)
                session.delete(group)
                session.flush()
        except GroupWriteRefused as refused:
            audit_group_conflict(refused.group_name, refused.decision, written_by, actor=actor, operation="group.delete")
            raise
        except MembershipRefused as refused:
            audit_membership_conflicts(MembershipOutcome(conflicts=refused.outcome.refused), written_by, actor=actor, operation="group.delete")
            raise
        if group_decision is not None and group_decision.conflict:
            audit_group_conflict(group_name, group_decision, written_by, actor=actor, operation="group.delete")
        audit_membership_conflicts(outcome, written_by, actor=actor, operation="group.delete")
        return outcome.removed, grants
