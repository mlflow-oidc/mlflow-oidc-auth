"""
Pluggable cache backend for MLflow OIDC Auth.

Provides a CacheBackend protocol with two implementations:
- LocalTTLCacheBackend: In-process cachetools.TTLCache (default, zero-config)
- RedisCacheBackend: Redis-backed cache for multi-replica deployments

Backend selection is driven by ``CACHE_BACKEND`` config:
- ``"local"`` (default) — uses LocalTTLCacheBackend
- ``"redis"`` — uses RedisCacheBackend (requires ``redis`` package and ``CACHE_REDIS_URL``)

Usage::

    from mlflow_oidc_auth.cache import get_cache_backend

    cache = get_cache_backend("permissions", maxsize=2048, ttl=30)
    cache.set("key", value)
    result = cache.get("key")
"""

from mlflow_oidc_auth.cache.backend import CacheBackend
from mlflow_oidc_auth.cache.factory import get_cache_backend

__all__ = [
    "CacheBackend",
    "get_cache_backend",
]
