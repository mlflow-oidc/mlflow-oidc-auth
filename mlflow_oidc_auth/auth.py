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


def handle_user_and_group_management(token) -> list[str]:
    """Handle user and group management based on the token. Returns list of error messages or empty list."""
    errors = []
    email = token["userinfo"].get("email") or token["userinfo"].get("preferred_username")
    display_name = token["userinfo"].get("name")
    if not email:
        errors.append("User profile error: No email provided in OIDC userinfo.")
    if not display_name:
        errors.append("User profile error: No display name provided in OIDC userinfo.")
    if errors:
        return errors

    # Get user groups
    try:
        if config.OIDC_GROUP_DETECTION_PLUGIN:
            import importlib

            user_groups = importlib.import_module(config.OIDC_GROUP_DETECTION_PLUGIN).get_user_groups(token["access_token"])
        else:
            user_groups = token["userinfo"][config.OIDC_GROUPS_ATTRIBUTE]
    except Exception as e:
        logger.error(f"Group detection error: {str(e)}")
        errors.append("Group detection error: Failed to get user groups")
        return errors

    logger.debug(f"User groups: {user_groups}")

    is_admin = config.OIDC_ADMIN_GROUP_NAME in user_groups
    if not is_admin and not any(group in user_groups for group in config.OIDC_GROUP_NAME):
        errors.append("Authorization error: User is not allowed to login.")
        return errors

    try:
        create_user(username=email.lower(), display_name=display_name, is_admin=is_admin)
        populate_groups(group_names=user_groups)
        update_user(username=email.lower(), group_names=user_groups)
    except Exception as e:
        logger.error(f"User/group DB error: {str(e)}")
        errors.append("User/group DB error: Failed to update user/groups")

    return errors
