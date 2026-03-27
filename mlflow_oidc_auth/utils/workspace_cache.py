"""Workspace permission cache for hot-path lookups.

Uses the pluggable CacheBackend (local TTLCache by default, Redis for
multi-replica) with lazy initialization to avoid import-time config reads.
Only active when MLFLOW_ENABLE_WORKSPACES is True.
"""

import re

from mlflow_oidc_auth.cache import CacheBackend, get_cache_backend
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import MANAGE, Permission, get_permission

logger = get_logger()

_cache: CacheBackend | None = None

_WORKSPACE_CACHE_DEFAULT_MAX_SIZE = 1024
_WORKSPACE_CACHE_DEFAULT_TTL = 300


def _sanitize(value: str) -> str:
    """Strip control characters from a value before logging to prevent log injection."""
    return value.replace("\n", "").replace("\r", "").replace("\t", "")


def _make_cache_key(username: str, workspace: str) -> str:
    """Build a string cache key for workspace permission lookups."""
    return f"{username}:{workspace}"


def _get_cache() -> CacheBackend:
    """Get or create the workspace permission cache (lazy init)."""
    global _cache
    if _cache is None:
        maxsize = getattr(
            config, "WORKSPACE_CACHE_MAX_SIZE", _WORKSPACE_CACHE_DEFAULT_MAX_SIZE
        )
        ttl = getattr(
            config, "WORKSPACE_CACHE_TTL_SECONDS", _WORKSPACE_CACHE_DEFAULT_TTL
        )
        _cache = get_cache_backend("workspace", maxsize=maxsize, ttl=ttl)
    return _cache


def get_workspace_permission_cached(username: str, workspace: str) -> Permission | None:
    """Get effective workspace permission for a user, with caching.

    Returns None if the user has no workspace permission.
    Only active when MLFLOW_ENABLE_WORKSPACES is True.

    Parameters:
        username: The username to look up.
        workspace: The workspace name.

    Returns:
        Permission object or None if no permission found.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return None

    cache = _get_cache()
    key = _make_cache_key(username, workspace)
    cached = cache.get(key)
    if cached is not None:
        return cached

    perm = _lookup_workspace_permission(username, workspace)
    if perm is not None:
        cache.set(key, perm)  # Only cache non-None to avoid caching denials
    return perm


def invalidate_workspace_permission(username: str, workspace: str) -> None:
    """Remove a specific user+workspace entry from cache (per D-13).

    Called by workspace permission router after successful CUD operations.
    Only invalidates user permission changes; group changes rely on TTL (per D-15).
    """
    cache = _get_cache()
    cache.delete(_make_cache_key(username, workspace))


def flush_workspace_cache() -> None:
    """Flush entire workspace permission cache (per D-09).

    Called by workspace regex permission router after any CUD operation.
    Full flush is necessary because regex changes can affect any user+workspace combo.
    """
    cache = _get_cache()
    cache.clear()
    logger.debug("Workspace permission cache fully flushed (regex CUD)")


def _match_workspace_regex_permission(regexes, workspace: str) -> Permission | None:
    """Match workspace name against sorted regex permissions.

    Per D-07: regexes are sorted by priority (lower number = higher priority).
    Per D-04: first match wins (short-circuit).
    Per D-08: when multiple regexes match at the same priority, return most permissive.

    Parameters:
        regexes: List of regex permission entities, sorted by priority ascending.
        workspace: The workspace name to match against.

    Returns:
        Permission object or None if no regex matches.
    """
    best_perm = None
    best_priority = None

    for regex_perm in regexes:
        # If we already found a match at a higher priority (lower number), stop
        if best_priority is not None and regex_perm.priority > best_priority:
            break

        if re.match(regex_perm.regex, workspace):
            perm = get_permission(regex_perm.permission)
            if best_perm is None:
                best_perm = perm
                best_priority = regex_perm.priority
            elif perm.priority > best_perm.priority:
                # Same priority tier, more permissive wins (D-08)
                best_perm = perm

    return best_perm


def _resolve_user_direct(store, username: str, workspace: str) -> Permission | None:
    """Resolve user-direct workspace permission."""
    from mlflow.exceptions import MlflowException

    try:
        perm = store.get_workspace_permission(workspace, username)
        return get_permission(perm.permission)
    except MlflowException as e:
        if e.error_code == "RESOURCE_DOES_NOT_EXIST":
            logger.debug(
                "No user-direct workspace permission for %s@%s",
                _sanitize(username),
                _sanitize(workspace),
            )
        else:
            logger.warning(
                "Unexpected MlflowException resolving user-direct workspace permission for %s@%s: %s",
                _sanitize(username),
                _sanitize(workspace),
                e,
            )
        return None
    except Exception as e:
        logger.warning(
            "Unexpected error resolving user-direct workspace permission for %s@%s: %s",
            _sanitize(username),
            _sanitize(workspace),
            e,
        )
        return None


def _resolve_group_direct(store, username: str, workspace: str) -> Permission | None:
    """Resolve group-direct workspace permission (highest across user's groups)."""
    from mlflow.exceptions import MlflowException

    try:
        perm = store.get_user_groups_workspace_permission(workspace, username)
        return get_permission(perm.permission)
    except MlflowException as e:
        if e.error_code == "RESOURCE_DOES_NOT_EXIST":
            logger.debug(
                "No group-direct workspace permission for %s@%s",
                _sanitize(username),
                _sanitize(workspace),
            )
        else:
            logger.warning(
                "Unexpected MlflowException resolving group-direct workspace permission for %s@%s: %s",
                _sanitize(username),
                _sanitize(workspace),
                e,
            )
        return None
    except Exception as e:
        logger.warning(
            "Unexpected error resolving group-direct workspace permission for %s@%s: %s",
            _sanitize(username),
            _sanitize(workspace),
            e,
        )
        return None


def _resolve_user_regex(store, username: str, workspace: str) -> Permission | None:
    """Resolve user-regex workspace permission.

    Lists user's regex permissions (sorted by priority) and matches against workspace name.
    """
    try:
        regexes = store.list_workspace_regex_permissions(username)
        if not regexes:
            return None
        return _match_workspace_regex_permission(regexes, workspace)
    except Exception as e:
        logger.warning(
            "Error resolving user-regex workspace permission for %s@%s: %s",
            _sanitize(username),
            _sanitize(workspace),
            e,
        )
        return None


def _resolve_group_regex(store, username: str, workspace: str) -> Permission | None:
    """Resolve group-regex workspace permission.

    Gets user's group IDs, lists all group regex permissions for those groups,
    and matches against workspace name.
    """
    try:
        group_ids = store.get_groups_ids_for_user(username)
        if not group_ids:
            return None
        regexes = store.list_workspace_group_regex_permissions_for_groups_ids(group_ids)
        if not regexes:
            return None
        return _match_workspace_regex_permission(regexes, workspace)
    except Exception as e:
        logger.warning(
            "Error resolving group-regex workspace permission for %s@%s: %s",
            _sanitize(username),
            _sanitize(workspace),
            e,
        )
        return None


def _lookup_workspace_permission(username: str, workspace: str) -> Permission | None:
    """Look up workspace permission from DB using configured source resolution order.

    Per D-03: Resolution order respects PERMISSION_SOURCE_ORDER config.
    Per D-04: First match wins (short-circuit).
    Per D-05: Not hardcoded — configurable.

    Parameters:
        username: The username to look up.
        workspace: The workspace name.

    Returns:
        Permission object or None if no permission found.
    """
    from mlflow_oidc_auth.store import store  # Lazy import to avoid circular dependency

    logger.debug(
        "Looking up workspace permission for %s@%s",
        _sanitize(username),
        _sanitize(workspace),
    )

    # Build source resolution functions keyed by source name
    source_resolvers = {
        "user": lambda: _resolve_user_direct(store, username, workspace),
        "group": lambda: _resolve_group_direct(store, username, workspace),
        "regex": lambda: _resolve_user_regex(store, username, workspace),
        "group-regex": lambda: _resolve_group_regex(store, username, workspace),
    }

    logger.debug("Source order: %s", config.PERMISSION_SOURCE_ORDER)

    for source_name in config.PERMISSION_SOURCE_ORDER:
        resolver = source_resolvers.get(source_name)
        if resolver is None:
            logger.warning("Invalid workspace permission source: %s", source_name)
            continue
        result = resolver()
        if result is not None:
            logger.debug(
                "Workspace permission found via source '%s' for %s@%s: %s",
                source_name,
                _sanitize(username),
                _sanitize(workspace),
                result,
            )
            return result
        logger.debug(
            "Source '%s' returned None for %s@%s",
            source_name,
            _sanitize(username),
            _sanitize(workspace),
        )

    logger.warning(
        "No workspace permission found for %s@%s after checking all sources",
        _sanitize(username),
        _sanitize(workspace),
    )
    return None
