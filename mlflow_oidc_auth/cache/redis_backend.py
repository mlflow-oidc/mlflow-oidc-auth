"""
Redis-backed cache backend for multi-replica deployments.

Requires the ``redis`` package (install via ``pip install mlflow-oidc-auth[cache]``).
Values are serialized with pickle for round-trip fidelity of arbitrary Python objects.

Configuration:
- ``CACHE_REDIS_URL``: Redis connection URL (e.g. ``redis://localhost:6379/0``).
- ``CACHE_KEY_PREFIX``: Optional prefix for all keys (default ``mlflow_oidc_auth:``).

Thread-safety: redis-py's ConnectionPool is thread-safe.
"""

import pickle
from typing import Any

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


class RedisCacheBackend:
    """Redis-backed cache with TTL and namespace prefix.

    Parameters:
        url: Redis connection URL.
        prefix: Key prefix for namespace isolation.
        ttl: Default time-to-live in seconds for each entry.
    """

    def __init__(self, url: str, prefix: str, ttl: int) -> None:
        try:
            import redis
        except ImportError:
            raise ImportError(
                "Redis cache backend requires the 'redis' package. "
                "Install it with: pip install mlflow-oidc-auth[cache]"
            )

        self._client = redis.Redis.from_url(url, decode_responses=False)
        self._prefix = prefix
        self._ttl = ttl

        # Verify connectivity at init time so misconfig fails fast
        try:
            self._client.ping()
            logger.info("Redis cache backend connected to %s", url)
        except redis.ConnectionError as e:
            raise ConnectionError(f"Cannot connect to Redis at {url}: {e}") from e

    def _make_key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def get(self, key: str) -> Any | None:
        raw = self._client.get(self._make_key(key))
        if raw is None:
            return None
        return pickle.loads(raw)

    def set(self, key: str, value: Any) -> None:
        raw = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        self._client.setex(self._make_key(key), self._ttl, raw)

    def delete(self, key: str) -> None:
        self._client.delete(self._make_key(key))

    def clear(self) -> None:
        """Delete all keys matching this backend's prefix.

        Uses SCAN to avoid blocking the server (no KEYS *).
        """
        cursor = 0
        pattern = f"{self._prefix}*"
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match=pattern, count=500)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break
