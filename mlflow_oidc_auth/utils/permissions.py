"""
Permission resolution utilities for MLflow OIDC Auth.

This module provides registry-driven permission resolution for all 7 resource types.
The PERMISSION_REGISTRY maps resource types to builder functions that create
source configurations, and resolve_permission() is the single entry point.

A pluggable cache backend is used to avoid repeated DB lookups on every request.
Cache entries are keyed by ``resource_type:resource_id:username`` and expire
after PERMISSION_CACHE_TTL_SECONDS (default 30). The backend is selected via
``CACHE_BACKEND`` config (``"local"`` or ``"redis"``).

Explicit invalidation is available via invalidate_permission_cache() and
flush_permission_cache().

Existing public functions (effective_*, can_*) are thin wrappers around
resolve_permission() and remain backward-compatible.
"""

import re
from typing import Callable, Dict

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.cache import CacheBackend, get_cache_backend
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import PermissionResult
from mlflow_oidc_auth.permissions import NO_PERMISSIONS, get_permission
from mlflow_oidc_auth.store import store

logger = get_logger()

# ---------------------------------------------------------------------------
# Permission cache (lazy init to avoid import-time config reads)
# ---------------------------------------------------------------------------

_PERMISSION_CACHE_MAX_SIZE = 2048
_PERMISSION_CACHE_DEFAULT_TTL = 30

_permission_cache: CacheBackend | None = None


def _get_permission_cache() -> CacheBackend:
    """Get or create the permission resolution cache (lazy init)."""
    global _permission_cache
    if _permission_cache is None:
        ttl = getattr(config, "PERMISSION_CACHE_TTL_SECONDS", _PERMISSION_CACHE_DEFAULT_TTL)
        _permission_cache = get_cache_backend("permissions", maxsize=_PERMISSION_CACHE_MAX_SIZE, ttl=ttl)
    return _permission_cache


# Distinguishes "no workspace context on this request" from a workspace literally named
# after it. Cannot collide with a real name: MLflow's WorkspaceNameValidator rejects ":".
_NO_WORKSPACE_CACHE_MARKER = "::no-workspace"


def _get_cache_workspace(workspace: str | None = None) -> str | None:
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

    if workspace is None:
        from mlflow_oidc_auth.bridge.user import get_request_workspace

        workspace = get_request_workspace()

    # None also covers resolution outside a request context, which likewise skips the
    # workspace branch below and so belongs in the same bucket.
    return workspace or _NO_WORKSPACE_CACHE_MARKER


def _make_cache_key(resource_type: str, resource_id: str, username: str, workspace: str | None = None) -> str:
    """Build a string cache key from the permission lookup tuple.

    The workspace is part of the key whenever workspaces are enabled: the same
    resource id denotes different entities in different workspaces, and a result
    may itself be workspace-derived, so a workspace-blind key would serve one
    tenant's decision to another for the lifetime of the entry.
    """
    if workspace is not None:
        return f"{workspace}:{resource_type}:{resource_id}:{username}"
    return f"{resource_type}:{resource_id}:{username}"


def invalidate_permission_cache(resource_type: str, resource_id: str, username: str, workspace: str | None = None) -> None:
    """Remove a specific permission entry from cache.

    Call after permission CUD operations for a specific user+resource. When
    workspaces are enabled, pass the workspace the entry was cached under;
    omitting it falls back to the workspace of the current request.
    """
    cache = _get_permission_cache()
    if workspace is None:
        workspace = _get_cache_workspace()
    cache.delete(_make_cache_key(resource_type, resource_id, username, workspace))


def flush_permission_cache() -> None:
    """Flush entire permission cache.

    Call after bulk operations (e.g., regex permission changes) that
    may affect many user+resource combos.
    """
    cache = _get_permission_cache()
    cache.clear()
    logger.debug("Permission cache fully flushed")


# Resource type constants
EXPERIMENT = "experiment"
REGISTERED_MODEL = "registered_model"
PROMPT = "prompt"
SCORER = "scorer"
GATEWAY_ENDPOINT = "gateway_endpoint"
GATEWAY_SECRET = "gateway_secret"
GATEWAY_MODEL_DEFINITION = "gateway_model_definition"


# ---------------------------------------------------------------------------
# Generic regex matcher (replaces 10+ near-identical functions)
# ---------------------------------------------------------------------------


def _match_regex_permission(regexes, name: str, label: str) -> str:
    """Generic regex matcher for any resource type. Replaces 8 near-identical functions."""
    for regex in regexes:
        if re.match(regex.regex, name):
            logger.debug(f"Regex permission found for {label} {name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}")
            return regex.permission
    raise MlflowException(f"{label} {name}", error_code=RESOURCE_DOES_NOT_EXIST)


# ---------------------------------------------------------------------------
# Experiment-specific regex wrappers (experiment_id → experiment_name lookup)
# ---------------------------------------------------------------------------


def _get_experiment_permission_from_regex(regexes, experiment_id: str) -> str:
    experiment_name = _get_tracking_store().get_experiment(experiment_id).name
    return _match_regex_permission(regexes, experiment_name, "experiment")


def _get_experiment_group_permission_from_regex(regexes, experiment_id: str) -> str:
    experiment_name = _get_tracking_store().get_experiment(experiment_id).name
    return _match_regex_permission(regexes, experiment_name, "experiment")


# ---------------------------------------------------------------------------
# Builder functions — one per resource type
# ---------------------------------------------------------------------------


def _build_experiment_sources(experiment_id: str, username: str, **kwargs) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda experiment_id=experiment_id, user=username: store.get_experiment_permission(experiment_id, user).permission,
        "group": lambda experiment_id=experiment_id, user=username: store.get_user_groups_experiment_permission(experiment_id, user).permission,
        "regex": lambda experiment_id=experiment_id, user=username: _get_experiment_permission_from_regex(
            store.list_experiment_regex_permissions(user), experiment_id
        ),
        "group-regex": lambda experiment_id=experiment_id, user=username: _get_experiment_group_permission_from_regex(
            store.list_group_experiment_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            experiment_id,
        ),
    }


def _build_registered_model_sources(model_name: str, username: str, **kwargs) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda model_name=model_name, user=username: store.get_registered_model_permission(model_name, user).permission,
        "group": lambda model_name=model_name, user=username: store.get_user_groups_registered_model_permission(model_name, user).permission,
        "regex": lambda model_name=model_name, user=username: _match_regex_permission(
            store.list_registered_model_regex_permissions(user),
            model_name,
            "model name",
        ),
        "group-regex": lambda model_name=model_name, user=username: _match_regex_permission(
            store.list_group_registered_model_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            model_name,
            "model name",
        ),
    }


def _build_prompt_sources(model_name: str, username: str, **kwargs) -> Dict[str, Callable[[], str]]:
    """Build prompt permission sources.

    CRITICAL: user/group sources map to store.get_registered_model_permission and
    store.get_user_groups_registered_model_permission (NOT prompt-specific methods).
    Regex sources use prompt-specific store methods. This is intentional — preserved
    from the original implementation.
    """
    return {
        "user": lambda model_name=model_name, user=username: store.get_registered_model_permission(model_name, user).permission,
        "group": lambda model_name=model_name, user=username: store.get_user_groups_registered_model_permission(model_name, user).permission,
        "regex": lambda model_name=model_name, user=username: _match_regex_permission(store.list_prompt_regex_permissions(user), model_name, "model name"),
        "group-regex": lambda model_name=model_name, user=username: _match_regex_permission(
            store.list_group_prompt_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            model_name,
            "model name",
        ),
    }


def _build_scorer_sources(experiment_id: str, username: str, **kwargs) -> Dict[str, Callable[[], str]]:
    scorer_name = kwargs["scorer_name"]
    return {
        "user": lambda experiment_id=experiment_id, scorer_name=scorer_name, user=username: store.get_scorer_permission(
            experiment_id, scorer_name, user
        ).permission,
        "group": lambda experiment_id=experiment_id, scorer_name=scorer_name, user=username: store.get_user_groups_scorer_permission(
            experiment_id, scorer_name, user
        ).permission,
        "regex": lambda scorer_name=scorer_name, user=username: _match_regex_permission(store.list_scorer_regex_permissions(user), scorer_name, "scorer name"),
        "group-regex": lambda scorer_name=scorer_name, user=username: _match_regex_permission(
            store.list_group_scorer_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            scorer_name,
            "scorer name",
        ),
    }


def _build_gateway_endpoint_sources(gateway_name: str, username: str, **kwargs) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda gateway_name=gateway_name, user=username: store.get_gateway_endpoint_permission(gateway_name, user).permission,
        "group": lambda gateway_name=gateway_name, user=username: store.get_user_groups_gateway_endpoint_permission(gateway_name, user).permission,
        "regex": lambda gateway_name=gateway_name, user=username: _match_regex_permission(
            store.list_gateway_endpoint_regex_permissions(user),
            gateway_name,
            "gateway name",
        ),
        "group-regex": lambda gateway_name=gateway_name, user=username: _match_regex_permission(
            store.list_group_gateway_endpoint_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            gateway_name,
            "gateway name",
        ),
    }


def _build_gateway_secret_sources(gateway_name: str, username: str, **kwargs) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda gateway_name=gateway_name, user=username: store.get_gateway_secret_permission(gateway_name, user).permission,
        "group": lambda gateway_name=gateway_name, user=username: store.get_user_groups_gateway_secret_permission(gateway_name, user).permission,
        "regex": lambda gateway_name=gateway_name, user=username: _match_regex_permission(
            store.list_gateway_secret_regex_permissions(user),
            gateway_name,
            "gateway name",
        ),
        "group-regex": lambda gateway_name=gateway_name, user=username: _match_regex_permission(
            store.list_group_gateway_secret_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            gateway_name,
            "gateway name",
        ),
    }


def _build_gateway_model_definition_sources(gateway_name: str, username: str, **kwargs) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda gateway_name=gateway_name, user=username: store.get_gateway_model_definition_permission(gateway_name, user).permission,
        "group": lambda gateway_name=gateway_name, user=username: store.get_user_groups_gateway_model_definition_permission(gateway_name, user).permission,
        "regex": lambda gateway_name=gateway_name, user=username: _match_regex_permission(
            store.list_gateway_model_definition_regex_permissions(user),
            gateway_name,
            "gateway name",
        ),
        "group-regex": lambda gateway_name=gateway_name, user=username: _match_regex_permission(
            store.list_group_gateway_model_definition_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            gateway_name,
            "gateway name",
        ),
    }


# ---------------------------------------------------------------------------
# Permission Registry and resolve_permission()
# ---------------------------------------------------------------------------


PERMISSION_REGISTRY: Dict[str, Callable[..., Dict[str, Callable[[], str]]]] = {
    EXPERIMENT: _build_experiment_sources,
    REGISTERED_MODEL: _build_registered_model_sources,
    PROMPT: _build_prompt_sources,
    SCORER: _build_scorer_sources,
    GATEWAY_ENDPOINT: _build_gateway_endpoint_sources,
    GATEWAY_SECRET: _build_gateway_secret_sources,
    GATEWAY_MODEL_DEFINITION: _build_gateway_model_definition_sources,
}


def _apply_workspace_fallback(result: PermissionResult, username: str, workspace: str | None = None) -> PermissionResult:
    """Defer a generic ``fallback`` result to the user's workspace permission.

    Per WSAUTH-C/WSAUTH-04: when workspaces are enabled and no resource-level
    permission was found, use the user's permission on the request workspace
    instead of the global default; if the user has no workspace permission,
    deny with ``NO_PERMISSIONS`` (kind ``workspace-deny``). A header-less request
    (no workspace) is left unchanged so the global default still applies.

    Shared by resolve_permission and the creation resolvers so both paths agree.
    """
    if result.kind != "fallback" or not config.MLFLOW_ENABLE_WORKSPACES:
        return result

    from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached

    if workspace is None:
        from mlflow_oidc_auth.bridge.user import get_request_workspace

        workspace = get_request_workspace()
    if not workspace:
        return result
    ws_perm = get_workspace_permission_cached(username, workspace)
    if ws_perm is not None:
        return PermissionResult(ws_perm, "workspace")
    return PermissionResult(NO_PERMISSIONS, "workspace-deny")


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

    The shipped default is ``MANAGE``, so on a fresh install this is the granting case for
    every resource, which is exactly the exposure operators should be able to see before
    the default changes (issue #293). Only the granting case warns; both cases are counted
    and logged at debug.

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

    logger.debug("Permission fallback: %s granted %s to %s (occurrence %d)", resource_type, permission.name, username, count)

    if not permission.can_read:
        # A fallback that grants nothing is the safe, expected shape.
        return

    if count in _FALLBACK_WARN_AT or count % _FALLBACK_WARN_EVERY == 0:
        logger.warning(
            f"DEFAULT_MLFLOW_PERMISSION granted {permission.name} on a {resource_type} to {username} "
            f"because no explicit permission exists ({count} such grants for {resource_type} so far). "
            "Access is coming from configuration rather than a permission record. "
            "Call get_permission_fallback_samples() for the affected resource ids, or enable DEBUG logging. "
            "See issue #293: this default is changing to NO_PERMISSIONS in a future major version."
        )


def resolve_permission(resource_type: str, resource_id: str, username: str, workspace: str | None = None, **kwargs) -> PermissionResult:
    """Single entry point for all permission resolution. Per D-01 (REFAC-01).

    Results are cached with a short TTL to avoid repeated DB lookups on every
    request. Workspace-enabled lookups include the workspace in the cache key.
    """
    cache = _get_permission_cache()
    cache_key = _make_cache_key(resource_type, resource_id, username, _get_cache_workspace(workspace))

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    builder = PERMISSION_REGISTRY[resource_type]
    sources_config = builder(resource_id, username, **kwargs)
    result = get_permission_from_store_or_default(sources_config)
    result = _apply_workspace_fallback(result, username, workspace) if workspace is not None else _apply_workspace_fallback(result, username)

    # Recorded here rather than where the fallback is constructed, because this is the
    # only layer that knows WHICH resource and user it was for. Checked after the
    # workspace fallback, which may already have replaced it with a real decision.
    if result.kind == "fallback":
        record_permission_fallback(resource_type, resource_id, username, result.permission)

    cache.set(cache_key, result)
    return result


# ---------------------------------------------------------------------------
# Public API — thin wrappers
# ---------------------------------------------------------------------------


def effective_experiment_permission(experiment_id: str, user: str, workspace: str | None = None) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return resolve_permission(EXPERIMENT, experiment_id, user, workspace=workspace)


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


def effective_prompt_permission(prompt_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return resolve_permission(PROMPT, prompt_name, user)


def effective_scorer_permission(experiment_id: str, scorer_name: str, user: str) -> PermissionResult:
    """Resolve effective permission for a scorer.

    This mirrors the behavior of `effective_experiment_permission` / `effective_registered_model_permission`
    but uses scorer-specific permission sources.
    """
    return resolve_permission(SCORER, experiment_id, user, scorer_name=scorer_name)


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
    for source_name in config.PERMISSION_SOURCE_ORDER:
        if source_name in PERMISSION_SOURCES_CONFIG:
            try:
                # Get the permission retrieval function from the configuration
                permission_func = PERMISSION_SOURCES_CONFIG[source_name]
                # Call the function to get the permission
                perm = permission_func()
                logger.debug(f"Permission found using source: {source_name}")
                return PermissionResult(get_permission(perm), source_name)
            except MlflowException as e:
                if e.error_code != ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
                    raise  # Re-raise exceptions other than RESOURCE_DOES_NOT_EXIST
                logger.debug(f"Permission not found using source {source_name}: {e}")
        else:
            logger.warning(f"Invalid permission source configured: {source_name}")

    # If no permission is found, use the default
    perm = config.DEFAULT_MLFLOW_PERMISSION
    logger.debug("Default permission used")
    return PermissionResult(get_permission(perm), "fallback")
