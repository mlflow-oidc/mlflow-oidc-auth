"""
Authentication router for FastAPI application.

This router handles OIDC authentication flows including login, logout, and callback.
"""

import secrets
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.oauth import oauth
from mlflow_oidc_auth.utils import get_configured_or_dynamic_redirect_uri

from ._prefix import UI_ROUTER_PREFIX

logger = get_logger()

auth_router = APIRouter(
    tags=["auth"],
    responses={404: {"description": "Not found"}},
)

CALLBACK = "/callback"
LOGIN = "/login"
LOGOUT = "/logout"
AUTH_STATUS = "/auth/status"


def _build_ui_url(request: Request, path: str, query_params: Optional[dict] = None) -> str:
    """
    Build a UI URL with the correct prefix and optional query parameters.

    Args:
        request: FastAPI request object
        path: The UI route path (e.g., "/auth", "/home")
        query_params: Optional dictionary of query parameters

    Returns:
        Complete URL string for the UI route
    """
    base_url = str(request.base_url).rstrip("/")
    url = f"{base_url}{UI_ROUTER_PREFIX}/#{path}"

    if query_params:
        query_string = urlencode(query_params, doseq=True)
        url = f"{url}?{query_string}"

    return url


@auth_router.get(LOGIN)
async def login(request: Request):
    """
    Initiate OIDC login flow.

    This endpoint redirects the user to the OIDC provider for authentication.

    Args:
        request: FastAPI request object

    Returns:
        Redirect response to OIDC provider
    """
    logger.info("Starting OIDC login flow")

    try:
        # Get session for storing OAuth state (using Starlette's built-in session)
        session = request.session

        # Generate OAuth state for CSRF protection
        oauth_state = secrets.token_urlsafe(32)
        session["oauth_state"] = oauth_state

        # Get redirect URI (configured or dynamic)
        redirect_url = get_configured_or_dynamic_redirect_uri(request=request, callback_path=CALLBACK, configured_uri=config.OIDC_REDIRECT_URI)

        logger.debug(f"OIDC redirect URL: {redirect_url}")
        logger.debug(f"OAuth state: {oauth_state}")

        # Redirect to OIDC provider
        if hasattr(oauth.oidc, "authorize_redirect"):
            return await oauth.oidc.authorize_redirect(  # type: ignore
                request,
                redirect_uri=redirect_url,
                state=oauth_state,
            )
        else:
            logger.error("OIDC client not properly configured")
            raise HTTPException(status_code=500, detail="OIDC authentication not available")

    except Exception as e:
        logger.error(f"Error initiating OIDC login: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate OIDC login")


@auth_router.get(LOGOUT)
async def logout(request: Request):
    """
    Handle user logout.

    This endpoint clears the user session and optionally redirects to OIDC logout.

    Args:
        request: FastAPI request object

    Returns:
        Redirect response or logout confirmation
    """
    logger.info("Processing user logout")

    try:
        # Get and clear session (using Starlette's built-in session)
        session = request.session
        username = session.get("username")
        session.clear()

        if username:
            logger.info(f"User {username} logged out successfully")

        # Check if OIDC provider supports logout
        if hasattr(oauth.oidc, "server_metadata"):
            metadata = getattr(oauth.oidc, "server_metadata", {})
            end_session_endpoint = metadata.get("end_session_endpoint")

            if end_session_endpoint:
                # Redirect to OIDC provider logout with post-logout redirect to auth page
                post_logout_redirect = _build_ui_url(request, "/auth")
                logout_url = f"{end_session_endpoint}?post_logout_redirect_uri={post_logout_redirect}"
                return RedirectResponse(url=logout_url, status_code=302)

        # Default redirect to auth page using the helper function
        auth_url = _build_ui_url(request, "/auth")
        return RedirectResponse(url=auth_url, status_code=302)

    except Exception as e:
        logger.error(f"Error during logout: {e}")
        # Still clear session even if redirect fails - redirect to auth page
        auth_url = _build_ui_url(request, "/auth")
        return RedirectResponse(url=auth_url, status_code=302)


@auth_router.get(CALLBACK)
async def callback(request: Request):
    """
    Handle OIDC callback after authentication.

    This endpoint processes the OIDC callback, validates the token,
    and establishes a user session.

    Args:
        request: FastAPI request object

    Returns:
        Redirect response to home page or error page
    """
    logger.info("Processing OIDC callback")

    try:
        # Get session (using Starlette's built-in session)
        session = request.session

        # Process OIDC callback using FastAPI-native implementation
        email, errors = await _process_oidc_callback_fastapi(request, session)

        if errors:
            # Handle authentication errors
            logger.error(f"OIDC callback errors: {errors}")

            # Redirect to auth page with error parameters for frontend display
            auth_error_url = _build_ui_url(request, "/auth", {"error": errors})

            logger.debug(f"Redirecting to auth error page: {auth_error_url}")
            return RedirectResponse(url=auth_error_url, status_code=302)

        if email:
            # Successful authentication
            session["username"] = email
            session["authenticated"] = True

            logger.info(f"User {email} authenticated successfully via OIDC")

            # Redirect to UI home page or original destination
            default_redirect = session.pop("redirect_after_login", None)
            if not default_redirect:
                # Default to UI home page using the helper function
                default_redirect = _build_ui_url(request, "/home")

            return RedirectResponse(url=default_redirect, status_code=302)
        else:
            # Authentication failed without specific errors
            logger.error("OIDC authentication failed without specific errors")
            raise HTTPException(status_code=401, detail="Authentication failed")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in OIDC callback: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during authentication")


@auth_router.get(AUTH_STATUS)
async def auth_status(request: Request):
    """
    Get current authentication status.

    This endpoint returns information about the current user's authentication state.

    Args:
        request: FastAPI request object

    Returns:
        JSON response with authentication status
    """
    try:
        session = request.session
        username = session.get("username")
        is_authenticated = bool(username)

        return JSONResponse(
            content={
                "authenticated": is_authenticated,
                "username": username,
                "provider": config.OIDC_PROVIDER_DISPLAY_NAME if is_authenticated else None,
            }
        )

    except Exception as e:
        logger.error(f"Error getting auth status: {e}")
        return JSONResponse(status_code=500, content={"error": "Failed to get authentication status"})


async def _process_oidc_callback_fastapi(request: Request, session) -> tuple[Optional[str], list[str]]:
    """
    Process the OIDC callback logic using FastAPI-native implementation.

    Args:
        request: FastAPI request object
        session: SessionManager instance

    Returns:
        Tuple of (email, error_list)
    """
    import html

    from mlflow_oidc_auth.oauth import oauth

    errors = []

    # Handle OIDC error response
    error_param = request.query_params.get("error")
    error_description = request.query_params.get("error_description")
    if error_param:
        safe_desc = html.escape(error_description) if error_description else ""
        errors.append("OIDC provider error: An error occurred during the OIDC authentication process.")
        if safe_desc:
            errors.append(f"{safe_desc}")
        return None, errors

    # State check for CSRF protection
    state = request.query_params.get("state")
    stored_state = session.get("oauth_state")
    if not stored_state:
        errors.append("Session error: Missing OAuth state in session. Please try logging in again.")
        return None, errors
    if state != stored_state:
        errors.append("Security error: Invalid state parameter. Possible CSRF detected.")
        return None, errors

    # Clear the OAuth state after validation
    session.pop("oauth_state", None)

    # Get authorization code
    code = request.query_params.get("code")
    if not code:
        errors.append("OIDC error: No authorization code received from provider.")
        return None, errors

    try:
        # Exchange authorization code for tokens
        if not hasattr(oauth.oidc, "authorize_access_token"):
            errors.append("OIDC configuration error: OAuth client not properly initialized.")
            return None, errors

        token_response = await oauth.oidc.authorize_access_token(request)  # type: ignore

        if not token_response:
            errors.append("OIDC token error: Failed to exchange authorization code for tokens.")
            return None, errors

        # Validate the token and get user info
        access_token = token_response.get("access_token")
        id_token = token_response.get("id_token")
        userinfo = token_response.get("userinfo")

        if not userinfo:
            errors.append("OIDC token error: No user information received from provider.")
            return None, errors

        # Extract user details
        email = userinfo.get("email") or userinfo.get("preferred_username")
        display_name = userinfo.get("name")

        if not email:
            errors.append("User profile error: No email provided in OIDC userinfo.")
            return None, errors
        if not display_name:
            errors.append("User profile error: No display name provided in OIDC userinfo.")
            return None, errors

        # Handle user and group management
        try:
            from mlflow_oidc_auth.config import config
            from mlflow_oidc_auth.user import create_user, populate_groups, update_user

            # Get user groups
            if config.OIDC_GROUP_DETECTION_PLUGIN:
                import importlib

                user_groups = importlib.import_module(config.OIDC_GROUP_DETECTION_PLUGIN).get_user_groups(access_token)
            else:
                user_groups = userinfo.get(config.OIDC_GROUPS_ATTRIBUTE, [])

            logger.debug(f"User groups: {user_groups}")

            # Check authorization
            is_admin = config.OIDC_ADMIN_GROUP_NAME in user_groups
            if not is_admin and not any(group in user_groups for group in config.OIDC_GROUP_NAME):
                errors.append("Authorization error: User is not allowed to login.")
                return None, errors

            # Create/update user and groups
            create_user(username=email.lower(), display_name=display_name, is_admin=is_admin)
            populate_groups(group_names=user_groups)
            update_user(username=email.lower(), group_names=user_groups)

            logger.info(f"User {email} successfully processed with groups: {user_groups}")

        except Exception as e:
            logger.error(f"User/group management error: {str(e)}")
            errors.append("User/group DB error: Failed to update user/groups")
            return None, errors

        return email.lower(), []

    except Exception as e:
        logger.error(f"OIDC token exchange error: {str(e)}")
        errors.append("OIDC token error: Failed to process authentication response.")
        return None, errors
