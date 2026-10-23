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

import threading
from typing import Any

from cachetools import TTLCache


class LocalTTLCacheBackend:
    """In-process TTL cache backed by cachetools.TTLCache.

    ``TTLCache`` is not thread-safe, and the cache is shared by every thread of the process: the
    event loop and the thread pool that runs Flask requests. A lock guards each operation.

    Parameters:
        maxsize: Maximum number of entries.
        ttl: Time-to-live in seconds for each entry.
    """

    def __init__(self, maxsize: int, ttl: int) -> None:
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = value

    def delete(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            # Materialize the key list first: TTLCache mutates on iteration when
            # entries expire, and we delete while walking it.
            for key in [k for k in list(self._cache.keys()) if isinstance(k, str) and k.startswith(prefix)]:
                self._cache.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
