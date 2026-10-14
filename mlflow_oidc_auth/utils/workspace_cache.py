"""Workspace permission cache for hot-path lookups.

Uses the pluggable CacheBackend (local TTLCache by default, Redis for
multi-replica) with lazy initialization to avoid import-time config reads.
Only active when MLFLOW_ENABLE_WORKSPACES is True.

Two caches, both keyed ``username:workspace``:

* the **grant cache** holds resolved permissions for ``WORKSPACE_CACHE_TTL_SECONDS``;
* the **denial cache** remembers "resolved, no grant" (issue #456) for at most
  ``PERMISSION_CACHE_TTL_SECONDS``.

They are separate on purpose. The workspace name comes from the client (a header, a URL, a
ListWorkspaces response), so denials can be produced for arbitrarily many names; in their own
bounded cache they can only evict other denials, never a real grant. The short TTL bounds how
long a denial cached on one replica of a local-backend deployment can outlive a grant written
through another. A lookup that hit an error is never cached in either.
"""

import re

from mlflow_oidc_auth.cache import CacheBackend, get_cache_backend
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import Permission, get_permission

logger = get_logger()

_cache: CacheBackend | None = None
_denial_cache: CacheBackend | None = None

_WORKSPACE_CACHE_DEFAULT_MAX_SIZE = 1024
_WORKSPACE_CACHE_DEFAULT_TTL = 300
_PERMISSION_CACHE_DEFAULT_TTL = 30


def _sanitize(value: str) -> str:
    """Strip control characters from a value before logging to prevent log injection."""
    return value.replace("\n", "").replace("\r", "").replace("\t", "")


def _make_cache_key(username: str, workspace: str) -> str:
    """Build a string cache key for workspace permission lookups."""
    return f"{username}:{workspace}"


def _get_cache() -> CacheBackend:
    """Get or create the workspace grant cache (lazy init). It never holds a denial."""
    global _cache
    if _cache is None:
        maxsize = getattr(config, "WORKSPACE_CACHE_MAX_SIZE", _WORKSPACE_CACHE_DEFAULT_MAX_SIZE)
        ttl = getattr(config, "WORKSPACE_CACHE_TTL_SECONDS", _WORKSPACE_CACHE_DEFAULT_TTL)
        _cache = get_cache_backend("workspace", maxsize=maxsize, ttl=ttl)
    return _cache


def _denial_ttl() -> int:
    """Denials live no longer than a cached permission decision, nor than a cached grant."""
    grant_ttl = getattr(config, "WORKSPACE_CACHE_TTL_SECONDS", _WORKSPACE_CACHE_DEFAULT_TTL)
    permission_ttl = getattr(config, "PERMISSION_CACHE_TTL_SECONDS", _PERMISSION_CACHE_DEFAULT_TTL)
    return min(grant_ttl, permission_ttl)


def _get_denial_cache() -> CacheBackend:
    """Get or create the workspace denial cache (lazy init).

    Same size bound as the grant cache but a separate store, so a flood of denials for
    made-up workspace names evicts only other denials. The Redis namespace
    ``workspace_denials`` does not share the grant namespace's ``workspace:`` prefix, so
    neither cache's prefix delete or clear reaches into the other.
    """
    global _denial_cache
    if _denial_cache is None:
        maxsize = getattr(config, "WORKSPACE_CACHE_MAX_SIZE", _WORKSPACE_CACHE_DEFAULT_MAX_SIZE)
        _denial_cache = get_cache_backend("workspace_denials", maxsize=maxsize, ttl=_denial_ttl())
    return _denial_cache


def _caches() -> tuple[CacheBackend, CacheBackend]:
    return _get_cache(), _get_denial_cache()


def get_workspace_permission_cached(username: str, workspace: str) -> Permission | None:
    """Get effective workspace permission for a user, with caching.

    Returns None if the user has no workspace permission, or if the lookup failed (fail
    closed). A grant is cached in the grant cache; a clean "no grant" in the denial cache;
    a failed lookup is not cached at all, so the next request tries again.
    Only active when MLFLOW_ENABLE_WORKSPACES is True.

    Parameters:
        username: The username to look up.
        workspace: The workspace name.

    Returns:
        Permission object or None if no permission found.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return None

    key = _make_cache_key(username, workspace)
    grants, denials = _caches()
    cached = grants.get(key)
    if cached is not None:
        return cached
    if denials.get(key) is not None:
        return None

    perm, errored = _resolve_workspace_permission(username, workspace)
    if errored:
        return None
    if perm is not None:
        grants.set(key, perm)
    else:
        denials.set(key, True)
    return perm


def invalidate_workspace_permission(username: str, workspace: str) -> None:
    """Remove a specific user+workspace entry from both caches (per D-13).

    Called by workspace permission router after successful CUD operations.
    """
    key = _make_cache_key(username, workspace)
    for cache in _caches():
        cache.delete(key)


def invalidate_user_workspace_entries(username: str) -> None:
    """Drop every cached workspace entry, grant or denial, for one user.

    Group membership drives the group-scoped branch of workspace resolution, so a
    membership change can alter this user's permission in ANY workspace — but only
    this user's. Keys are ``username:workspace``, so a prefix delete is exact and
    bounded, and leaves every other user's entries warm.

    This matters for throughput as well as correctness: OIDC login re-syncs group
    membership on every sign-in, so a full flush here would wipe the cache fleet-wide
    on each login.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        # Nothing is ever cached with workspaces off, so skip the work entirely —
        # otherwise every login pays a Redis keyspace SCAN for no benefit. Mirrors
        # the guard in get_workspace_permission_cached.
        return
    for cache in _caches():
        cache.delete_prefix(f"{username}:")
    logger.debug("Workspace cache entries invalidated for user %s", _sanitize(username))


def invalidate_group_workspace_permission(group_name: str, workspace: str) -> None:
    """Drop the cached entry for ``workspace`` for every member of ``group_name``.

    A group-scoped workspace permission change affects exactly the group's members in
    that one workspace, so invalidating per member is exact and costs one bounded
    query. Previously these changes invalidated nothing and relied on TTL expiry
    (decision D-15), which left revoked access working for up to the cache TTL.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        # Nothing is cached with workspaces off — skip, and in particular skip the
        # get_group_users lookup, which would otherwise be a wasted query per mutation.
        return

    from mlflow_oidc_auth.store import store

    try:
        members = store.get_group_users(group_name)
    except Exception:
        # Never let an invalidation failure mask the successful mutation — but do not
        # leave stale authorization behind either: fall back to a full flush.
        logger.warning(
            "Could not list members of group %s for targeted workspace-cache invalidation; flushing instead",
            _sanitize(group_name),
        )
        flush_workspace_cache()
        return

    caches = _caches()
    for member in members:
        key = _make_cache_key(member.username, workspace)
        for cache in caches:
            cache.delete(key)
    logger.debug(
        "Workspace cache invalidated for %d member(s) of group %s in workspace %s",
        len(members),
        _sanitize(group_name),
        _sanitize(workspace),
    )


def flush_workspace_cache() -> None:
    """Flush both workspace caches (per D-09).

    Called by workspace regex permission router after any CUD operation.
    Full flush is necessary because regex changes can affect any user+workspace combo.
    """
    for cache in _caches():
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


def _record_error(errors: list | None, source: str) -> None:
    """Note that ``source`` failed, as opposed to finding no grant."""
    if errors is not None:
        errors.append(source)


def _is_not_found(error: Exception) -> bool:
    """Whether ``error`` is the store saying "no such row" — no grant, not a failure."""
    from mlflow.exceptions import MlflowException

    return isinstance(error, MlflowException) and error.error_code == "RESOURCE_DOES_NOT_EXIST"


def _resolve_user_direct(store, username: str, workspace: str, errors: list | None = None) -> Permission | None:
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
            _record_error(errors, "user-direct")
        return None
    except Exception as e:
        logger.warning(
            "Unexpected error resolving user-direct workspace permission for %s@%s: %s",
            _sanitize(username),
            _sanitize(workspace),
            e,
        )
        _record_error(errors, "user-direct")
        return None


def _resolve_group_direct(store, username: str, workspace: str, errors: list | None = None) -> Permission | None:
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
            _record_error(errors, "group-direct")
        return None
    except Exception as e:
        logger.warning(
            "Unexpected error resolving group-direct workspace permission for %s@%s: %s",
            _sanitize(username),
            _sanitize(workspace),
            e,
        )
        _record_error(errors, "group-direct")
        return None


def _resolve_user_regex(store, username: str, workspace: str, errors: list | None = None) -> Permission | None:
    """Resolve user-regex workspace permission.

    Lists user's regex permissions (sorted by priority) and matches against workspace name.
    """
    try:
        regexes = store.list_workspace_regex_permissions(username)
        if not regexes:
            return None
        return _match_workspace_regex_permission(regexes, workspace)
    except Exception as e:
        if _is_not_found(e):
            return None
        logger.warning(
            "Error resolving user-regex workspace permission for %s@%s: %s",
            _sanitize(username),
            _sanitize(workspace),
            e,
        )
        _record_error(errors, "user-regex")
        return None


def _resolve_group_regex(store, username: str, workspace: str, errors: list | None = None) -> Permission | None:
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
        if _is_not_found(e):
            return None
        logger.warning(
            "Error resolving group-regex workspace permission for %s@%s: %s",
            _sanitize(username),
            _sanitize(workspace),
            e,
        )
        _record_error(errors, "group-regex")
        return None


def _lookup_workspace_permission(username: str, workspace: str) -> Permission | None:
    """Look up workspace permission from DB using configured source resolution order.

    Per D-03: Resolution order respects PERMISSION_SOURCE_ORDER config.
    Per D-04: First match wins (short-circuit).
    Per D-05: Not hardcoded — configurable.

    A failed lookup returns None (fail closed); use :func:`_resolve_workspace_permission`
    to tell a failure from "no grant".

    Parameters:
        username: The username to look up.
        workspace: The workspace name.

    Returns:
        Permission object or None if no permission found or the lookup failed.
    """
    return _resolve_workspace_permission(username, workspace)[0]


def _resolve_workspace_permission(username: str, workspace: str) -> tuple[Permission | None, bool]:
    """Resolve a workspace permission, reporting whether any source failed.

    A source that errors before a match makes the answer unknown: a lower-priority source's
    grant may be wider than what the failed source holds, so the walk is denied (fail closed)
    rather than falling through to it.

    Parameters:
        username: The username to look up.
        workspace: The workspace name.

    Returns:
        ``(permission, errored)``. ``errored`` True means the result must not be cached;
        the permission is then always None.
    """
    from mlflow_oidc_auth.store import store  # Lazy import to avoid circular dependency

    logger.debug(
        "Looking up workspace permission for %s@%s",
        _sanitize(username),
        _sanitize(workspace),
    )

    # Build source resolution functions keyed by source name
    errors: list[str] = []
    source_resolvers = {
        "user": lambda: _resolve_user_direct(store, username, workspace, errors),
        "group": lambda: _resolve_group_direct(store, username, workspace, errors),
        "regex": lambda: _resolve_user_regex(store, username, workspace, errors),
        "group-regex": lambda: _resolve_group_regex(store, username, workspace, errors),
    }

    logger.debug("Source order: %s", config.PERMISSION_SOURCE_ORDER)

    for source_name in config.PERMISSION_SOURCE_ORDER:
        resolver = source_resolvers.get(source_name)
        if resolver is None:
            logger.warning("Invalid workspace permission source: %s", source_name)
            continue
        result = resolver()
        if errors:
            logger.warning(
                "Workspace permission lookup for %s@%s failed in source(s) %s; denying without caching",
                _sanitize(username),
                _sanitize(workspace),
                ", ".join(errors),
            )
            return None, True
        if result is not None:
            logger.debug(
                "Workspace permission found via source '%s' for %s@%s: %s",
                source_name,
                _sanitize(username),
                _sanitize(workspace),
                result,
            )
            return result, False
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
    return None, False
