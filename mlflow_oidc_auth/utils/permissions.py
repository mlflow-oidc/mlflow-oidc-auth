"""
Permission resolution utilities for MLflow OIDC Auth.

``resolve_permission()`` is the single entry point for one resource's permission, for all 8
resource types in ``grant_context.PERMISSION_REGISTRY``. The decision is made by ``utils/grant_context.py``
(issue #460), the one resolver shared with the list filters and the FastAPI batch path: the
user's grants are read once per resource type and resolved in memory.

Decisions are also cached with a pluggable cache backend. Entries are keyed by
``resource_type:resource_id:username`` (plus every extra resource-identifying kwarg, e.g. the
scorer name, for composite ids) and expire after PERMISSION_CACHE_TTL_SECONDS (default 30). The
backend is selected via ``CACHE_BACKEND`` config (``"local"`` or ``"redis"``).

Explicit invalidation is available via invalidate_permission_cache() and
flush_permission_cache(); both also drop the cached grant contexts.

Existing public functions (effective_*, can_*) are thin wrappers around
resolve_permission() and remain backward-compatible.
"""

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Sequence
from urllib.parse import quote

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.cache import CacheBackend, get_cache_backend
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import PermissionResult
from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.permissions import ALL_PERMISSIONS, NO_PERMISSIONS, USE, get_permission
from mlflow_oidc_auth.store import store

logger = get_logger()

# ---------------------------------------------------------------------------
# Permission cache (lazy init to avoid import-time config reads)
# ---------------------------------------------------------------------------

_PERMISSION_CACHE_DEFAULT_TTL = 30

_permission_cache: CacheBackend | None = None


def _get_permission_cache() -> CacheBackend:
    """Get or create the permission resolution cache (lazy init).

    "_v2": entries are :class:`_CachedDecision` since issue #460, so a replica still on the old
    format never reads one, nor this one an old entry.
    """
    global _permission_cache
    if _permission_cache is None:
        ttl = getattr(config, "PERMISSION_CACHE_TTL_SECONDS", _PERMISSION_CACHE_DEFAULT_TTL)
        # Validated once in config.py (positive int, default 10000).
        _permission_cache = get_cache_backend("permissions_v2", maxsize=config.PERMISSION_CACHE_MAX_SIZE, ttl=ttl)
    return _permission_cache


@dataclass(frozen=True)
class _CachedDecision:
    """A cached decision and the time it stops being valid.

    A decision is built from grant reads that may themselves be cached, possibly by another
    replica. Its expiry is capped at theirs, so a revoke is never served longer than one
    ``PERMISSION_CACHE_TTL_SECONDS`` after the grants were read — not one TTL after the decision
    was made from grants already nearly that old.
    """

    result: PermissionResult
    expires_at: float


# Distinguishes "no workspace context on this request" from a workspace literally named
# after it. Cannot collide with a real name: MLflow's WorkspaceNameValidator rejects ":".
_NO_WORKSPACE_CACHE_MARKER = "::no-workspace"


def _get_cache_workspace() -> str | None:
    """Return the workspace component of the cache key, or None when workspaces are off.

    This must describe what ``resolve_permission`` actually *did*, not what MLflow would
    resolve the request to. A header-less request currently skips workspace authorization
    entirely and keeps the resource-level fallback, whereas an explicit
    ``X-MLFLOW-WORKSPACE: default`` request runs the workspace check and can come back
    ``workspace-deny``. Those are different decisions, so they must not share a key —
    substituting the default workspace name here let a header-less result be served to an
    explicit-default request, and vice versa, for the lifetime of the entry.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return None

    from mlflow_oidc_auth.bridge.user import get_request_workspace
    from mlflow_oidc_auth.utils.grant_workspace import current_grant_workspace

    # None also covers resolution outside a Flask request context, which likewise skips
    # the workspace branch below and so belongs in the same bucket. Grants on name-keyed
    # resources are still read in a workspace there (MLflow's resolved one, see
    # utils/grant_workspace.py), so that workspace is part of the key: a decision for one
    # workspace's "churn" must never be served for another's.
    return get_request_workspace() or f"{_NO_WORKSPACE_CACHE_MARKER}:{current_grant_workspace()}"


def _make_cache_key(resource_type: str, resource_id: str, username: str, workspace: str | None = None, **qualifiers: str) -> str:
    """Build a string cache key from the permission lookup tuple.

    The workspace is part of the key whenever workspaces are enabled: the same
    resource id denotes different entities in different workspaces, and a result
    may itself be workspace-derived, so a workspace-blind key would serve one
    tenant's decision to another for the lifetime of the entry.

    ``qualifiers`` are the extra resource-identifying kwargs a registry builder takes
    when the id is composite — a scorer is ``(experiment_id, scorer_name)``. They MUST
    be part of the key: keyed on the experiment id alone, the decision for one scorer
    was served for every other scorer in the same experiment until the entry expired.
    Composite keys quote every component, so a ``:`` inside an id or a name cannot make
    two different lookups collide.
    """
    if qualifiers:
        parts = [quote(str(p), safe="") for p in (resource_type, resource_id, username)]
        parts += [f"{quote(k, safe='')}={quote(str(v), safe='')}" for k, v in sorted(qualifiers.items())]
        key = ":".join(parts)
        return f"{quote(workspace, safe='')}:{key}" if workspace is not None else key
    if workspace is not None:
        return f"{workspace}:{resource_type}:{resource_id}:{username}"
    return f"{resource_type}:{resource_id}:{username}"


def invalidate_permission_cache(resource_type: str, resource_id: str, username: str, workspace: str | None = None, **qualifiers: str) -> None:
    """Remove a specific permission entry from cache.

    Call after permission CUD operations for a specific user+resource. When
    workspaces are enabled, pass the workspace the entry was cached under;
    omitting it falls back to the workspace of the current request. For a composite
    resource pass the same qualifiers ``resolve_permission`` was given (e.g.
    ``scorer_name=...``), or the entry is not found.
    """
    # The decision is derived from the user's cached grants; drop those first, so the decision
    # cannot be rebuilt from grants that are about to go (the order flush_permission_cache uses).
    invalidate_user_grant_contexts(username)
    cache = _get_permission_cache()
    if workspace is None:
        workspace = _get_cache_workspace()
    cache.delete(_make_cache_key(resource_type, resource_id, username, workspace, **qualifiers))


def flush_permission_cache() -> None:
    """Flush entire permission cache.

    Call after bulk operations (e.g., regex permission changes) that
    may affect many user+resource combos. Flushes the cached grant contexts
    (``grant_context``) with it, so every store wrapper that calls this
    invalidates both.
    """
    # The grant sections first: a decision recomputed between the two clears must not be
    # rebuilt from grants that are about to go.
    flush_grant_contexts()
    cache = _get_permission_cache()
    cache.clear()
    logger.debug("Permission cache fully flushed")


# Resource type constants. Defined with the resolver (utils/grant_context.py) and re-exported here.
from mlflow_oidc_auth.utils.grant_context import (  # noqa: E402
    EXPERIMENT,
    GATEWAY_ENDPOINT,
    GATEWAY_MODEL_DEFINITION,
    GATEWAY_SECRET,
    GUARD,
    MCP_SERVER,
    PROMPT,
    REGISTERED_MODEL,
    PERMISSION_REGISTRY,
    best_matching_regex,
    flush_grant_contexts,
    invalidate_user_grant_contexts,
    load_grant_context,
    permission_cache_ttl,
    resolve,
    resolve_scorer,
    walk_sources,
    workspace_fallback,
)

# The same names for log messages. CodeQL treats anything derived from a constant named
# ``*_SECRET`` as a secret, so a message names the resource type by picking the matching
# registry name here (no constant of that name on the way) rather than by echoing the value
# it was given. Kept in step with PERMISSION_REGISTRY by test_permission_fallback_observability.py.
_RESOURCE_TYPE_LOG_NAMES = tuple(kind.name for kind in permission_kinds.resource_kinds())


# ---------------------------------------------------------------------------
# Pattern matcher. The one implementation is grant_context.best_matching_regex.
# ---------------------------------------------------------------------------


def _match_regex_permission(regexes: Sequence[Any], name: str, label: str, workspace: str | None = None) -> str:
    """Raising matcher, for the creation-time source chain (see ``grant_context.best_matching_regex``).

    Parameters:
        regexes: Regex permission entities with ``regex``, ``permission``, ``priority`` and ``id``.
        name: The resource name to match.
        label: What ``name`` is (e.g. ``"model name"``), for the debug log and error message.
        workspace: The resource's workspace; the request's grant workspace when omitted.

    Returns:
        The permission of the deciding pattern.

    Raises:
        MlflowException: ``RESOURCE_DOES_NOT_EXIST`` when no pattern matches.
    """
    regex = best_matching_regex(regexes, name, label, workspace)
    if regex is None:
        raise MlflowException(f"{label} {name}", error_code=RESOURCE_DOES_NOT_EXIST)
    return regex.permission


# ---------------------------------------------------------------------------
# resolve_permission() and its workspace fallback. Resolution itself is grant_context.resolve
# (issue #460): one implementation for single checks, list filters and the FastAPI batch path.
# ---------------------------------------------------------------------------


def _apply_workspace_fallback(result: PermissionResult, username: str, resource_type: str | None = None, resource_id: str | None = None) -> PermissionResult:
    """Defer a generic ``fallback`` result to the user's workspace permission.

    Per WSAUTH-C/WSAUTH-04: when workspaces are enabled and no resource-level
    permission was found, use the user's permission on the request workspace
    instead of the global default; if the user has no workspace permission,
    deny with ``NO_PERMISSIONS`` (kind ``workspace-deny``). A header-less request
    (no workspace) is left unchanged so the global default still applies.

    The decision is ``grant_context.workspace_fallback``, shared with ``resolve_permission``,
    the list filters and the batch path; this is its form for the creation resolvers, which have
    no grant context.
    """
    if result.kind != "fallback" or not config.MLFLOW_ENABLE_WORKSPACES:
        return result

    from mlflow_oidc_auth.bridge.user import get_request_workspace
    from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached

    return workspace_fallback(
        result,
        enabled=True,
        request_workspace=get_request_workspace(),
        resource_type=resource_type,
        in_request_workspace=lambda: _experiment_in_request_workspace(resource_id),
        workspace_permission=lambda workspace: get_workspace_permission_cached(username, workspace),
    )


def _experiment_in_request_workspace(experiment_id: str | None) -> bool:
    """Whether MLflow finds ``experiment_id`` in the request's workspace. Any failure is a no."""
    if not experiment_id:
        return False
    try:
        return _get_tracking_store().get_experiment(str(experiment_id)) is not None
    except Exception:
        return False


_FALLBACK_COUNTS: Dict[str, int] = {}

# Warn on these occurrence numbers, then every _FALLBACK_WARN_EVERY after that. The
# batch filters resolve one permission per resource, so a listing of a few thousand
# experiments would otherwise emit a few thousand identical warnings.
_FALLBACK_WARN_AT = frozenset((1, 10, 100, 1_000))
_FALLBACK_WARN_EVERY = 10_000

# A bounded, in-process sample of which resources were reached through the default.
# Bounded because it is never drained: an unbounded set keyed on caller-supplied ids
# would be a memory leak on a busy server.
_FALLBACK_SAMPLES: Dict[str, list] = {}
_FALLBACK_SAMPLE_LIMIT = 50


def get_permission_fallback_counts() -> Dict[str, int]:
    """How many times each resource type has fallen back to the configured default.

    Exposed for diagnostics and tests. Counts are per process and reset on restart.
    """
    return dict(_FALLBACK_COUNTS)


def get_permission_fallback_samples() -> Dict[str, list]:
    """Which resources were reached through the configured default, per resource type.

    Capped at _FALLBACK_SAMPLE_LIMIT ids per type — enough to start a migration, small
    enough not to grow without bound. Deliberately not logged: see record_permission_fallback.
    """
    return {resource_type: list(ids) for resource_type, ids in _FALLBACK_SAMPLES.items()}


def reset_permission_fallback_counts() -> None:
    """Clear the counters and samples (tests)."""
    _FALLBACK_COUNTS.clear()
    _FALLBACK_SAMPLES.clear()


def record_permission_fallback(resource_type: str, resource_id: str, username: str, permission) -> None:
    """Record that a permission decision came from ``DEFAULT_MLFLOW_PERMISSION``.

    A fallback means the resource has no user, group, regex or group-regex grant for this
    user, so the configured default decided the outcome. That is unremarkable when the
    default DENIES — the user simply has no access. It is worth surfacing when the default
    GRANTS, because then access is being handed out by configuration rather than by an
    explicit permission record, and nothing in the system says who intended it.

    The default is ``NO_PERMISSIONS`` (since v7.6.0, issue #293), so a granting fallback only
    happens where an operator has set a permissive ``DEFAULT_MLFLOW_PERMISSION`` — typically
    to keep pre-7.6 behaviour while migrating. That is the exposure operators should be able
    to see. Only the granting case warns; both cases are counted and logged at debug.

    Warnings are throttled by occurrence count rather than suppressed, so a long-running
    process keeps reporting at a decreasing rate instead of going quiet after startup.
    The counter is not synchronized: concurrent requests may race and skip a warning
    threshold, which affects log cadence only, never an authorization outcome.
    """
    count = _FALLBACK_COUNTS.get(resource_type, 0) + 1
    _FALLBACK_COUNTS[resource_type] = count

    # Resource ids are recorded in-process rather than written to the log. One of the
    # resource types here is the GATEWAY SECRET, whose id is the secret's NAME — not its
    # value, but a name like "openai-prod-key" is still something that does not belong in
    # a log aggregator, and CodeQL flags the whole parameter as tainted for exactly that
    # reason. get_permission_fallback_samples() gives an operator the same detail on
    # demand, without every deployment shipping identifiers off-host by default.
    samples = _FALLBACK_SAMPLES.setdefault(resource_type, [])
    if len(samples) < _FALLBACK_SAMPLE_LIMIT and resource_id not in samples:
        samples.append(resource_id)

    # The level and the resource type are logged by fixed names, not read off the arguments:
    # for a gateway secret both flow from secret-named code, and static analysis cannot tell
    # that only a level and a type name, never the secret, reach the log.
    level = next((name for name, known in ALL_PERMISSIONS.items() if known == permission), "UNKNOWN")
    kind = next((name for name in _RESOURCE_TYPE_LOG_NAMES if name == resource_type), "resource")

    logger.debug("Permission fallback: %s granted %s to %s (occurrence %d)", kind, level, username, count)

    if not permission.can_read:
        # A fallback that grants nothing is the safe, expected shape.
        return

    if count in _FALLBACK_WARN_AT or count % _FALLBACK_WARN_EVERY == 0:
        logger.warning(
            f"DEFAULT_MLFLOW_PERMISSION granted {level} on a {kind} to {username} "
            f"because no explicit permission exists ({count} such grants for {kind} so far). "
            "Access is coming from configuration rather than a permission record. "
            "Call get_permission_fallback_samples() for the affected resource ids, or enable DEBUG logging. "
            "The shipped default is NO_PERMISSIONS (issue #293); see docs/permissions.md 'Migrating to deny-by-default'."
        )


def resolve_permission(resource_type: str, resource_id: str, username: str, **kwargs: str) -> PermissionResult:
    """Single entry point for one resource's permission. Per D-01 (REFAC-01).

    Resolves with a single-resource grant context (``grant_context.resolve``): direct grants by
    their indexed per-resource queries, patterns from the user's cached pattern read. The decision
    is cached too, keyed ``resource_type:resource_id:username`` plus every kwarg, which identify
    composite resources (``scorer_name`` for a scorer), until the earlier of one TTL from now and
    one TTL from the oldest grant read it was built from.

    Raises:
        KeyError: For an unknown resource type.
    """
    if resource_type not in PERMISSION_REGISTRY:
        # An unknown type is an error, never a cache miss or a fallback decision.
        raise KeyError(resource_type)
    # kwargs identify the resource beyond its id (scorer_name for a scorer), so they are part of the key.
    cache_key = _make_cache_key(resource_type, resource_id, username, _get_cache_workspace(), **kwargs)
    return _cached_decision(cache_key, username, lambda ctx: resolve(ctx, resource_type, resource_id, name=kwargs.get("scorer_name")))


def _cached_decision(cache_key: str, username: str, decide: Callable[[Any], PermissionResult]) -> PermissionResult:
    """A decision from the permission cache, made with a single-resource grant context on a miss.

    The context reads the invalidation generation once, before it reads any grant; the decision
    is cached only if no invalidation overlapped (one generation read after the write), and only
    until the earlier of one TTL from now and one TTL from the oldest grant read it was built from.
    """
    cache = _get_permission_cache()
    cached = cache.get(cache_key)
    if isinstance(cached, _CachedDecision):
        if time.time() < cached.expires_at:
            return cached.result
        cache.delete(cache_key)

    ctx = load_grant_context(username)
    generation = ctx.generation()
    result = decide(ctx)
    ttl = permission_cache_ttl()
    expires_at = time.time() + ttl
    if ctx.oldest_read is not None:
        expires_at = min(expires_at, ctx.oldest_read + ttl)
    if expires_at > time.time():
        GUARD.store_unless_raced(cache, cache_key, _CachedDecision(result, expires_at), generation, check_before_write=False)
    return result


# ---------------------------------------------------------------------------
# Public API — thin wrappers (unchanged signatures)
# ---------------------------------------------------------------------------


def effective_experiment_permission(experiment_id: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return resolve_permission(EXPERIMENT, experiment_id, user)


def effective_registered_model_permission(model_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return resolve_permission(REGISTERED_MODEL, model_name, user)


# ---------------------------------------------------------------------------
# Creation-time resolvers (per issue #202 / #195)
#
# At creation the resource does not exist yet, so user/group sources keyed by
# experiment id or model name cannot apply. Only name-based regex sources are
# meaningful. A regex/group-regex miss falls back to the workspace permission
# (when workspaces are enabled) or the global default, via the shared helper.
# These are intentionally uncached: creation is rare and the request-scoped
# workspace fallback must be re-evaluated each call.
# ---------------------------------------------------------------------------


def _permission_new_experiment_sources_config(experiment_name: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "regex": lambda experiment_name=experiment_name, user=username: _match_regex_permission(
            store.list_experiment_regex_permissions(user), experiment_name, "experiment name"
        ),
        "group-regex": lambda experiment_name=experiment_name, user=username: _match_regex_permission(
            store.list_group_experiment_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            experiment_name,
            "experiment name",
        ),
    }


def _permission_new_registered_model_sources_config(model_name: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "regex": lambda model_name=model_name, user=username: _match_regex_permission(
            store.list_registered_model_regex_permissions(user), model_name, "model name"
        ),
        "group-regex": lambda model_name=model_name, user=username: _match_regex_permission(
            store.list_group_registered_model_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            model_name,
            "model name",
        ),
    }


def _permission_new_prompt_sources_config(prompt_name: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "regex": lambda prompt_name=prompt_name, user=username: _match_regex_permission(store.list_prompt_regex_permissions(user), prompt_name, "prompt name"),
        "group-regex": lambda prompt_name=prompt_name, user=username: _match_regex_permission(
            store.list_group_prompt_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            prompt_name,
            "prompt name",
        ),
    }


def effective_new_experiment_permission(experiment_name: str, user: str) -> PermissionResult:
    """Resolve the permission for creating an experiment with ``experiment_name``.

    Name-based regex/group-regex only; a miss falls back to the workspace
    permission (workspaces on) or the global default (workspaces off).
    """
    result = get_permission_from_store_or_default(_permission_new_experiment_sources_config(experiment_name, user))
    return _apply_workspace_fallback(result, user)


def effective_new_registered_model_permission(model_name: str, user: str) -> PermissionResult:
    """Resolve the permission for creating a registered model named ``model_name``.

    Name-based regex/group-regex only; a miss falls back to the workspace
    permission (workspaces on) or the global default (workspaces off).
    """
    result = get_permission_from_store_or_default(_permission_new_registered_model_sources_config(model_name, user))
    return _apply_workspace_fallback(result, user)


def effective_new_prompt_permission(prompt_name: str, user: str) -> PermissionResult:
    """Resolve the permission for creating a prompt named ``prompt_name``.

    As :func:`effective_new_registered_model_permission`, with the prompt patterns (#479): only
    name-based regex and group-regex grants apply, and a miss falls back to the workspace permission
    (workspaces on) or the global default (workspaces off).

    Parameters:
        prompt_name: The name of the prompt to be created.
        user: The username.

    Returns:
        The permission the user would hold on the new prompt.
    """
    result = get_permission_from_store_or_default(_permission_new_prompt_sources_config(prompt_name, user))
    return _apply_workspace_fallback(result, user)


def effective_prompt_permission(prompt_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return resolve_permission(PROMPT, prompt_name, user)


def effective_scorer_permission(experiment_id: str, scorer_name: str, user: str) -> PermissionResult:
    """Resolve effective permission for a scorer.

    A grant on the scorer itself (user, group, regex or group-regex) decides. A scorer with
    none inherits its experiment's effective permission, which in turn falls back to the
    workspace permission or ``DEFAULT_MLFLOW_PERMISSION`` as for the experiment itself.

    Parameters:
        experiment_id: The scorer's experiment.
        scorer_name: The scorer name.
        user: The caller.

    Returns:
        The scorer's grant, or the experiment's effective permission when there is none.
    """
    # One implementation of the scorer -> experiment inheritance: grant_context.resolve_scorer.
    cache_key = _make_cache_key("effective_scorer", experiment_id, user, _get_cache_workspace(), scorer_name=scorer_name)
    return _cached_decision(cache_key, user, lambda ctx: resolve_scorer(ctx, experiment_id, scorer_name))


def effective_gateway_endpoint_permission(gateway_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return resolve_permission(GATEWAY_ENDPOINT, gateway_name, user)


def effective_gateway_secret_permission(gateway_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return resolve_permission(GATEWAY_SECRET, gateway_name, user)


def effective_gateway_model_definition_permission(gateway_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return resolve_permission(GATEWAY_MODEL_DEFINITION, gateway_name, user)


# ---------------------------------------------------------------------------
# can_* helpers (unchanged signatures)
# ---------------------------------------------------------------------------


def effective_mcp_server_permission(name: str, user: str) -> PermissionResult:
    """The caller's permission on an MCP server of the request's workspace.

    User grant, then group grants (``PERMISSION_SOURCE_ORDER``), then — with workspaces enabled —
    the caller's permission on the request's workspace. A request that names no workspace is
    served MLflow's default workspace registry, so it falls back to the caller's permission on that
    workspace (``current_grant_workspace``) rather than to ``DEFAULT_MLFLOW_PERMISSION``: the
    registry was workspace-gated that way before servers had grants of their own, and a permissive
    global default must not widen it. With workspaces disabled the global default applies, as for every resource.
    """
    result = resolve_permission(MCP_SERVER, name, user)
    if result.kind != "fallback" or not config.MLFLOW_ENABLE_WORKSPACES:
        return result
    from mlflow_oidc_auth.utils.grant_workspace import current_grant_workspace
    from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached

    # The workspace MLflow serves the request from — its default, which a workspace provider may
    # name differently from ``default`` — the same one the grants were just looked up in.
    ws_perm = get_workspace_permission_cached(user, current_grant_workspace())
    if ws_perm is not None:
        return PermissionResult(ws_perm, "workspace")
    return PermissionResult(NO_PERMISSIONS, "workspace-deny")


def can_read_experiment(experiment_id: str, user: str) -> bool:
    permission = effective_experiment_permission(experiment_id, user).permission
    return permission.can_read


def can_read_registered_model(model_name: str, user: str) -> bool:
    permission = effective_registered_model_permission(model_name, user).permission
    return permission.can_read


def can_manage_experiment(experiment_id: str, user: str) -> bool:
    permission = effective_experiment_permission(experiment_id, user).permission
    return permission.can_manage


def can_manage_registered_model(model_name: str, user: str) -> bool:
    permission = effective_registered_model_permission(model_name, user).permission
    return permission.can_manage


def can_manage_scorer(experiment_id: str, scorer_name: str, user: str) -> bool:
    """Check if a user can manage a scorer.

    Scorers are scoped to an experiment. This uses the effective scorer permission
    resolution (user/group/regex/fallback) and checks the MANAGE bit.
    """
    permission = effective_scorer_permission(experiment_id, scorer_name, user).permission
    return permission.can_manage


def can_read_gateway_endpoint(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_endpoint_permission(gateway_name, user).permission
    return permission.can_read


def can_use_gateway_endpoint(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_endpoint_permission(gateway_name, user).permission
    return permission.can_use


def can_update_gateway_endpoint(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_endpoint_permission(gateway_name, user).permission
    return permission.can_update


def can_manage_gateway_endpoint(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_endpoint_permission(gateway_name, user).permission
    return permission.can_manage


def can_read_gateway_secret(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_secret_permission(gateway_name, user).permission
    return permission.can_read


def can_use_gateway_secret(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_secret_permission(gateway_name, user).permission
    return permission.can_use


def can_update_gateway_secret(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_secret_permission(gateway_name, user).permission
    return permission.can_update


def can_manage_gateway_secret(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_secret_permission(gateway_name, user).permission
    return permission.can_manage


def can_read_gateway_model_definition(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_model_definition_permission(gateway_name, user).permission
    return permission.can_read


def can_use_gateway_model_definition(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_model_definition_permission(gateway_name, user).permission
    return permission.can_use


def can_update_gateway_model_definition(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_model_definition_permission(gateway_name, user).permission
    return permission.can_update


def can_manage_gateway_model_definition(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_model_definition_permission(gateway_name, user).permission
    return permission.can_manage


def can_read_mcp_server(name: str, user: str) -> bool:
    return effective_mcp_server_permission(name, user).permission.can_read


def _mcp_server_write_permission(name: str, user: str):
    """The permission ``user`` may change ``name`` with, or None.

    An MCP server nobody manages — one registered before servers had permissions, when only
    administrators could change them — stays that way: a permission that comes only from the
    workspace (or the global default) does not reach it until a user or group is granted ``MANAGE``
    on it. A lesser grant — ``READ`` for a contractor, or ``NO_PERMISSIONS`` to shut someone out —
    does not open it to everyone else. A server created since gets its creator's ``MANAGE`` grant,
    so normal rules apply to it at once. Administrators are let through before this is asked.
    """
    result = effective_mcp_server_permission(name, user)
    if result.kind not in ("user", "group"):
        # With workspaces disabled there is no workspace to delegate through: only a grant on the
        # server changes it, never the global default.
        if not config.MLFLOW_ENABLE_WORKSPACES or not store.mcp_server_has_manager(name):
            return None
    return result.permission


def mcp_server_display_permission(name: str, user: str):
    """The permission to report for ``user`` on ``name`` (MLflow's ``allowed_actions``).

    The resolved permission, capped at ``USE`` where the rule for servers nobody manages keeps the
    user from changing it (see :func:`_mcp_server_write_permission`), so a UI never offers an edit
    or a delete that would be refused.
    """
    result = effective_mcp_server_permission(name, user)
    if result.permission.can_update and _mcp_server_write_permission(name, user) is None:
        return USE
    return result.permission


def can_update_mcp_server(name: str, user: str) -> bool:
    permission = _mcp_server_write_permission(name, user)
    return permission is not None and permission.can_update


def can_delete_mcp_server(name: str, user: str) -> bool:
    permission = _mcp_server_write_permission(name, user)
    return permission is not None and permission.can_delete


def can_manage_mcp_server(name: str, user: str) -> bool:
    permission = _mcp_server_write_permission(name, user)
    return permission is not None and permission.can_manage


# ---------------------------------------------------------------------------
# Core resolution loop (UNCHANGED)
# ---------------------------------------------------------------------------


# Note: PERMISSION_SOURCES_CONFIG callables return `str` (permission names like
# "READ", "MANAGE") rather than `Permission` objects. This is by design — the
# store and repository layers persist and return string permission names.
# Converting to `Permission` via `get_permission()` happens once in this
# function, keeping the builder functions simple and store-agnostic.
def get_permission_from_store_or_default(
    PERMISSION_SOURCES_CONFIG: Dict[str, Callable[[], str]],
) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources.

    This function iterates through permission sources in the order defined by
    PERMISSION_SOURCE_ORDER configuration, stopping at the first successful match.
    If no explicit permission is found, returns the default permission.

    Args:
        PERMISSION_SOURCES_CONFIG: Dictionary mapping source names to functions
                                 that retrieve permissions from those sources

    Returns:
        PermissionResult: Contains the permission and source type information

    Edge Cases:
        - Empty PERMISSION_SOURCES_CONFIG: Returns default permission with 'fallback' type
        - Invalid source in config: Logs warning and continues to next source
        - All sources fail: Returns default permission with 'fallback' type
        - MLflowException with non-RESOURCE_DOES_NOT_EXIST error: Re-raises the exception

    Note:
        The function follows the configured permission source priority order
        defined in config.PERMISSION_SOURCE_ORDER and stops at the first successful match.
    """
    return walk_sources(PERMISSION_SOURCES_CONFIG, config.PERMISSION_SOURCE_ORDER, config.DEFAULT_MLFLOW_PERMISSION, get_permission)
