import requests
from authlib.jose import jwt
from authlib.jose.errors import BadSignatureError

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.user import create_user, populate_groups, update_user

logger = get_logger()


def _get_oidc_jwks():
    """Fetch JWKS from OIDC provider without caching."""
    if config.OIDC_DISCOVERY_URL is None:
        raise ValueError("OIDC_DISCOVERY_URL is not set in the configuration")

    try:
        logger.debug("Fetching OIDC discovery metadata")
        metadata = requests.get(config.OIDC_DISCOVERY_URL, timeout=10).json()
        jwks_uri = metadata.get("jwks_uri")
        if not jwks_uri:
            raise ValueError("No jwks_uri found in OIDC discovery metadata")

        logger.debug(f"Fetching JWKS from {jwks_uri}")
        jwks = requests.get(jwks_uri, timeout=10).json()
        return jwks
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch OIDC JWKS: {e}")
        raise


def validate_token(token):
    """Validate JWT token using OIDC JWKS."""
    try:
        jwks = _get_oidc_jwks()
        payload = jwt.decode(token, jwks)
        payload.validate()
        return payload
    except BadSignatureError as e:
        logger.error("Token validation failed with bad signature: %s", str(e))
        raise
    except Exception as e:
        logger.error("Unexpected error during token validation: %s", str(e))
        raise
