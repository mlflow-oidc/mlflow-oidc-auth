from typing import Optional

import requests
from authlib.integrations.flask_client import OAuth
from authlib.jose import jwt
from authlib.jose.errors import BadSignatureError
from flask import request
from mlflow.server import app

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.user import create_user, populate_groups, update_user

_oauth_instance: Optional[OAuth] = None


def get_oauth_instance(app) -> OAuth:
    # returns a singleton instance of OAuth
    # to avoid circular imports
    global _oauth_instance

    if _oauth_instance is None:
        _oauth_instance = OAuth(app)
        _oauth_instance.register(
            name="oidc",
            client_id=config.OIDC_CLIENT_ID,
            client_secret=config.OIDC_CLIENT_SECRET,
            server_metadata_url=config.OIDC_DISCOVERY_URL,
            client_kwargs={"scope": config.OIDC_SCOPE},
        )
    return _oauth_instance


def _get_oidc_jwks(clear_cache: bool = False):
    from mlflow_oidc_auth.app import cache

    if clear_cache:
        app.logger.debug("Clearing JWKS cache")
        cache.delete("jwks")
    jwks = cache.get("jwks")
    if jwks:
        app.logger.debug("JWKS cache hit")
        return jwks
    app.logger.debug("JWKS cache miss")
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
        app.logger.warning("Token validation failed. Attempting JWKS refresh. Error: %s", str(e))
        jwks = _get_oidc_jwks(clear_cache=True)
        try:
            payload = jwt.decode(token, jwks)
            payload.validate()
            return payload
        except BadSignatureError as e:
            app.logger.error("Token validation failed after JWKS refresh. Error: %s", str(e))
            raise
        except Exception as e:
            app.logger.error("Unexpected error during token validation: %s", str(e))
            raise


def authenticate_request_basic_auth() -> bool:
    if request.authorization is None:
        return False
    username = request.authorization.username
    password = request.authorization.password
    app.logger.debug("Authenticating user %s", username)
    if username is not None and password is not None and store.authenticate_user(username.lower(), password):
        app.logger.debug("User %s authenticated", username)
        return True
    else:
        app.logger.debug("User %s not authenticated", username)
        return False


def authenticate_request_bearer_token() -> bool:
    if request.authorization and request.authorization.token:
        token = request.authorization.token
        try:
            user = validate_token(token)
            app.logger.debug("User %s authenticated", user.get("email"))
            return True
        except Exception as e:
            app.logger.error(f"JWT auth failed: {str(e)}")
            return False
    else:
        app.logger.debug("No authorization token found")
        return False


def handle_token_validation(oauth_instance):
    """Validate the token and handle JWKS refresh if necessary."""
    try:
        token = oauth_instance.oidc.authorize_access_token()
    except BadSignatureError:
        app.logger.warning("Bad signature detected. Refreshing JWKS keys.")
        oauth_instance.oidc.load_server_metadata(force=True)
        try:
            token = oauth_instance.oidc.authorize_access_token()
        except BadSignatureError:
            app.logger.error("Bad signature persists after JWKS refresh. Token verification failed.")
            return None
    app.logger.debug(f"Token: {token}")
    return token


def handle_user_and_group_management(token) -> list[str]:
    """Handle user and group management based on the token. Returns list of error messages or empty list."""
    errors = []
    email = token["userinfo"].get("email")
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
            user_groups = token["userinfo"].get(config.OIDC_GROUPS_ATTRIBUTE, [])
    except Exception as e:
        app.logger.error(f"Group detection error: {str(e)}")
        errors.append("Group detection error: Failed to get user groups")
        return errors

    app.logger.debug(f"User groups: {user_groups}")

    is_admin = config.OIDC_ADMIN_GROUP_NAME in user_groups
    if not is_admin and not any(group in user_groups for group in config.OIDC_GROUP_NAME):
        errors.append("Authorization error: User is not allowed to login.")
        return errors

    try:
        create_user(username=email.lower(), display_name=display_name, is_admin=is_admin)
        populate_groups(group_names=user_groups)
        update_user(username=email.lower(), group_names=user_groups)
    except Exception as e:
        app.logger.error(f"User/group DB error: {str(e)}")
        errors.append("User/group DB error: Failed to update user/groups")

    return errors


def process_oidc_callback(request, session) -> tuple[Optional[str], list[str]]:
    """
    Process the OIDC callback logic.
    Returns (email, error_list) tuple.
    """
    import html

    errors = []

    # Handle OIDC error response
    error_param = request.args.get("error")
    error_description = request.args.get("error_description")
    if error_param:
        safe_desc = html.escape(error_description) if error_description else ""
        errors.append("OIDC provider error: An error occurred during the OIDC authentication process.")
        if safe_desc:
            errors.append(f"{safe_desc}")
        return None, errors

    # State check
    state = request.args.get("state")
    if "oauth_state" not in session:
        errors.append("Session error: Missing OAuth state in session. Please try logging in again.")
        return None, errors
    if state != session["oauth_state"]:
        errors.append("Security error: Invalid state parameter. Possible CSRF detected.")
        return None, errors

    oauth_instance = get_oauth_instance(app)
    if oauth_instance is None or getattr(oauth_instance, "oidc", None) is None:
        app.logger.error("OAuth instance or OIDC is not properly initialized")
        errors.append("Server error: OAuth instance or OIDC is not properly initialized. Please contact the administrator.")
        return None, errors

    token = handle_token_validation(oauth_instance)
    if token is None:
        errors.append("OIDC token error: Invalid token signature or token could not be validated.")
        return None, errors

    # User and group management
    user_errors = handle_user_and_group_management(token)
    if user_errors:
        errors.extend(user_errors)
        return None, errors

    email = token["userinfo"].get("email")
    return email.lower(), []
