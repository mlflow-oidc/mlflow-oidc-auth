"""Workspace permission cache for hot-path lookups.

Uses cachetools.TTLCache with lazy initialization to avoid import-time config reads.
Only active when MLFLOW_ENABLE_WORKSPACES is True.
"""

from cachetools import TTLCache

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import MANAGE, Permission, get_permission

logger = get_logger()

_cache: TTLCache | None = None


def _get_cache() -> TTLCache:
    """Get or create the workspace permission cache (lazy init)."""
    global _cache
    if _cache is None:
        _cache = TTLCache(
            maxsize=config.WORKSPACE_CACHE_MAX_SIZE,
            ttl=config.WORKSPACE_CACHE_TTL_SECONDS,
        )
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
    key = (username, workspace)
    if key in cache:
        return cache[key]

    perm = _lookup_workspace_permission(username, workspace)
    if perm is not None:
        cache[key] = perm  # Only cache non-None to avoid caching denials
    return perm


def invalidate_workspace_permission(username: str, workspace: str) -> None:
    """Remove a specific user+workspace entry from cache (per D-13).

    Called by workspace permission router after successful CUD operations.
    Only invalidates user permission changes; group changes rely on TTL (per D-15).
    """
    cache = _get_cache()
    cache.pop((username, workspace), None)


def flush_workspace_cache() -> None:
    """Flush entire workspace permission cache (per D-09).

    Called by workspace regex permission router after any CUD operation.
    Full flush is necessary because regex changes can affect any user+workspace combo.
    """
    cache = _get_cache()
    cache.clear()
    logger.debug("Workspace permission cache fully flushed (regex CUD)")


def _lookup_workspace_permission(username: str, workspace: str) -> Permission | None:
    """Look up workspace permission from DB, with implicit default workspace access.

    Parameters:
        username: The username to look up.
        workspace: The workspace name.

    Returns:
        Permission object or None if no permission found.
    """
    from mlflow_oidc_auth.store import store  # Lazy import to avoid circular dependency

    # Implicit access to default workspace (per decision WSAUTH-D)
    if workspace == "default" and config.GRANT_DEFAULT_WORKSPACE_ACCESS:
        return MANAGE

    # User-level workspace permission
    try:
        perm = store.get_workspace_permission(workspace, username)
        return get_permission(perm.permission)
    except Exception:
        pass

    # Group-level workspace permission (highest across user's groups)
    try:
        perm = store.get_user_groups_workspace_permission(workspace, username)
        return get_permission(perm.permission)
    except Exception:
        pass

    return None
