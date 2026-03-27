"""
In-process TTL cache backend using cachetools.

This is the default backend — zero-config, no external dependencies beyond
cachetools (already a core dependency). Suitable for single-replica deployments
or when cross-replica cache coherence is not required.

Limitations:
- Each process has its own isolated cache.
- Cache invalidation is local only — other replicas are unaware.
- TTL expiry is the only cross-replica consistency mechanism.
"""

from typing import Any

from cachetools import TTLCache


class LocalTTLCacheBackend:
    """In-process TTL cache backed by cachetools.TTLCache.

    Parameters:
        maxsize: Maximum number of entries.
        ttl: Time-to-live in seconds for each entry.
    """

    def __init__(self, maxsize: int, ttl: int) -> None:
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = value

    def delete(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()
