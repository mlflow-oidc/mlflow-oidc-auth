"""Storage for group → workspace rules and the grants they own (issue #418).

The rule engine (:mod:`mlflow_oidc_auth.workspace_rules`) decides which group should hold which
workspace permission; :meth:`WorkspaceGroupRuleRepository.reconcile` makes the table agree, in one
transaction, touching only rows that carry the rule's own ``rule_id``. A manual grant
(``rule_id IS NULL``) or another rule's grant for the same group and workspace is reported and left
alone — including when it appears between the engine's decision and the write, which a SAVEPOINT
per insert turns into a ``skip`` rather than a failed transaction.
"""

from dataclasses import replace
from datetime import datetime, timezone
from typing import Collection, Dict, Iterable, List, Optional, Set, Tuple

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from mlflow_oidc_auth.db.models.user import SqlGroup
from mlflow_oidc_auth.db.models.workspace import SqlWorkspaceGroupPermission
from mlflow_oidc_auth.db.models.workspace_rule import SqlWorkspaceGroupRule
from mlflow_oidc_auth.entities.workspace_rule import RuleGrantChange, WorkspaceGroupRule
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

# Keeps every IN (...) list well under SQLite's bound-parameter limit on large directories.
_CHUNK = 500

Pair = Tuple[str, str]  # (workspace, group_name)

MANUAL_GRANT = "manual grant"
# Reason prefix for a pair another rule holds; the engine parses the holder's id after it.
HELD_BY_RULE = "held by rule "


# Login sources that name a provider; see mlflow_oidc_auth.ownership.LOGIN_SOURCE_PREFIXES.
_PROVIDER_SOURCES = ("oidc:", "saml:")
_DEFAULT_PROVIDER_ID = "default"


def _namespaced_for_its_source(group_name: str, managed_by: Optional[str]) -> bool:
    """False for a group a non-default provider created under a name without its ``<id>:`` prefix."""
    if not managed_by or not managed_by.startswith(_PROVIDER_SOURCES):
        return True
    provider_id = managed_by.split(":", 1)[1]
    return provider_id == _DEFAULT_PROVIDER_ID or group_name.startswith(f"{provider_id}:")


def _semantics(rule: WorkspaceGroupRule) -> Tuple:
    """The fields that decide what a rule grants."""
    return (rule.pattern, rule.permission, rule.mode, rule.enabled)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _chunks(values: List, size: int = _CHUNK) -> Iterable[List]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


class WorkspaceGroupRuleRepository:
    """CRUD for rules, and the one write path for the grants they own."""

    def __init__(self, session_maker):
        self.ManagedSessionMaker = session_maker

    @staticmethod
    def _get(session, rule_id: int) -> SqlWorkspaceGroupRule:
        rule = session.get(SqlWorkspaceGroupRule, rule_id)
        if rule is None:
            raise MlflowException(f"Workspace group rule {rule_id} not found", RESOURCE_DOES_NOT_EXIST)
        return rule

    def create(self, *, name: str, pattern: str, permission: str, mode: str, enabled: bool, created_by: Optional[str]) -> WorkspaceGroupRule:
        """Create a rule.

        Raises:
            MlflowException: ``RESOURCE_ALREADY_EXISTS`` when the name is taken.
        """
        now = _now()
        with self.ManagedSessionMaker(read_only=False) as session:
            rule = SqlWorkspaceGroupRule(
                name=name, pattern=pattern, permission=permission, mode=mode, enabled=enabled, created_by=created_by, created_at=now, updated_at=now
            )
            try:
                with session.begin_nested():
                    session.add(rule)
            except IntegrityError as exc:
                raise MlflowException(f"Workspace group rule named {name!r} already exists", RESOURCE_ALREADY_EXISTS) from exc
            return rule.to_mlflow_entity()

    def get(self, rule_id: int) -> WorkspaceGroupRule:
        """One rule.

        Raises:
            MlflowException: ``RESOURCE_DOES_NOT_EXIST`` for an unknown id.
        """
        with self.ManagedSessionMaker() as session:
            return self._get(session, rule_id).to_mlflow_entity()

    def list(self, *, enabled_only: bool = False) -> List[WorkspaceGroupRule]:
        """Every rule, lowest id (highest precedence) first."""
        with self.ManagedSessionMaker() as session:
            query = session.query(SqlWorkspaceGroupRule)
            if enabled_only:
                query = query.filter(SqlWorkspaceGroupRule.enabled.is_(True))
            return [r.to_mlflow_entity() for r in query.order_by(SqlWorkspaceGroupRule.id).all()]

    def update(self, rule_id: int, fields: Dict[str, object], *, clear_grants: bool = False) -> Tuple[WorkspaceGroupRule, List[RuleGrantChange]]:
        """Change a rule, and with ``clear_grants`` delete every grant it owns, in one transaction.

        Parameters:
            rule_id: The rule.
            fields: Columns to set; ``name``, ``pattern``, ``permission``, ``mode``, ``enabled``.
            clear_grants: Delete the rule's grants — for a rule that stops enforcing.

        Returns:
            The updated rule and one applied ``remove`` per deleted grant.

        Raises:
            MlflowException: ``RESOURCE_DOES_NOT_EXIST`` for an unknown id,
                ``RESOURCE_ALREADY_EXISTS`` when the new name is taken.
        """
        allowed = {"name", "pattern", "permission", "mode", "enabled"}
        with self.ManagedSessionMaker(read_only=False) as session:
            rule = self._get(session, rule_id)
            for key, value in fields.items():
                if key not in allowed:
                    raise ValueError(f"unknown rule field {key!r}")
                setattr(rule, key, value)
            rule.updated_at = _now()
            try:
                with session.begin_nested():
                    session.flush()
            except IntegrityError as exc:
                raise MlflowException(f"Workspace group rule named {fields.get('name')!r} already exists", RESOURCE_ALREADY_EXISTS) from exc
            removed = self._delete_grants(session, rule_id) if clear_grants else []
            return rule.to_mlflow_entity(), removed

    def delete(self, rule_id: int) -> List[RuleGrantChange]:
        """Delete a rule and every grant it owns, in one transaction.

        Returns:
            One applied ``remove`` per deleted grant.

        Raises:
            MlflowException: ``RESOURCE_DOES_NOT_EXIST`` for an unknown id.
        """
        with self.ManagedSessionMaker(read_only=False) as session:
            rule = self._get(session, rule_id)
            removed = self._delete_grants(session, rule_id)
            session.delete(rule)
            session.flush()
            return removed

    def clear_grants(self, rule_id: int) -> List[RuleGrantChange]:
        """Delete every grant a rule holds, leaving the rule itself untouched.

        Returns:
            One applied ``remove`` per deleted grant.
        """
        with self.ManagedSessionMaker(read_only=False) as session:
            return self._delete_grants(session, rule_id)

    @staticmethod
    def _delete_grants(session, rule_id: int) -> List[RuleGrantChange]:
        rows = (
            session.query(SqlWorkspaceGroupPermission, SqlGroup.group_name)
            .join(SqlGroup, SqlGroup.id == SqlWorkspaceGroupPermission.group_id)
            .filter(SqlWorkspaceGroupPermission.rule_id == rule_id)
            .order_by(SqlWorkspaceGroupPermission.workspace, SqlGroup.group_name)
            .all()
        )
        removed = [RuleGrantChange("remove", group_name, row.workspace, row.permission, applied=True, rule_id=rule_id) for row, group_name in rows]
        session.query(SqlWorkspaceGroupPermission).filter(SqlWorkspaceGroupPermission.rule_id == rule_id).delete(synchronize_session=False)
        session.flush()
        return removed

    def eligible_group_names(self, names: Optional[Collection[str]] = None) -> List[str]:
        """Group names a rule may match: every group, or those of ``names`` that exist, minus any
        name a non-default provider chose outside its own namespace.

        A group records the source that created it (``managed_by``). One created by a provider
        other than ``default`` (``oidc:<id>`` / ``saml:<id>``) is eligible only under its
        ``<id>:``-prefixed name: a rule must never trust a group name such a provider picked in
        the deployment's own namespace, however the group came to exist.

        Parameters:
            names: Limit to these names; None means every group.

        Returns:
            Eligible names, sorted.
        """
        with self.ManagedSessionMaker() as session:
            query = session.query(SqlGroup.group_name, SqlGroup.managed_by)
            if names is None:
                rows = query.all()
            else:
                rows = []
                for chunk in _chunks(sorted(set(names))):
                    rows.extend(query.filter(SqlGroup.group_name.in_(chunk)).all())
        return sorted(name for name, managed_by in rows if _namespaced_for_its_source(name, managed_by))

    def reconcile(
        self,
        rule_id: int,
        desired: Dict[Pair, str],
        *,
        scope: Optional[Collection[str]] = None,
        retain: Collection[Pair] = (),
        dry_run: bool = False,
        expected: Optional[WorkspaceGroupRule] = None,
    ) -> List[RuleGrantChange]:
        """Make the rule's grants match ``desired``, in one transaction.

        For each wanted ``(workspace, group) → permission``: no row → ``grant``; a row this rule
        owns → ``keep`` or ``update``; a manual row → ``skip`` (manual grant); another rule's row →
        ``skip`` (held by that rule). Every row this rule owns that is not wanted and not in
        ``retain`` → ``remove``.

        Parameters:
            rule_id: The rule whose grants these are.
            desired: What the rule wants, keyed by ``(workspace, group_name)``.
            scope: Group names to reconcile. None reconciles every grant the rule owns — a
                backfill; a set limits removal to those groups — groups that just arrived.
            retain: Pairs the rule owns but no longer wins (a lower-id rule matches too). Kept
                rather than removed, so the grant does not vanish until the winner writes its own.
            dry_run: Compute the changes, write nothing.
            expected: The rule as ``desired`` was computed from. For a write, the rule row is
                locked and compared first: if it was deleted, disabled or otherwise changed since —
                a concurrent PATCH or DELETE — nothing is written and the result is empty, so a
                stale plan cannot re-create a grant a disable just removed. The PATCH that changed
                it runs its own reconcile.

        Returns:
            The changes, sorted by workspace then group. ``applied`` is True on the ones written.
        """
        changes: List[RuleGrantChange] = []
        retain_set: Set[Pair] = set(retain)
        scope_names = None if scope is None else set(scope)
        wanted_groups = sorted({group for _, group in desired} | (scope_names or set()))

        with self.ManagedSessionMaker(read_only=dry_run) as session:
            if not dry_run and expected is not None:
                current = session.query(SqlWorkspaceGroupRule).filter(SqlWorkspaceGroupRule.id == rule_id).with_for_update().one_or_none()
                if current is None or _semantics(current.to_mlflow_entity()) != _semantics(expected):
                    logger.info("Workspace group rule %s changed while its grants were being computed; not writing a stale plan", rule_id)
                    return []
            ids: Dict[str, int] = {}
            for chunk in _chunks(wanted_groups):
                ids.update(dict(session.query(SqlGroup.group_name, SqlGroup.id).filter(SqlGroup.group_name.in_(chunk)).all()))
            names = {group_id: name for name, group_id in ids.items()}

            existing: Dict[Pair, SqlWorkspaceGroupPermission] = {}
            owned_filter = SqlWorkspaceGroupPermission.rule_id == rule_id
            id_list = sorted(ids.values())
            chunks = list(_chunks(id_list)) or [[]]
            for chunk in chunks:
                query = (
                    session.query(SqlWorkspaceGroupPermission, SqlGroup.group_name)
                    .join(SqlGroup, SqlGroup.id == SqlWorkspaceGroupPermission.group_id)
                    .filter(
                        or_(owned_filter, SqlWorkspaceGroupPermission.group_id.in_(chunk))
                        if scope_names is None
                        else SqlWorkspaceGroupPermission.group_id.in_(chunk)
                    )
                )
                for row, group_name in query.all():
                    names.setdefault(row.group_id, group_name)
                    existing[(row.workspace, group_name)] = row

            for (workspace, group), permission in desired.items():
                row = existing.get((workspace, group))
                if group not in ids:
                    # Deleted between the engine's read and this one. Nothing to grant it on.
                    changes.append(RuleGrantChange("skip", group, workspace, permission, reason="group no longer exists"))
                elif row is None:
                    applied = False
                    if not dry_run:
                        try:
                            with session.begin_nested():
                                session.add(SqlWorkspaceGroupPermission(workspace=workspace, group_id=ids[group], permission=permission, rule_id=rule_id))
                            applied = True
                        except IntegrityError:
                            # Someone else granted it since the read. Theirs stands.
                            changes.append(RuleGrantChange("skip", group, workspace, permission, reason="granted concurrently"))
                            continue
                    changes.append(RuleGrantChange("grant", group, workspace, permission, applied=applied))
                elif row.rule_id is None:
                    changes.append(RuleGrantChange("skip", group, workspace, permission, reason=MANUAL_GRANT))
                elif row.rule_id != rule_id:
                    changes.append(RuleGrantChange("skip", group, workspace, permission, reason=f"{HELD_BY_RULE}{row.rule_id}"))
                elif row.permission == permission:
                    changes.append(RuleGrantChange("keep", group, workspace, permission))
                else:
                    previous = row.permission
                    if not dry_run:
                        row.permission = permission
                    changes.append(RuleGrantChange("update", group, workspace, permission, previous=previous, applied=not dry_run))

            for (workspace, group), row in existing.items():
                if row.rule_id != rule_id or (workspace, group) in desired or (workspace, group) in retain_set:
                    continue
                if scope_names is not None and group not in scope_names:
                    continue
                if not dry_run:
                    session.delete(row)
                changes.append(RuleGrantChange("remove", group, workspace, row.permission, applied=not dry_run))

            if not dry_run:
                session.flush()

        return sorted((replace(c, rule_id=rule_id) for c in changes), key=lambda c: (c.workspace, c.group))
