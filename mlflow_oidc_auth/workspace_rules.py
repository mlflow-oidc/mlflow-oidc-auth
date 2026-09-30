"""Group → workspace rules: attach a group to a workspace by its name (issue #418).

Onboarding a tenant used to mean creating a group in the identity provider and then attaching it to
its workspace by hand. A rule does the attaching: ``^team-(?P<ws>[a-z0-9-]+)-ds$`` with ``EDIT``
gives the group ``team-acme-ds`` EDIT on the workspace ``acme``. It uses the existing tenant boundary
— a workspace group grant — and never touches individual resources.

What the directory can influence is bounded:

* the pattern is always matched with ``re.fullmatch`` against the *local* group name, which for a
  non-default provider carries its ``<provider-id>:`` prefix, so a partner provider's ``team-acme-ds``
  arrives as ``partner:team-acme-ds`` and does not match a rule written for the deployment's own;
* the permission is capped by ``WORKSPACE_RULES_MAX_PERMISSION`` (default ``EDIT``), checked when
  the rule is saved *and* when it is applied, so lowering the ceiling stops over-ceiling rules;
* a rule writes only rows carrying its own ``rule_id``. A manual grant is never created, changed or
  removed by a rule, and an administrator's edit of a rule's grant makes it manual;
* the workspace must already exist in MLflow — a rule never creates one;
* nothing here runs unless ``MLFLOW_ENABLE_WORKSPACES`` is on.

When rules run:

* on a group's arrival — SCIM create, admin create, and a login that brings new groups — only for
  those groups (:func:`apply_rules_for_groups`);
* on rule create, update or enable — a backfill over every group (:func:`backfill`);
* on rule delete or disable — only that rule's grants are removed (:func:`remove`).

Several rules matching the same group and workspace: the lowest id wins and the others report
``shadowed``. Only enabled ``enforce`` rules compete; a ``report`` rule never shadows anything.
"""

import re
from datetime import datetime, timezone
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode

from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities.workspace_rule import RuleGrantChange, WorkspaceGroupRule
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import get_permission
from mlflow_oidc_auth.repository.workspace_rule import HELD_BY_RULE
from mlflow_oidc_auth.store import store

logger = get_logger()

MODE_REPORT = "report"
MODE_ENFORCE = "enforce"
MODES = (MODE_REPORT, MODE_ENFORCE)
RULE_PERMISSIONS = ("READ", "USE", "EDIT", "MANAGE")
MAX_PATTERN_LENGTH = 256
WORKSPACE_GROUP = "ws"

REASON_MISSING_WORKSPACE = "workspace does not exist"
REASON_ABOVE_CEILING = "permission above WORKSPACE_RULES_MAX_PERMISSION"
REASON_DEFAULT_WORKSPACE = "the default workspace is never granted by a rule"
CEILING_ACTOR = "system:workspace-rules-ceiling"

# The shared workspace every deployment has (app.py seeds it). It holds resources from before
# workspaces and from clients that send no workspace, so a group name — chosen by whoever can
# create groups in the directory — must never be enough to get into it. Grant it by hand.
DEFAULT_WORKSPACE = "default"

Pair = Tuple[str, str]  # (workspace, group_name)


class RuleValidationError(ValueError):
    """A rule field an administrator supplied is not acceptable. The message is safe to return."""


def max_permission() -> str:
    """The configured ceiling, already normalised by the config to one of :data:`RULE_PERMISSIONS`."""
    return config.WORKSPACE_RULES_MAX_PERMISSION


def allowed_permissions() -> List[str]:
    """The permissions a rule may grant under the current ceiling, lowest first."""
    ceiling = get_permission(max_permission()).priority
    return [p for p in RULE_PERMISSIONS if get_permission(p).priority <= ceiling]


def validate_pattern(pattern: str) -> re.Pattern:
    """Compile a rule pattern, or say why it is not acceptable.

    Raises:
        RuleValidationError: longer than 256 characters, not a valid regex, or without ``(?P<ws>...)``.
    """
    if not isinstance(pattern, str) or not pattern:
        raise RuleValidationError("pattern is required")
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise RuleValidationError(f"pattern must be at most {MAX_PATTERN_LENGTH} characters")
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise RuleValidationError(f"pattern is not a valid regular expression: {exc}") from exc
    if WORKSPACE_GROUP not in compiled.groupindex:
        raise RuleValidationError("pattern must contain the named group (?P<ws>...) matching the workspace name")
    return compiled


def validate_permission(permission: str) -> str:
    """Check a rule permission against the ceiling.

    Raises:
        RuleValidationError: not READ/USE/EDIT/MANAGE (``NO_PERMISSIONS`` included), or above
            ``WORKSPACE_RULES_MAX_PERMISSION``.
    """
    if permission not in RULE_PERMISSIONS:
        raise RuleValidationError(f"permission must be one of {', '.join(RULE_PERMISSIONS)}")
    if permission not in allowed_permissions():
        raise RuleValidationError(f"permission {permission} is above WORKSPACE_RULES_MAX_PERMISSION ({max_permission()})")
    return permission


def validate_mode(mode: str) -> str:
    """Check a rule mode.

    Raises:
        RuleValidationError: neither ``report`` nor ``enforce``.
    """
    if mode not in MODES:
        raise RuleValidationError(f"mode must be one of {', '.join(MODES)}")
    return mode


def is_enforcing(rule: WorkspaceGroupRule) -> bool:
    """Whether ``rule`` writes grants: enabled and in ``enforce`` mode."""
    return rule.enabled and rule.mode == MODE_ENFORCE


def _within_ceiling(rule: WorkspaceGroupRule) -> bool:
    return rule.permission in allowed_permissions()


def _match(rule: WorkspaceGroupRule, group_name: str) -> Optional[str]:
    """The workspace ``group_name`` maps to under ``rule``, or None when it does not match.

    A pattern that no longer compiles (it was validated when saved, so only a Python upgrade could
    cause this) matches nothing.
    """
    try:
        found = re.fullmatch(rule.pattern, group_name)
    except re.error:
        return None
    if found is None:
        return None
    return found.groupdict().get(WORKSPACE_GROUP) or None


class WorkspaceStoreUnavailable(RuntimeError):
    """MLflow's workspace store could not answer. Nothing is written while it cannot."""


class _WorkspaceExists:
    """Memoised check that a workspace exists in MLflow's workspace store.

    A workspace the store reports missing is skipped. A store that cannot answer at all raises
    :class:`WorkspaceStoreUnavailable` instead: treating an outage as "every workspace is missing"
    would make a backfill remove every grant the rule holds.
    """

    def __init__(self):
        self._known: Dict[str, bool] = {}
        self._store = None

    def __call__(self, name: str) -> bool:
        if name not in self._known:
            self._known[name] = self._check(name)
        return self._known[name]

    def _check(self, name: str) -> bool:
        if self._store is None:
            try:
                from mlflow.server import handlers

                self._store = handlers._get_workspace_store()
            except Exception as exc:
                raise WorkspaceStoreUnavailable(f"MLflow's workspace store cannot be reached: {type(exc).__name__}") from exc
        try:
            self._store.get_workspace(name)
            return True
        except MlflowException as exc:
            if exc.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
                return False
            raise WorkspaceStoreUnavailable(f"MLflow's workspace store failed: {exc.error_code}") from exc
        except Exception as exc:
            raise WorkspaceStoreUnavailable(f"MLflow's workspace store failed: {type(exc).__name__}") from exc


@dataclass
class Plan:
    """What one rule wants for a set of groups, before the database says what is already there.

    Attributes:
        rule: The rule.
        desired: ``(workspace, group) → permission`` for the groups the rule wins.
        retain: Pairs the rule matches but a lower-id rule wins: its existing grant there, if any,
            is kept rather than removed.
        items: Lines decided without the database — ``shadowed`` and ``skip`` (missing workspace,
            above ceiling).
    """

    rule: WorkspaceGroupRule
    desired: Dict[Pair, str] = field(default_factory=dict)
    retain: Set[Pair] = field(default_factory=set)
    items: List[RuleGrantChange] = field(default_factory=list)


def evaluate(
    rule: WorkspaceGroupRule,
    group_names: Iterable[str],
    *,
    competitors: Optional[Sequence[WorkspaceGroupRule]] = None,
    workspace_exists: Optional[Callable[[str], bool]] = None,
) -> Plan:
    """Decide what ``rule`` wants for ``group_names``, as if it were enforcing.

    Parameters:
        rule: The rule to evaluate. Its ``enabled`` and ``mode`` are not consulted here — a
            preview of a disabled or report-mode rule shows what enforcing it would do.
        group_names: Local group names to consider.
        competitors: The enabled enforce rules. A lower-id one matching the same group and
            workspace shadows ``rule``. Loaded from the store when omitted.
        workspace_exists: Workspace existence check; MLflow's workspace store when omitted.

    Returns:
        The plan. Nothing is written.
    """
    if competitors is None:
        competitors = [r for r in store.list_workspace_group_rules(enabled_only=True) if r.mode == MODE_ENFORCE]
    exists = workspace_exists or _WorkspaceExists()
    earlier = [r for r in competitors if r.id < rule.id and _within_ceiling(r)]
    plan = Plan(rule=rule)
    within = _within_ceiling(rule)

    for group in sorted(set(group_names)):
        workspace = _match(rule, group)
        if workspace is None:
            continue
        winner = next((r for r in earlier if _match(r, group) == workspace), None)
        if winner is not None:
            plan.retain.add((workspace, group))
            plan.items.append(RuleGrantChange("shadowed", group, workspace, rule.permission, reason=f"rule {winner.id} ({winner.name}) wins"))
        elif not within:
            plan.items.append(RuleGrantChange("skip", group, workspace, rule.permission, reason=REASON_ABOVE_CEILING))
        elif workspace == DEFAULT_WORKSPACE:
            plan.items.append(RuleGrantChange("skip", group, workspace, rule.permission, reason=REASON_DEFAULT_WORKSPACE))
        elif not exists(workspace):
            plan.items.append(RuleGrantChange("skip", group, workspace, rule.permission, reason=REASON_MISSING_WORKSPACE))
        else:
            plan.desired[(workspace, group)] = rule.permission
    return plan


def _execute(plan: Plan, *, scope: Optional[Iterable[str]], dry_run: bool) -> List[RuleGrantChange]:
    """Run a plan against the store. Returns every line, sorted by workspace then group."""
    changes = store.reconcile_workspace_group_rule(
        plan.rule.id, plan.desired, scope=None if scope is None else set(scope), retain=plan.retain, dry_run=dry_run, expected=plan.rule
    )
    return _sorted([*changes, *(replace(c, rule_id=plan.rule.id) for c in plan.items)])


def _audit(rule: WorkspaceGroupRule, changes: Iterable[RuleGrantChange], actor: str) -> None:
    """One audit event per grant written or removed, and per line an enforcing rule skipped.

    Only ``rule``'s own lines: another rule's (a hand-over) are audited where they were written.
    """
    for change in changes:
        if change.rule_id is not None and change.rule_id != rule.id:
            continue
        detail = {"rule_id": rule.id, "workspace": change.workspace, "group": change.group, "permission": change.permission}
        if change.applied and change.action in ("grant", "update"):
            if change.previous is not None:
                detail["previous"] = change.previous
            emit_audit_event("permission.provisioned", actor, resource_type="group_workspace_permission", resource_id=change.workspace, detail=detail)
        elif change.applied and change.action == "remove":
            emit_audit_event("permission.deprovisioned", actor, resource_type="group_workspace_permission", resource_id=change.workspace, detail=detail)
        elif change.action in ("skip", "shadowed"):
            emit_audit_event(
                "workspace_rule.skipped",
                actor,
                resource_type="workspace_rule",
                resource_id=str(rule.id),
                detail={**detail, "reason": change.reason or change.action},
            )


def _enforcing_rules() -> List[WorkspaceGroupRule]:
    """The rules that compete for grants: enabled and enforcing, lowest id first."""
    return [r for r in store.list_workspace_group_rules(enabled_only=True) if r.mode == MODE_ENFORCE]


def _sorted(changes: Iterable[RuleGrantChange]) -> List[RuleGrantChange]:
    return sorted(changes, key=lambda c: (c.workspace, c.group, c.action))


def preview(rule: WorkspaceGroupRule) -> List[RuleGrantChange]:
    """What enforcing ``rule`` now would grant, update, keep, skip or remove, over every group. Writes nothing.

    Raises:
        WorkspaceStoreUnavailable: MLflow's workspace store cannot answer.
    """
    competitors = _enforcing_rules()
    changes = _execute(evaluate(rule, store.list_rule_eligible_group_names(), competitors=competitors), scope=None, dry_run=True)
    return _preview_takeovers(rule, changes, competitors)


def preview_unsaved(pattern: str, permission: str, *, rule_id: Optional[int] = None) -> List[RuleGrantChange]:
    """What a rule with ``pattern`` and ``permission`` would do if saved now and enforced. Writes nothing.

    Parameters:
        pattern: The pattern to preview.
        permission: The permission to preview.
        rule_id: An existing rule being edited. The preview keeps its id — its precedence, and the
            grants it already holds, which show as ``keep`` / ``update`` / ``remove``. Without it,
            the draft gets the id a new rule would — one past every existing rule — so any existing
            enforcing rule matching the same group and workspace shadows it, as it would once saved.

    Raises:
        MlflowException: ``RESOURCE_DOES_NOT_EXIST`` for an unknown ``rule_id``.
        WorkspaceStoreUnavailable: MLflow's workspace store cannot answer.
    """
    rules = store.list_workspace_group_rules()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if rule_id is not None:
        base = store.get_workspace_group_rule(rule_id)
        draft = replace(base, pattern=pattern, permission=permission, mode=MODE_ENFORCE, enabled=True)
    else:
        draft = WorkspaceGroupRule(
            id=max((r.id for r in rules), default=0) + 1,
            name="(unsaved)",
            pattern=pattern,
            permission=permission,
            mode=MODE_ENFORCE,
            enabled=True,
            created_by=None,
            created_at=now,
            updated_at=now,
        )
    competitors = [r for r in rules if is_enforcing(r) and r.id != draft.id]
    changes = _execute(evaluate(draft, store.list_rule_eligible_group_names(), competitors=competitors), scope=None, dry_run=True)
    return _preview_takeovers(draft, changes, competitors)


def _is_held_by_other(change: RuleGrantChange) -> bool:
    return change.action == "skip" and bool(change.reason) and change.reason.startswith(HELD_BY_RULE)


def _preview_takeovers(rule: WorkspaceGroupRule, changes: List[RuleGrantChange], competitors: Sequence[WorkspaceGroupRule]) -> List[RuleGrantChange]:
    """In a preview, show a pair a higher-id enforcing rule holds as what enforcing would do: take it over."""
    enforcing = {r.id for r in competitors}
    previewed = []
    for change in changes:
        if _is_held_by_other(change):
            holder_id = int(change.reason[len(HELD_BY_RULE) :])
            if holder_id > rule.id and holder_id in enforcing:
                change = replace(change, action="grant", reason=f"takes over from rule {holder_id}")
        previewed.append(change)
    return previewed


def _take_over_held(
    rule: WorkspaceGroupRule,
    changes: List[RuleGrantChange],
    competitors: Sequence[WorkspaceGroupRule],
    exists: Callable[[str], bool],
    actor: str,
) -> List[RuleGrantChange]:
    """Let ``rule`` win the pairs a higher-id rule still holds — lowest id wins (decision 4).

    Such a pair appears when the winner was disabled or in ``report`` when the loser granted it. No
    rule ever writes another's row: the loser releases its own grants where ``rule`` now shadows it,
    then ``rule`` grants its own. Returns ``changes`` with the ``held by`` lines replaced by the result.
    """
    held: Dict[int, Set[str]] = {}
    for change in changes:
        if _is_held_by_other(change):
            holder_id = int(change.reason[len(HELD_BY_RULE) :])
            if holder_id > rule.id:
                held.setdefault(holder_id, set()).add(change.group)
    by_id = {r.id: r for r in competitors}
    released: Set[str] = set()
    handed_over: List[RuleGrantChange] = []
    for holder_id, groups in held.items():
        holder = by_id.get(holder_id)
        if holder is None:
            continue
        plan = evaluate(holder, groups, competitors=competitors, workspace_exists=exists)
        plan.retain = set()
        holder_writes = [c for c in _execute(plan, scope=groups, dry_run=False) if c.applied]
        _audit(holder, holder_writes, actor)
        handed_over.extend(holder_writes)
        released |= groups
    if not released:
        return changes
    retried = _execute(evaluate(rule, released, competitors=competitors, workspace_exists=exists), scope=released, dry_run=False)
    # Only the ``held by`` lines are superseded: anything else ``rule`` already wrote for those groups
    # (a removal elsewhere, say) stays in the result, to be reported and audited.
    kept = [c for c in changes if not (c.group in released and _is_held_by_other(c))]
    # The holder's lines carry its own rule_id; the caller audits only ``rule``'s, so they are not audited twice.
    return _sorted([*kept, *retried, *handed_over])


def backfill(rule: WorkspaceGroupRule, *, actor: str) -> List[RuleGrantChange]:
    """Reconcile ``rule`` against every existing group — on rule create, update or enable.

    An enforcing rule writes, in one transaction, and removes the grants it holds that it no longer
    wants (a narrowed pattern, say); where a higher-id rule holds a pair it wins, that rule releases
    it first. A report-mode or disabled rule writes nothing: the result is its preview, every line
    ``applied=False``.

    Raises:
        WorkspaceStoreUnavailable: MLflow's workspace store cannot answer; nothing was written.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return []
    if not is_enforcing(rule):
        return preview(rule)
    competitors = _enforcing_rules()
    exists = _WorkspaceExists()
    plan = evaluate(rule, store.list_rule_eligible_group_names(), competitors=competitors, workspace_exists=exists)
    changes = _execute(plan, scope=None, dry_run=False)
    changes = _take_over_held(rule, changes, competitors, exists, actor)
    _audit(rule, changes, actor)
    return changes


def remove(rule: WorkspaceGroupRule, *, actor: str) -> List[RuleGrantChange]:
    """Remove every grant ``rule`` holds and nothing else — on disable or a switch to ``report``.

    The other enforcing rules are then applied to the groups that lost a grant, so a rule ``rule``
    shadowed takes over. Returns the removals followed by what they caused.
    """
    removed = store.clear_workspace_group_rule_grants(rule.id)
    _audit(rule, removed, actor)
    return removed + reapply_after_removal(removed, actor=actor)


def audit_removed(rule: WorkspaceGroupRule, removed: Iterable[RuleGrantChange], *, actor: str) -> None:
    """Audit grants a rule write already removed (its delete, or an update that stopped enforcing)."""
    _audit(rule, removed, actor)


def reapply_after_removal(removed: Iterable[RuleGrantChange], *, actor: str) -> List[RuleGrantChange]:
    """Apply the enforcing rules to the groups whose rule grant was just removed. Never raises.

    A rule the removed one shadowed wins those pairs now; without this it would stay without a
    grant until something happened to touch it.
    """
    groups = {c.group for c in removed if c.applied and c.action == "remove"}
    if not groups:
        return []
    return [c for c in apply_rules_for_groups(groups, source=actor) if c.applied]


def apply_rules_for_groups(group_names: Iterable[str], *, source: str) -> List[RuleGrantChange]:
    """Apply every enforcing rule to the given groups. Never raises.

    Called after the group writes at the three places groups arrive — SCIM create, the admin
    create-group endpoint, and a login that created groups — and after a rule's grants are removed.
    A failure is logged and audited and swallowed: it must never fail the login or the SCIM request
    that brought the group. Each rule runs in its own transaction, so one failing rule does not stop
    the others. A workspace store that cannot answer fails the rule — nothing is written.

    Parameters:
        group_names: Local group names.
        source: Who brought them — ``scim``, ``oidc:<id>``, ``saml:<id>`` or the admin's username.
            Recorded as the actor of the audit events.

    Returns:
        Every line from every enforcing rule; empty when workspaces are off or nothing matched.
    """
    names = sorted({g for g in group_names if g})
    if not config.MLFLOW_ENABLE_WORKSPACES or not names:
        return []
    try:
        rules = _enforcing_rules()
        if rules:
            names = store.list_rule_eligible_group_names(names)
    except Exception as exc:
        _report_failure(None, names, source, exc)
        return []
    if not rules or not names:
        return []

    exists = _WorkspaceExists()
    changes: List[RuleGrantChange] = []
    for rule in rules:
        try:
            plan = evaluate(rule, names, competitors=rules, workspace_exists=exists)
            if not plan.desired and not plan.items:
                continue
            rule_changes = _execute(plan, scope=names, dry_run=False)
            rule_changes = _take_over_held(rule, rule_changes, rules, exists, source)
            _audit(rule, rule_changes, source)
            changes.extend(rule_changes)
        except Exception as exc:
            _report_failure(rule, names, source, exc)
    return changes


def enforce_ceiling() -> List[RuleGrantChange]:
    """Remove every grant held by a rule above ``WORKSPACE_RULES_MAX_PERMISSION``. Never raises.

    Run at startup with workspaces enabled. The ceiling is checked whenever a rule is applied, but a
    rule that already granted MANAGE keeps those grants until something applies it again — so after
    an operator lowers the ceiling and restarts, this is what makes the lower ceiling true. The rule
    itself stays and reports ``skip`` until its permission is lowered. Each rule is handled on its
    own, so one failure does not stop the rest.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return []
    try:
        rules = store.list_workspace_group_rules()
    except Exception as exc:
        logger.error("Could not read workspace group rules to apply WORKSPACE_RULES_MAX_PERMISSION: %s", type(exc).__name__)
        return []
    removed: List[RuleGrantChange] = []
    for rule in rules:
        if _within_ceiling(rule):
            continue
        try:
            rule_removed = store.clear_workspace_group_rule_grants(rule.id)
        except Exception as exc:
            logger.error("Could not remove the grants of workspace group rule %s above the permission ceiling: %s", rule.id, type(exc).__name__)
            continue
        if rule_removed:
            # The configured ceiling is deliberately not logged: configuration can come from a secret store.
            logger.warning("Removed %d grant(s) of workspace group rule %s: its permission is above WORKSPACE_RULES_MAX_PERMISSION", len(rule_removed), rule.id)
            _audit(rule, rule_removed, CEILING_ACTOR)
            removed.extend(rule_removed)
    return removed + reapply_after_removal(removed, actor=CEILING_ACTOR)


def _report_failure(rule: Optional[WorkspaceGroupRule], group_names: List[str], source: str, exc: Exception) -> None:
    logger.error("Workspace group rule %s failed for %d arrived group(s): %s", rule.id if rule else "lookup", len(group_names), exc)
    emit_audit_event(
        "workspace_rule.failed",
        source,
        resource_type="workspace_rule",
        resource_id=str(rule.id) if rule else None,
        detail={"groups": group_names, "error": type(exc).__name__},
        status="denied",
    )
