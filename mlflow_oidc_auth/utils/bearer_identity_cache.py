"""Cache of bearer identity decisions (see ``middleware/auth_middleware._bearer_identity``).

A deployment with more than one provider resolves every bearer token's identity the way login
does; caching the decision keeps that off most requests. Entries live as long as permission
decisions do, and the whole cache is flushed when a user is deleted or an identity is bound, so a
decision never outlives the account or binding it was made about.
"""

from mlflow_oidc_auth.cache import CacheBackend, get_cache_backend
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

_cache: CacheBackend | None = None


def bearer_identity_cache() -> CacheBackend:
    """The cache, created on first use."""
    global _cache
    if _cache is None:
        _cache = get_cache_backend("bearer-identity", maxsize=4096, ttl=getattr(config, "PERMISSION_CACHE_TTL_SECONDS", 30))
    return _cache


def flush_bearer_identity_cache() -> None:
    """Drop every cached decision. Never raises: a failure leaves entries to expire by TTL."""
    try:
        bearer_identity_cache().clear()
    except Exception as e:
        logger.warning("Bearer identity cache flush failed (%s); entries expire via TTL", type(e).__name__)
