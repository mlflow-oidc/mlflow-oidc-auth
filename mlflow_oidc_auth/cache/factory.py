"""
Cache backend factory.

Creates cache backend instances based on the ``CACHE_BACKEND`` configuration.
Supports ``"local"`` (default) and ``"redis"`` backends.

Each call creates a fresh backend instance — callers are expected to hold
a module-level reference (lazy-initialized) to reuse the same backend.
"""

from mlflow_oidc_auth.cache.backend import CacheBackend
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


def get_cache_backend(namespace: str, maxsize: int, ttl: int) -> CacheBackend:
    """Create a cache backend instance based on application configuration.

    Parameters:
        namespace: Logical cache name (e.g. ``"permissions"``, ``"workspace"``).
            Used as a sub-prefix in Redis to isolate different cache domains.
        maxsize: Maximum entries for local backend (ignored by Redis).
        ttl: Time-to-live in seconds for cache entries.

    Returns:
        A CacheBackend implementation.

    Raises:
        ValueError: If ``CACHE_BACKEND`` is set to an unknown value.
        ImportError: If ``"redis"`` is selected but the redis package is missing.
        ConnectionError: If ``"redis"`` is selected but the server is unreachable.
    """
    from mlflow_oidc_auth.config import config

    backend_type = getattr(config, "CACHE_BACKEND", "local")

    if backend_type == "local":
        from mlflow_oidc_auth.cache.local_backend import LocalTTLCacheBackend

        logger.info(
            "Using local TTL cache backend for '%s' (maxsize=%d, ttl=%ds)",
            namespace,
            maxsize,
            ttl,
        )
        return LocalTTLCacheBackend(maxsize=maxsize, ttl=ttl)

    elif backend_type == "redis":
        from mlflow_oidc_auth.cache.redis_backend import RedisCacheBackend

        redis_url = getattr(config, "CACHE_REDIS_URL", None)
        if not redis_url:
            raise ValueError("CACHE_BACKEND is set to 'redis' but CACHE_REDIS_URL is not configured")

        key_prefix = getattr(config, "CACHE_KEY_PREFIX", "mlflow_oidc_auth:")
        full_prefix = f"{key_prefix}{namespace}:"

        logger.info(
            "Using Redis cache backend for '%s' (url=%s, prefix=%s, ttl=%ds)",
            namespace,
            redis_url,
            full_prefix,
            ttl,
        )
        return RedisCacheBackend(url=redis_url, prefix=full_prefix, ttl=ttl)

    else:
        raise ValueError(f"Unknown CACHE_BACKEND: '{backend_type}'. Supported values: 'local', 'redis'")
