"""Resources a departing user leaves without a manager (issues #324, #375).

When a directory deactivates or deletes someone, anything *only they* could manage becomes
unmanageable by anyone short of an administrator. That is not a reason to block the
deprovisioning — access removal must never wait on housekeeping — but it is something an
operator needs to hear about. This module finds those resources and reports them as
``resource.orphaned`` audit events, and, when ``ORPHAN_FALLBACK_PRINCIPAL`` is configured, hands
them to that principal as part of the hard delete that cascades the departing user's grants away.

Not to be confused with :mod:`mlflow_oidc_auth.ownership`, which is the ``managed_by`` write guard
on user rows.

**Which resources are the departing user's.** Those they hold ``MANAGE`` on *directly*, or
through a *group* holding ``MANAGE`` on it (``via`` is ``"direct"`` or ``"group:<name>"`` on the
event). A user whose only path to a resource was a regex grant is not enumerated: a pattern
matches resources in the tracking store, including ones not created yet, and walking the store on
every deprovisioning is out of proportion to a report.

**What counts as another holder.** Any of:

* another *active* user with a direct ``MANAGE`` grant;
* a group holding ``MANAGE`` that has an active member other than the departing user — so a group
  in which the departing user was the last active member does *not* keep the resource managed;
* another active user whose own regex grants resolve to ``MANAGE`` for the resource;
* another active user whose groups' regex grants resolve to ``MANAGE`` for the resource.

Regex grants are resolved exactly as the request-time resolvers resolve them: the principal's
patterns in priority order, first match wins (for workspaces, the most permissive of the
best-priority matches), against the same subject — the experiment's *name*, the model or prompt
name, the scorer name, the gateway key, the workspace name. A regex holder's permission is found by
replaying ``PERMISSION_SOURCE_ORDER``, so a direct or group grant the resolver reaches first (say,
``READ``) shadows their patterns. Where the subject lives in MLflow
rather than in this plugin's tables (an experiment's name, whether a registered model is a prompt),
at most :data:`_EXTERNAL_LOOKUP_LIMIT` lookups are made per resource type, and a resource that
cannot be resolved is reported, never silently assumed held.

Admins are not counted as holders — an admin can always recover a resource, which is precisely why
an orphan is a report and never a refusal.
"""

import re
from collections import defaultdict
from typing import Any, Dict, FrozenSet, Iterable, List, NamedTuple, Optional, Set, Tuple

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

MANAGE = "MANAGE"

#: ``resource_type`` values used in ``resource.orphaned`` events.
EXPERIMENT = "experiment"
REGISTERED_MODEL = "registered_model"  # prompts are registered models and share these grants
SCORER = "scorer"
GATEWAY_ENDPOINT = "gateway_endpoint"
GATEWAY_MODEL_DEFINITION = "gateway_model_definition"
WORKSPACE = "workspace"

#: Upper bound on MLflow store lookups (experiment names, prompt flags) per resource type and run.
_EXTERNAL_LOOKUP_LIMIT = 200

VIA_DIRECT = "direct"
VIA_GROUP_PREFIX = "group:"


class _Spec(NamedTuple):
    resource_type: str
    user_model: Any
    group_model: Any
    key_columns: Tuple[str, ...]
    user_regex_model: Any
    group_regex_model: Any
    #: Index into the key tuple of the value a regex is matched against. ``None`` for experiments,
    #: whose patterns match the experiment *name*, which only the tracking store knows.
    regex_key_index: Optional[int]


def _specs() -> List[_Spec]:
    """One entry per resource kind: its grant tables, key columns and regex subject."""
    from mlflow_oidc_auth.db.models import (
        SqlExperimentGroupPermission,
        SqlExperimentGroupRegexPermission,
        SqlExperimentPermission,
        SqlExperimentRegexPermission,
        SqlGatewayEndpointGroupPermission,
        SqlGatewayEndpointGroupRegexPermission,
        SqlGatewayEndpointPermission,
        SqlGatewayEndpointRegexPermission,
        SqlGatewayModelDefinitionGroupPermission,
        SqlGatewayModelDefinitionGroupRegexPermission,
        SqlGatewayModelDefinitionPermission,
        SqlGatewayModelDefinitionRegexPermission,
        SqlGatewaySecretGroupPermission,
        SqlGatewaySecretGroupRegexPermission,
        SqlGatewaySecretPermission,
        SqlGatewaySecretRegexPermission,
        SqlRegisteredModelGroupPermission,
        SqlRegisteredModelGroupRegexPermission,
        SqlRegisteredModelPermission,
        SqlRegisteredModelRegexPermission,
        SqlScorerGroupPermission,
        SqlScorerGroupRegexPermission,
        SqlScorerPermission,
        SqlScorerRegexPermission,
        SqlWorkspaceGroupPermission,
        SqlWorkspaceGroupRegexPermission,
        SqlWorkspacePermission,
        SqlWorkspaceRegexPermission,
    )

    return [
        _Spec(
            EXPERIMENT,
            SqlExperimentPermission,
            SqlExperimentGroupPermission,
            ("experiment_id",),
            SqlExperimentRegexPermission,
            SqlExperimentGroupRegexPermission,
            None,
        ),
        _Spec(
            REGISTERED_MODEL,
            SqlRegisteredModelPermission,
            SqlRegisteredModelGroupPermission,
            ("name",),
            SqlRegisteredModelRegexPermission,
            SqlRegisteredModelGroupRegexPermission,
            0,
        ),
        # A scorer's patterns match the scorer name, as in ``_build_scorer_sources``.
        _Spec(
            SCORER, SqlScorerPermission, SqlScorerGroupPermission, ("experiment_id", "scorer_name"), SqlScorerRegexPermission, SqlScorerGroupRegexPermission, 1
        ),
        # Gateway resolvers pass one value to both the grant lookup and the pattern match: the key.
        _Spec(
            GATEWAY_ENDPOINT,
            SqlGatewayEndpointPermission,
            SqlGatewayEndpointGroupPermission,
            ("endpoint_id",),
            SqlGatewayEndpointRegexPermission,
            SqlGatewayEndpointGroupRegexPermission,
            0,
        ),
        _Spec(
            GATEWAY_MODEL_DEFINITION,
            SqlGatewayModelDefinitionPermission,
            SqlGatewayModelDefinitionGroupPermission,
            ("model_definition_id",),
            SqlGatewayModelDefinitionRegexPermission,
            SqlGatewayModelDefinitionGroupRegexPermission,
            0,
        ),
        # The resource-type label is written inline: a module constant carrying "secret" in its
        # name makes static analysis treat the label (not a secret) as sensitive wherever it is logged.
        _Spec(
            "gateway_secret",
            SqlGatewaySecretPermission,
            SqlGatewaySecretGroupPermission,
            ("secret_id",),
            SqlGatewaySecretRegexPermission,
            SqlGatewaySecretGroupRegexPermission,
            0,
        ),
        _Spec(WORKSPACE, SqlWorkspacePermission, SqlWorkspaceGroupPermission, ("workspace",), SqlWorkspaceRegexPermission, SqlWorkspaceGroupRegexPermission, 0),
    ]


def _resource_id(keys: Tuple[str, ...]) -> str:
    return "/".join(str(k) for k in keys)


def _key_columns(model, names):
    return [getattr(model, n) for n in names if hasattr(model, n)]


# ---------------------------------------------------------------------------
# Regex holders
# ---------------------------------------------------------------------------

#: A principal's regex rules in the order the resolver evaluates them (priority, then id).
RuleList = List[Any]


def _regex_permission(rules: RuleList, subject: str, workspace: bool = False) -> Optional[str]:
    """The permission ``rules`` resolve to for ``subject``, exactly as the request-time resolver does.

    ``None`` when nothing matches — or when a pattern is malformed, which holds nothing either.
    """
    from mlflow.exceptions import MlflowException

    try:
        if workspace:
            from mlflow_oidc_auth.utils.workspace_cache import _match_workspace_regex_permission

            permission = _match_workspace_regex_permission(rules, subject)
            return permission.name if permission is not None else None
        from mlflow_oidc_auth.utils.permissions import _match_regex_permission

        return _match_regex_permission(rules, subject, "resource")
    except (MlflowException, re.error):
        return None


def _manages_by_rules(rules: RuleList, subject: str) -> bool:
    """Whether ``rules`` resolve to ``MANAGE`` for ``subject``, first match by priority."""
    return _regex_permission(rules, subject) == MANAGE


def _manages_workspace_by_rules(rules: RuleList, subject: str) -> bool:
    """Workspace variant: ties at the best priority resolve to the most permissive match."""
    return _regex_permission(rules, subject, workspace=True) == MANAGE


class _Context:
    """Per-run state shared across resource types, each part loaded once and only when needed."""

    def __init__(self, session, user_id: int):
        self.session = session
        self.user_id = user_id
        self._memberships: Optional[Dict[int, FrozenSet[int]]] = None

    def other_active_memberships(self) -> Dict[int, FrozenSet[int]]:
        """``{user_id: group_ids}`` for every active user other than the departing one."""
        if self._memberships is None:
            from mlflow_oidc_auth.db.models import SqlUser, SqlUserGroup

            groups: Dict[int, Set[int]] = defaultdict(set)
            rows = (
                self.session.query(SqlUserGroup.user_id, SqlUserGroup.group_id)
                .join(SqlUser, SqlUser.id == SqlUserGroup.user_id)
                .filter(SqlUser.active.is_(True), SqlUser.id != self.user_id)
                .all()
            )
            for member, group in rows:
                groups[member].add(group)
            self._memberships = {member: frozenset(ids) for member, ids in groups.items()}
        return self._memberships

    def managed_groups(self) -> Set[int]:
        """Groups with at least one active member who is not the departing user."""
        return {group for ids in self.other_active_memberships().values() for group in ids}


def _sort_rules(rules: Iterable[Any]) -> RuleList:
    return sorted(rules, key=lambda r: (r.priority, r.id))


def _rule_columns(model):
    columns = [model.id, model.regex, model.priority, model.permission]
    if hasattr(model, "prompt"):
        columns.append(model.prompt)
    return columns


def _prompt_flag(row) -> bool:
    return bool(getattr(row, "prompt", False))


def _limited(values: List[str], what: str) -> List[str]:
    if len(values) > _EXTERNAL_LOOKUP_LIMIT:
        logger.warning(
            "Orphan check: %d %s need an MLflow lookup to resolve regex grants; only the first %d are resolved, the rest are reported",
            len(values),
            what,
            _EXTERNAL_LOOKUP_LIMIT,
        )
    return values[:_EXTERNAL_LOOKUP_LIMIT]


def _experiment_names(experiment_ids: List[str]) -> Dict[str, str]:
    """``{experiment_id: name}`` from the tracking store. Unresolvable ids are left out."""
    from mlflow.server.handlers import _get_tracking_store

    try:
        tracking_store = _get_tracking_store()
    except Exception:
        logger.warning("Orphan check: tracking store unavailable; experiment regex grants are not resolved")
        return {}
    names: Dict[str, str] = {}
    for experiment_id in _limited(experiment_ids, "experiments"):
        try:
            names[experiment_id] = tracking_store.get_experiment(experiment_id).name
        except Exception:
            logger.debug("Orphan check: experiment %s could not be resolved; treating it as not regex-held", experiment_id)
    return names


def _prompt_flags(names: List[str]) -> Dict[str, bool]:
    """``{name: is_prompt}`` from the model registry. Unresolvable names are left out."""
    from mlflow.prompt.constants import IS_PROMPT_TAG_KEY
    from mlflow.server.handlers import _get_model_registry_store

    try:
        registry_store = _get_model_registry_store()
    except Exception:
        logger.warning("Orphan check: model registry unavailable; registered model regex grants are not resolved")
        return {}
    flags: Dict[str, bool] = {}
    for name in _limited(names, "registered models"):
        try:
            model = registry_store.get_registered_model(name)
            # ``RegisteredModel.tags`` hides the prompt marker; the raw tags carry it.
            tags = getattr(model, "_tags", None) or {}
            flags[name] = str(tags.get(IS_PROMPT_TAG_KEY, "")).lower() == "true"
        except Exception:
            logger.debug("Orphan check: registered model %s could not be resolved; treating it as not regex-held", name)
    return flags


class _Holder(NamedTuple):
    """One other active user's grants on a resource type, as their resolver would see them."""

    direct: Dict[Tuple[str, ...], str]
    group: Dict[Tuple[str, ...], str]
    #: ``{prompt_flag: rules}`` for the user's own patterns and for their groups' patterns.
    regex: Dict[bool, RuleList]
    group_regex: Dict[bool, RuleList]


def _more_permissive(a: Optional[str], b: str) -> str:
    from mlflow_oidc_auth.permissions import get_permission

    if a is None:
        return b
    return b if get_permission(b).priority > get_permission(a).priority else a


def _regex_holders(ctx: _Context, spec: _Spec) -> List[_Holder]:
    """Other active users with a ``MANAGE`` pattern (their own or a group's), with every grant that
    could decide their permission first. Four statements plus the shared membership read.

    A user whose patterns hold no ``MANAGE`` rule can never manage anything through them, and is
    already counted (or not) by the direct and group checks, so they are left out.
    """
    from mlflow_oidc_auth.db.models import SqlUser

    memberships = ctx.other_active_memberships()
    own: Dict[int, Dict[bool, List[Any]]] = defaultdict(lambda: defaultdict(list))
    rows = (
        ctx.session.query(spec.user_regex_model.user_id, *_rule_columns(spec.user_regex_model))
        .join(SqlUser, SqlUser.id == spec.user_regex_model.user_id)
        .filter(SqlUser.active.is_(True), SqlUser.id != ctx.user_id)
        .all()
    )
    for row in rows:
        own[row.user_id][_prompt_flag(row)].append(row)

    managed = ctx.managed_groups()
    per_group: Dict[int, Dict[bool, List[Any]]] = defaultdict(lambda: defaultdict(list))
    if managed:
        for row in ctx.session.query(spec.group_regex_model.group_id, *_rule_columns(spec.group_regex_model)).all():
            if row.group_id in managed:
                per_group[row.group_id][_prompt_flag(row)].append(row)

    def has_manage(rules_by_flag) -> bool:
        return any(r.permission == MANAGE for rules in rules_by_flag.values() for r in rules)

    candidates = {u for u, rules in own.items() if has_manage(rules)}
    candidates |= {u for u, groups in memberships.items() if any(has_manage(per_group[g]) for g in groups if g in per_group)}
    if not candidates:
        return []

    key_names = spec.key_columns
    direct: Dict[int, Dict[Tuple[str, ...], str]] = defaultdict(dict)
    user_keys = _key_columns(spec.user_model, key_names)
    for row in ctx.session.query(spec.user_model.user_id, spec.user_model.permission, *user_keys).filter(spec.user_model.user_id.in_(candidates)).all():
        direct[row[0]][tuple(row[2:])] = row[1]
    group_grants: Dict[int, Dict[Tuple[str, ...], str]] = defaultdict(dict)
    candidate_groups = {g for u in candidates for g in memberships.get(u, ())}
    if candidate_groups:
        group_keys = _key_columns(spec.group_model, key_names)
        rows = (
            ctx.session.query(spec.group_model.group_id, spec.group_model.permission, *group_keys).filter(spec.group_model.group_id.in_(candidate_groups)).all()
        )
        for row in rows:
            group_grants[row[0]][tuple(row[2:])] = row[1]

    holders = []
    for u in sorted(candidates):
        groups = memberships.get(u, frozenset())
        via_groups: Dict[Tuple[str, ...], str] = {}
        for g in groups:
            for keys, permission in group_grants.get(g, {}).items():
                via_groups[keys] = _more_permissive(via_groups.get(keys), permission)
        holders.append(
            _Holder(
                direct=direct.get(u, {}),
                group=via_groups,
                regex={flag: _sort_rules(own[u][flag]) for flag in (False, True)} if u in own else {False: [], True: []},
                group_regex={flag: _sort_rules([r for g in groups for r in per_group[g][flag]]) if per_group else [] for flag in (False, True)},
            )
        )
    return holders


def _resolves_to_manage(holder: _Holder, keys: Tuple[str, ...], subject: Optional[str], prompt: bool, workspace: bool) -> bool:
    """Replay ``PERMISSION_SOURCE_ORDER`` for one holder: the first source with an answer decides.

    A direct or group grant at any level shadows a later regex source, as it does at request time.
    ``subject`` is ``None`` when the regex subject could not be resolved: the regex sources then
    give no answer. The configured default is never a holder.
    """
    from mlflow_oidc_auth.config import config

    for source in config.PERMISSION_SOURCE_ORDER:
        if source == "user":
            answer = holder.direct.get(keys)
        elif source == "group":
            answer = holder.group.get(keys)
        elif source == "regex":
            answer = _regex_permission(holder.regex[prompt], subject, workspace) if subject is not None else None
        elif source == "group-regex":
            answer = _regex_permission(holder.group_regex[prompt], subject, workspace) if subject is not None else None
        else:
            continue
        if answer is not None:
            return answer == MANAGE
    return False


def _regex_held(ctx: _Context, spec: _Spec, candidates: Set[Tuple[str, ...]]) -> Set[Tuple[str, ...]]:
    """The subset of ``candidates`` another active user manages through a regex grant.

    Each holder's permission is resolved by replaying ``PERMISSION_SOURCE_ORDER``, so a direct or
    group grant that the resolver would reach first (say, ``READ``) is what they get, whatever their
    patterns say. A bounded number of statements; at most :data:`_EXTERNAL_LOOKUP_LIMIT` MLflow
    lookups where the subject lives there.
    """
    holders = _regex_holders(ctx, spec)
    if not holders:
        return set()
    workspace = spec.resource_type == WORKSPACE

    def held(keys, subject, prompt) -> bool:
        return any(_resolves_to_manage(h, keys, subject, prompt, workspace) for h in holders)

    if spec.regex_key_index is None:  # experiments: patterns match the name
        names = _experiment_names(sorted({keys[0] for keys in candidates}))
        return {keys for keys in candidates if keys[0] in names and held(keys, names[keys[0]], False)}

    if spec.resource_type != REGISTERED_MODEL:
        return {keys for keys in candidates if held(keys, keys[spec.regex_key_index], False)}

    # Registered models and prompts share grant rows but not patterns: model patterns apply to a
    # model, prompt patterns to a prompt. Ask the registry only when the two disagree.
    result: Set[Tuple[str, ...]] = set()
    undecided: Dict[str, Tuple[str, ...]] = {}
    for keys in candidates:
        as_model, as_prompt = held(keys, keys[0], False), held(keys, keys[0], True)
        if as_model and as_prompt:
            result.add(keys)
        elif as_model or as_prompt:
            undecided[keys[0]] = keys
    if undecided:
        flags = _prompt_flags(sorted(undecided))
        for name, keys in undecided.items():
            if name in flags and held(keys, name, flags[name]):
                result.add(keys)
    return result


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def _detect(session, user_id: int) -> List[Tuple[str, str, str]]:
    """``[(resource_type, resource_id, via), ...]`` for which ``user_id`` is the last ``MANAGE`` holder."""
    from mlflow_oidc_auth.db.models import SqlGroup, SqlUser, SqlUserGroup

    ctx = _Context(session, user_id)
    managed_groups = ctx.managed_groups()
    orphans: List[Tuple[str, str, str]] = []

    for spec in _specs():
        key_names = spec.key_columns
        user_keys = _key_columns(spec.user_model, key_names)
        group_keys = _key_columns(spec.group_model, key_names)
        if len(user_keys) != len(key_names) or len(group_keys) != len(key_names):
            logger.warning("Skipping orphan check for %s: unexpected permission schema", spec.resource_type)
            continue

        direct = {tuple(r) for r in session.query(*user_keys).filter(spec.user_model.user_id == user_id, spec.user_model.permission == MANAGE).all()}
        # Resources the departing user manages through one of their groups, with the group names.
        through_group: Dict[Tuple[str, ...], List[str]] = defaultdict(list)
        rows = (
            session.query(*group_keys, SqlGroup.group_name)
            .join(SqlUserGroup, SqlUserGroup.group_id == spec.group_model.group_id)
            .join(SqlGroup, SqlGroup.id == spec.group_model.group_id)
            .filter(SqlUserGroup.user_id == user_id, spec.group_model.permission == MANAGE)
            .all()
        )
        for r in rows:
            through_group[tuple(r[:-1])].append(r[-1])
        mine = direct | set(through_group)
        if not mine:
            continue

        others = {
            tuple(r)
            for r in session.query(*user_keys)
            .join(SqlUser, SqlUser.id == spec.user_model.user_id)
            .filter(spec.user_model.permission == MANAGE, spec.user_model.user_id != user_id, SqlUser.active.is_(True))
            .all()
        }
        groups = {
            tuple(r[:-1])
            for r in session.query(*group_keys, spec.group_model.group_id).filter(spec.group_model.permission == MANAGE).all()
            if r[-1] in managed_groups
        }
        candidates = mine - others - groups
        if candidates:
            candidates -= _regex_held(ctx, spec, candidates)
        for keys in sorted(candidates):
            via = VIA_DIRECT if keys in direct else VIA_GROUP_PREFIX + sorted(through_group[keys])[0]
            orphans.append((spec.resource_type, _resource_id(keys), via))
    return orphans


def _find_in_session(session, user_id: int) -> List[Tuple[str, str]]:
    """Orphan detection against an open session. See :func:`find_orphaned_resources`."""
    return [(resource_type, resource_id) for resource_type, resource_id, _ in _detect(session, user_id)]


def _store_or_singleton(store):
    if store is None:
        from mlflow_oidc_auth.store import store as store_singleton

        return store_singleton
    return store


def find_orphaned_resources(username: str, store=None, via: Optional[Dict[Tuple[str, str], str]] = None) -> List[Tuple[str, str]]:
    """Resources for which ``username`` is the last holder of ``MANAGE``.

    Parameters:
        username: The departing user.
        store: The store to read; defaults to the singleton.
        via: When given, filled with ``{(resource_type, resource_id): via}`` — ``"direct"`` or
            ``"group:<name>"``, the departing user's own path to ``MANAGE``.

    Returns:
        ``[(resource_type, resource_id), ...]``. A scorer's id is ``<experiment_id>/<scorer_name>``.
        Empty for an unknown user.
    """
    from mlflow_oidc_auth.db.models import SqlUser
    from mlflow_oidc_auth.repository.user import normalize_username

    store = _store_or_singleton(store)
    with store.ManagedSessionMaker() as session:
        user = session.query(SqlUser.id).filter(SqlUser.username == normalize_username(username)).one_or_none()
        if user is None:
            return []
        found = _detect(session, user[0])
    if via is not None:
        via.update({(t, i): v for t, i, v in found})
    return [(t, i) for t, i, _ in found]


def _valid_fallback(session, fallback: Optional[str], departing_id: int):
    """The fallback principal's row, or None when it may not receive a hand-over.

    It must exist, be active, not be a service account and not be the departing user. A service
    account is refused because it is a credential, not a person accountable for the resource.
    """
    from mlflow_oidc_auth.db.models import SqlUser
    from mlflow_oidc_auth.repository.user import normalize_username

    if not fallback:
        return None
    target = session.query(SqlUser).filter(SqlUser.username == normalize_username(fallback)).one_or_none()
    if target is None or not target.active or target.is_service_account or target.id == departing_id:
        logger.warning(
            "ORPHAN_FALLBACK_PRINCIPAL %r is not an existing, active, non-service-account user other than the one being deleted; "
            "orphaned resources are reported only",
            fallback,
        )
        return None
    return target


def _transfer_in_session(session, target_id: int, orphans: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Grant ``MANAGE`` on each orphan to ``target_id``, raising an existing lower grant."""
    specs: Dict[str, _Spec] = {spec.resource_type: spec for spec in _specs()}
    transferred: List[Tuple[str, str]] = []
    for resource_type, resource_id in orphans:
        user_model, key_names = specs[resource_type].user_model, specs[resource_type].key_columns
        values = resource_id.split("/", len(key_names) - 1)
        criteria = {name: value for name, value in zip(key_names, values)}
        existing = session.query(user_model).filter_by(user_id=target_id, **criteria).one_or_none()
        if existing is None:
            session.add(user_model(user_id=target_id, permission=MANAGE, **criteria))
        else:
            existing.permission = MANAGE
        transferred.append((resource_type, resource_id))
    session.flush()
    return transferred


def _audit(orphans, transferred, fallback, *, actor: str, source: str, username: str, via: Optional[Dict[Tuple[str, str], str]] = None) -> None:
    from mlflow_oidc_auth.audit import emit_audit_event

    for resource_type, resource_id in orphans:
        try:
            detail = {"user": username, "source": source}
            path = (via or {}).get((resource_type, resource_id))
            if path:
                detail["via"] = path
            if (resource_type, resource_id) in transferred:
                detail["transferred_to"] = fallback
            emit_audit_event("resource.orphaned", actor=actor, resource_type=resource_type, resource_id=resource_id, detail=detail)
        except Exception:
            logger.exception("Could not audit orphaned %s %s", resource_type, resource_id)


def report_orphans(username: str, *, actor: str, source: str, store=None) -> List[Tuple[str, str]]:
    """Find and audit the resources ``username`` leaves unmanaged. For deactivation.

    Nothing is handed over: a deactivated user may come back, and their grants are still theirs.

    **Never raises.** Deprovisioning is the security-relevant half of this operation and must not
    wait on, or be undone by, a failure in the housekeeping half.

    Returns:
        The orphans found; empty on failure.
    """
    via: Dict[Tuple[str, str], str] = {}
    try:
        orphans = find_orphaned_resources(username, store=store, via=via)
    except Exception:
        logger.exception("Orphan detection failed for %s; continuing without it", username)
        return []
    _audit(orphans, set(), None, actor=actor, source=source, username=username, via=via)
    return orphans


def delete_user_reporting_orphans(
    username: str,
    *,
    actor: str,
    source: str,
    store=None,
    written_by: Optional[str] = None,
    admin_override: bool = False,
) -> List[Tuple[str, str]]:
    """Hard-delete ``username``, handing orphaned resources to ``ORPHAN_FALLBACK_PRINCIPAL``.

    Detection and hand-over run inside the delete's own transaction: detection before the cascade
    removes the grants it reads, the hand-over only after the cascade and the user row's delete
    have been flushed (the fallback's grants are independent of the rows removed). So a delete
    that fails (the last-admin invariant, a database error in the cascade) never reaches the
    hand-over, and a failed commit rolls it back — a hand-over can never outlive a refused delete.
    This ordering, not savepoint semantics, is what guarantees it: on SQLite a savepoint opened
    before any write begins the transaction itself and its release commits it.

    Neither half raises: a failure is logged and the delete proceeds without it. The hand-over
    runs under a savepoint — by then nested inside a transaction the cascade has begun — so a
    failed hand-over is undone without undoing the delete. Events are emitted only after the
    delete has committed.

    The ``managed_by`` guard (#360) is evaluated by the delete itself, before either hook runs:
    ``written_by`` and ``admin_override`` are passed through, and a refused delete detects nothing
    and hands nothing over.

    Returns:
        The orphans found.

    Raises:
        MlflowException: Whatever the delete itself raises, the ownership refusal included.
    """
    store = _store_or_singleton(store)
    try:
        from mlflow_oidc_auth.config import config

        fallback = getattr(config, "ORPHAN_FALLBACK_PRINCIPAL", None) or None
    except Exception:
        fallback = None

    found: List[Tuple[str, str]] = []
    via: Dict[Tuple[str, str], str] = {}
    transferred: List[Tuple[str, str]] = []
    departing: List[int] = []

    def before_cascade(session, user) -> None:
        try:
            with session.begin_nested():
                detected = _detect(session, user.id)
            found.extend((t, i) for t, i, _ in detected)
            via.update({(t, i): v for t, i, v in detected})
            departing.append(user.id)
        except Exception:
            logger.exception("Orphan detection failed while deleting %s; deleting without it", username)
            found.clear()
            via.clear()

    def after_cascade(session) -> None:
        if not found or not departing:
            return
        try:
            with session.begin_nested():
                target = _valid_fallback(session, fallback, departing[0])
                if target is not None:
                    transferred.extend(_transfer_in_session(session, target.id, found))
        except Exception:
            logger.exception("Orphan hand-over failed while deleting %s; deleting without it", username)
            transferred.clear()

    store.delete_user_with_hook(username, before_cascade, after_cascade, written_by=written_by, admin_override=admin_override, actor=actor)

    if transferred:
        try:
            from mlflow_oidc_auth.utils.permissions import flush_permission_cache

            flush_permission_cache()
        except Exception:
            logger.warning("Permission cache flush failed after orphan hand-over; entries expire via TTL")
    _audit(found, set(transferred), fallback, actor=actor, source=source, username=username, via=via)
    return found
