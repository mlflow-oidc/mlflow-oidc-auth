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

import uuid
from urllib.parse import quote

from mlflow_oidc_auth.cache import CacheBackend, get_cache_backend
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import Permission
from mlflow_oidc_auth.utils.grant_context import match_workspace_pattern, resolve_workspace_permission

logger = get_logger()

_cache: CacheBackend | None = None
_denial_cache: CacheBackend | None = None
_generation_cache: CacheBackend | None = None

# The one key of the generation cache. Invalidation stores a fresh random value under it.
_GENERATION_KEY = "generation"
# How long a generation value is kept. A lookup is only fooled if a value is written and then
# expires within the few milliseconds of one lookup, so this only has to be long.
_GENERATION_MIN_TTL = 3600

_WORKSPACE_CACHE_DEFAULT_MAX_SIZE = 1024
_WORKSPACE_CACHE_DEFAULT_TTL = 300
_PERMISSION_CACHE_DEFAULT_TTL = 30


def _sanitize(value: str) -> str:
    """Strip control characters from a value before logging to prevent log injection."""
    return value.replace("\n", "").replace("\r", "").replace("\t", "")


def _key_part(value: str) -> str:
    """Percent-encode one key component. ``:`` and ``%`` never survive unencoded."""
    return quote(value, safe="")


def _make_cache_key(username: str, workspace: str) -> str:
    """Build a collision-free ``username:workspace`` cache key.

    Both parts are percent-encoded, so the only literal ``:`` is the separator: user ``a``
    in workspace ``b:c`` and user ``a:b`` in workspace ``c`` get different keys.
    """
    return f"{_key_part(username)}:{_key_part(workspace)}"


def _user_key_prefix(username: str) -> str:
    """The key prefix of every entry of ``username``, and of no other user."""
    return f"{_key_part(username)}:"


def _get_cache() -> CacheBackend:
    """Get or create the workspace grant cache (lazy init). It never holds a denial."""
    global _cache
    if _cache is None:
        maxsize = getattr(config, "WORKSPACE_CACHE_MAX_SIZE", _WORKSPACE_CACHE_DEFAULT_MAX_SIZE)
        ttl = getattr(config, "WORKSPACE_CACHE_TTL_SECONDS", _WORKSPACE_CACHE_DEFAULT_TTL)
        # "_v2": keys became percent-encoded in #456, so new replicas never read old-format keys.
        _cache = get_cache_backend("workspace_v2", maxsize=maxsize, ttl=ttl)
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
    ``workspace_denials`` does not share the grant namespace's ``workspace_v2:`` prefix, so
    neither cache's prefix delete or clear reaches into the other.
    """
    global _denial_cache
    if _denial_cache is None:
        maxsize = getattr(config, "WORKSPACE_CACHE_MAX_SIZE", _WORKSPACE_CACHE_DEFAULT_MAX_SIZE)
        _denial_cache = get_cache_backend("workspace_denials", maxsize=maxsize, ttl=_denial_ttl())
    return _denial_cache


def _caches() -> tuple[CacheBackend, CacheBackend]:
    return _get_cache(), _get_denial_cache()


def _get_generation_cache() -> CacheBackend:
    """Get or create the one-entry cache holding the invalidation generation (lazy init).

    Its own store, so no flood of other entries can evict the generation. On Redis it is
    shared, so an invalidation on any replica is seen by a lookup on every replica.
    """
    global _generation_cache
    if _generation_cache is None:
        ttl = max(getattr(config, "WORKSPACE_CACHE_TTL_SECONDS", _WORKSPACE_CACHE_DEFAULT_TTL), _GENERATION_MIN_TTL)
        _generation_cache = get_cache_backend("workspace_generation", maxsize=1, ttl=ttl)
    return _generation_cache


def _current_generation():
    return _get_generation_cache().get(_GENERATION_KEY)


def _bump_generation() -> None:
    """Record that an invalidation is happening. Invalidations call it BEFORE and AFTER their deletes.

    The bump before means a lookup that checks the generation after writing its entry sees
    the move whenever the delete could still be pending; the bump after means a lookup that
    read the generation before the delete sees it too. A random value rather than a
    counter: any change is detected, and no atomic increment is needed on either backend.
    """
    _get_generation_cache().set(_GENERATION_KEY, uuid.uuid4().hex)


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

    # An invalidation that runs while this lookup is in flight may delete the key before we
    # write it, so the result could be stale (a denial read just before a grant was committed,
    # or a grant read just before a revoke). Invalidations bump the generation before and
    # after their deletes, so:
    # - moved before the write: answer this request but cache nothing;
    # - moved after the write: delete what we wrote. An invalidation that bumps only after
    #   this last check also deletes only after it, so it removes our entry itself.
    generation = _current_generation()
    perm, errored = _resolve_workspace_permission(username, workspace)
    if errored:
        return None
    if _current_generation() != generation:
        return perm
    target = grants if perm is not None else denials
    target.set(key, perm if perm is not None else True)
    if _current_generation() != generation:
        target.delete(key)
    return perm


def invalidate_workspace_permission(username: str, workspace: str) -> None:
    """Remove a specific user+workspace entry from both caches (per D-13).

    Called by workspace permission router after successful CUD operations.
    """
    key = _make_cache_key(username, workspace)
    _bump_generation()
    for cache in _caches():
        cache.delete(key)
    _bump_generation()


def invalidate_user_workspace_entries(username: str) -> None:
    """Drop every cached workspace entry, grant or denial, for one user.

    Group membership drives the group-scoped branch of workspace resolution, so a
    membership change can alter this user's permission in ANY workspace — but only
    this user's. Keys are ``username:workspace`` with both parts percent-encoded, so the
    prefix ``username:`` is exact — it cannot match another user whose name merely starts
    with this one — and leaves every other user's entries warm.

    This matters for throughput as well as correctness: OIDC login re-syncs group
    membership on every sign-in, so a full flush here would wipe the cache fleet-wide
    on each login.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        # Nothing is ever cached with workspaces off, so skip the work entirely —
        # otherwise every login pays a Redis keyspace SCAN for no benefit. Mirrors
        # the guard in get_workspace_permission_cached.
        return
    _bump_generation()
    for cache in _caches():
        cache.delete_prefix(_user_key_prefix(username))
    _bump_generation()
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
    _bump_generation()
    for member in members:
        key = _make_cache_key(member.username, workspace)
        for cache in caches:
            cache.delete(key)
    _bump_generation()
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
    _bump_generation()
    for cache in _caches():
        cache.clear()
    _bump_generation()
    logger.debug("Workspace permission cache fully flushed (regex CUD)")


def _match_workspace_regex_permission(regexes, workspace: str) -> Permission | None:
    """The permission the best workspace pattern grants on ``workspace``, or None.

    Per D-07 the best (lowest-number) priority tier decides; within it permission rank decides
    (D-08), ``NO_PERMISSIONS`` first, else the most permissive. This is the matcher every resource
    type uses (``grant_context.best_matching_regex``), so the two cannot drift.

    Parameters:
        regexes: Workspace pattern entities, normally sorted by priority ascending.
        workspace: The workspace name to match against.

    Returns:
        Permission object or None if no regex matches.
    """
    return match_workspace_pattern(regexes, workspace)


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

    The source walk is ``grant_context.resolve_workspace_permission`` (issue #460). A source that
    errors before a match makes the answer unknown: a lower-priority source's grant may be wider
    than what the failed source holds, so the walk is denied (fail closed) rather than falling
    through to it.

    Parameters:
        username: The username to look up.
        workspace: The workspace name.

    Returns:
        ``(permission, errored)``. ``errored`` True means the result must not be cached;
        the permission is then always None.
    """
    return resolve_workspace_permission(username, workspace, config.PERMISSION_SOURCE_ORDER)
