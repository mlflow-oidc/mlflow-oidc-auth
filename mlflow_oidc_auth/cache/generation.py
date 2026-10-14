"""Invalidation generations and collision-free keys, shared by the plugin's caches.

A cache that is filled from the database can race an invalidation: a lookup reads the old row,
the write commits and the invalidation deletes the (still absent) entry, then the lookup writes
what it read. A :class:`GenerationGuard` closes that window. Invalidations bump a generation
before and after their deletes (:meth:`GenerationGuard.invalidating`); a lookup reads the
generation before it reads the database and writes its entry only if the generation has not
moved, re-checking after the write (:meth:`GenerationGuard.store_unless_raced`). Used by the
workspace cache (issue #456) and the grant-context cache (issue #460).
"""

import uuid
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional
from urllib.parse import quote

from mlflow_oidc_auth.cache.backend import CacheBackend
from mlflow_oidc_auth.cache.factory import get_cache_backend

_GENERATION_KEY = "generation"

#: How long a generation value is kept, at least. A lookup is only fooled if a value is written
#: and then expires within the few milliseconds of one lookup, so this only has to be long.
GENERATION_MIN_TTL = 3600


def key_part(value: Any) -> str:
    """Percent-encode one key component, so ``:`` (and ``%``) never survive unencoded.

    Parameters:
        value: The component.

    Returns:
        The encoded component.
    """
    return quote(str(value), safe="")


def make_key(*parts: Any) -> str:
    """Join percent-encoded components with ``:``, the only literal ``:`` in the key.

    Parameters:
        parts: The key components.

    Returns:
        A key no other combination of components can produce.
    """
    return ":".join(key_part(part) for part in parts)


class GenerationGuard:
    """One invalidation generation, kept in its own one-entry cache.

    Its own store, so no flood of other entries can evict it. On Redis it is shared, so an
    invalidation on any replica is seen by a lookup on every replica.

    Parameters:
        namespace: The cache namespace of the generation entry.
        ttl: Returns the TTL of the entries it guards; the generation is kept at least
            :data:`GENERATION_MIN_TTL`, and never shorter than those entries.
    """

    def __init__(self, namespace: str, ttl: Callable[[], int]) -> None:
        self._namespace = namespace
        self._ttl = ttl
        self._cache: Optional[CacheBackend] = None

    def _backend(self) -> CacheBackend:
        if self._cache is None:
            self._cache = get_cache_backend(self._namespace, maxsize=1, ttl=max(self._ttl(), GENERATION_MIN_TTL))
        return self._cache

    def reset(self) -> None:
        """Forget the backend, so the next use builds it again from the configuration (tests)."""
        self._cache = None

    def current(self) -> Any:
        """The current generation; any change means an invalidation happened."""
        return self._backend().get(_GENERATION_KEY)

    def bump(self) -> None:
        """Record that an invalidation is happening.

        A random value rather than a counter: any change is detected, and no atomic increment is
        needed on either backend.
        """
        self._backend().set(_GENERATION_KEY, uuid.uuid4().hex)

    @contextmanager
    def invalidating(self) -> Iterator[None]:
        """Bump the generation before and after the deletes run inside the block.

        The bump before means a lookup that checks after writing its entry sees the move whenever
        the delete could still be pending; the bump after means a lookup that read the generation
        before the delete sees it too.
        """
        self.bump()
        try:
            yield
        finally:
            self.bump()

    def store_unless_raced(
        self,
        cache: CacheBackend,
        key: str,
        value: Any,
        generation: Any,
        current: Optional[Callable[[], Any]] = None,
        check_before_write: bool = True,
    ) -> bool:
        """Write ``value`` unless an invalidation overlapped the lookup that produced it.

        - Moved after the write: delete what was written. An invalidation that bumps only after
          this last check also deletes only after it, so it removes the entry itself. This check
          alone is what makes the write safe.
        - With ``check_before_write``, a generation that moved before the write skips the write
          too — one more round trip to spare a write that would be deleted anyway.

        Parameters:
            cache: The cache to write to.
            key: The entry's key.
            value: The entry.
            generation: The generation read before the database was read.
            current: Reads the current generation; :meth:`current` when omitted.
            check_before_write: Also check before writing (see above).

        Returns:
            Whether the entry was left in the cache.
        """
        read = current or self.current
        if check_before_write and read() != generation:
            return False
        cache.set(key, value)
        if read() != generation:
            cache.delete(key)
            return False
        return True
