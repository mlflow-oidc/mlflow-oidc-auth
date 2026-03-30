import threading

import requests
from authlib.jose import jwt
from authlib.jose.errors import BadSignatureError
from cachetools import TTLCache

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.user import create_user, populate_groups, update_user

logger = get_logger()

# JWKS cache: single-entry TTL cache shared across all token validations.
# TTL is configured via OIDC_JWKS_CACHE_TTL_SECONDS (default 300s).
# Thread-safe via a lock since multiple ASGI workers may validate concurrently.
_jwks_cache: TTLCache = TTLCache(maxsize=1, ttl=config.OIDC_JWKS_CACHE_TTL_SECONDS)
_jwks_cache_lock = threading.Lock()

_JWKS_CACHE_KEY = "jwks"


def _get_oidc_jwks(force_refresh: bool = False) -> dict:
    """Fetch JWKS from OIDC provider, with TTL-based caching.

    Results are cached for ``OIDC_JWKS_CACHE_TTL_SECONDS`` (default 300s) to
    avoid hitting the OIDC provider on every token validation.  When
    ``force_refresh`` is True the cache is cleared first — this is used on
    ``BadSignatureError`` to handle key rotation.

    Parameters:
        force_refresh: If True, bypass the cache and fetch fresh JWKS.

    Returns:
        The JWKS payload as a JSON-decoded dictionary.
    """
    if config.OIDC_DISCOVERY_URL is None:
        raise ValueError("OIDC_DISCOVERY_URL is not set in the configuration")

    with _jwks_cache_lock:
        if force_refresh:
            _jwks_cache.pop(_JWKS_CACHE_KEY, None)

        cached = _jwks_cache.get(_JWKS_CACHE_KEY)
        if cached is not None:
            return cached

    # Fetch outside the lock to avoid blocking other threads during HTTP I/O
    try:
        logger.debug("Fetching OIDC discovery metadata")
        metadata = requests.get(config.OIDC_DISCOVERY_URL).json()
        jwks_uri = metadata.get("jwks_uri")
        if not jwks_uri:
            raise ValueError("No jwks_uri found in OIDC discovery metadata")

        logger.debug("Fetching JWKS from %s", jwks_uri)
        jwks = requests.get(jwks_uri).json()
    except requests.exceptions.RequestException as e:
        logger.error("Failed to fetch OIDC JWKS: %s", e)
        raise

    with _jwks_cache_lock:
        _jwks_cache[_JWKS_CACHE_KEY] = jwks

    return jwks


def _get_claims_options() -> dict | None:
    """Build JWT claims validation options.

    Returns:
        A claims_options dict for authlib jwt.decode if audience validation
        is configured, otherwise None.
    """
    if config.OIDC_AUDIENCE:
        return {"aud": {"essential": True, "value": config.OIDC_AUDIENCE}}
    return None


def validate_token(token: str):
    """Validate JWT token using OIDC JWKS.

    When OIDC_AUDIENCE is configured, the ``aud`` claim is validated
    against the expected audience value during ``payload.validate()``.
    """
    claims_options = _get_claims_options()
    try:
        jwks = _get_oidc_jwks()
        payload = jwt.decode(token, jwks, claims_options=claims_options)
        payload.validate()
        return payload
    except BadSignatureError as e:
        logger.error("Token validation failed with bad signature: %s", str(e))
        # Force-refresh JWKS and retry once. This handles key rotation.
        jwks = _get_oidc_jwks(force_refresh=True)
        payload = jwt.decode(token, jwks, claims_options=claims_options)
        payload.validate()
        return payload
    except Exception as e:
        logger.error("Unexpected error during token validation: %s", str(e))
        raise
