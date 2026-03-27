import requests
from authlib.jose import jwt
from authlib.jose.errors import BadSignatureError

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.user import create_user, populate_groups, update_user

logger = get_logger()


def _get_oidc_jwks() -> dict:
    """Fetch JWKS from OIDC provider.

    Note:
        We intentionally avoid local caching here. JWKS endpoints are designed to be
        highly available and caching can introduce subtle key-rotation issues.

    Returns:
        The JWKS payload as a JSON-decoded dictionary.
    """
    if config.OIDC_DISCOVERY_URL is None:
        raise ValueError("OIDC_DISCOVERY_URL is not set in the configuration")

    try:
        logger.debug("Fetching OIDC discovery metadata")
        metadata = requests.get(config.OIDC_DISCOVERY_URL).json()
        jwks_uri = metadata.get("jwks_uri")
        if not jwks_uri:
            raise ValueError("No jwks_uri found in OIDC discovery metadata")

        logger.debug(f"Fetching JWKS from {jwks_uri}")
        jwks = requests.get(jwks_uri).json()
        return jwks
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch OIDC JWKS: {e}")
        raise


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
        # Refresh JWKS and retry once. This is expected when keys rotate.
        jwks = _get_oidc_jwks()
        payload = jwt.decode(token, jwks, claims_options=claims_options)
        payload.validate()
        return payload
    except Exception as e:
        logger.error("Unexpected error during token validation: %s", str(e))
        raise
