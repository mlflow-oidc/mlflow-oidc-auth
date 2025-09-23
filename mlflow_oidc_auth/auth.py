import requests
from authlib.jose import jwt
from authlib.jose.errors import BadSignatureError

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.user import create_user, populate_groups, update_user

logger = get_logger()


# TODO: rework, should use fastapi caching
def _get_oidc_jwks(clear_cache: bool = False):
    from mlflow_oidc_auth.app import cache

    if clear_cache:
        logger.debug("Clearing JWKS cache")
        cache.delete("jwks")
    jwks = cache.get("jwks")
    if jwks:
        logger.debug("JWKS cache hit")
        return jwks
    logger.debug("JWKS cache miss")
    if config.OIDC_DISCOVERY_URL is None:
        raise ValueError("OIDC_DISCOVERY_URL is not set in the configuration")
    metadata = requests.get(config.OIDC_DISCOVERY_URL).json()
    jwks_uri = metadata.get("jwks_uri")
    jwks = requests.get(jwks_uri).json()
    cache.set("jwks", jwks, timeout=3600)
    return jwks


def validate_token(token):
    try:
        jwks = _get_oidc_jwks()
        payload = jwt.decode(token, jwks)
        payload.validate()
        return payload
    except BadSignatureError as e:
        logger.warning("Token validation failed. Attempting JWKS refresh. Error: %s", str(e))
        jwks = _get_oidc_jwks(clear_cache=True)
        try:
            payload = jwt.decode(token, jwks)
            payload.validate()
            return payload
        except BadSignatureError as e:
            logger.error("Token validation failed after JWKS refresh. Error: %s", str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error during token validation: %s", str(e))
            raise
