"""
Authentication router for FastAPI application.

This router handles OIDC authentication flows including login, logout, and callback.
"""

import secrets
from collections.abc import Awaitable
from typing import Any, Optional
from urllib.parse import urlencode

from authlib.jose.errors import BadSignatureError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.oauth import oauth, is_oidc_configured
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


async def _maybe_await(result: Any) -> Any:
    """Await the result when it's awaitable; otherwise return it directly."""

    if isinstance(result, Awaitable) or hasattr(result, "__await__"):
        return await result
    return result


async def _refresh_oidc_jwks() -> None:
    """Force a JWKS refresh on the OAuth client to handle key rotation."""

    refresh_fn = getattr(oauth.oidc, "fetch_jwk_set", None)
    metadata_refresh_fn = getattr(oauth.oidc, "load_server_metadata", None)

    try:
        if refresh_fn:
            await _maybe_await(refresh_fn(force=True))  # type: ignore[call-arg]
            return
        if metadata_refresh_fn:
            await _maybe_await(metadata_refresh_fn(force=True))  # type: ignore[call-arg]
    except Exception as exc:  # pragma: no cover - defensive logging path
        logger.warning(f"Failed to refresh OIDC JWKS after bad signature: {exc}")


async def _call_authorize_access_token(request: Request) -> Optional[dict[str, Any]]:
    """Invoke authorize_access_token while supporting sync or async implementations."""

    token_call = oauth.oidc.authorize_access_token(request)  # type: ignore
    return await _maybe_await(token_call)


async def _authorize_access_token_with_retry(request: Request) -> Optional[dict[str, Any]]:
    """Exchange code for tokens, retrying once after a JWKS refresh on any validation failure."""

    last_error: Optional[Exception] = None

    for attempt in range(2):
        try:
            return await _call_authorize_access_token(request)
        except BadSignatureError as exc:
            last_error = exc
            logger.warning("OIDC token exchange attempt %d failed with bad signature: %s", attempt + 1, exc)
            if attempt == 0:
                await _refresh_oidc_jwks()
                continue
            break
        except Exception as exc:
            last_error = exc
            logger.warning("OIDC token exchange attempt %d failed: %s", attempt + 1, exc)
            if attempt == 0:
                await _refresh_oidc_jwks()
                continue
            break

    if last_error:
        raise last_error
    return None


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
    url = f"{base_url}{UI_ROUTER_PREFIX}{path}"

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
        # Check if OIDC is properly configured before proceeding
        if not is_oidc_configured():
            logger.error("OIDC is not properly configured")
            raise HTTPException(status_code=500, detail="OIDC authentication not available - configuration error")

        # Get session for storing OAuth state (using Starlette's built-in session)
        session = request.session

        # Generate OAuth state for CSRF protection
        oauth_state = secrets.token_urlsafe(32)
        session["oauth_state"] = oauth_state

        # Get redirect URI (configured or dynamic). Use a safe fallback if dynamic calculation fails
        try:
            redirect_url = get_configured_or_dynamic_redirect_uri(request=request, callback_path=CALLBACK, configured_uri=config.OIDC_REDIRECT_URI)
        except Exception as e:
            logger.warning(f"Failed to get dynamic redirect URI: {e}")
            # Fallback to base_url + callback when request.url or other internals are not available in tests
            base = str(getattr(request, "base_url", "http://localhost:8000"))
            redirect_url = base.rstrip("/") + CALLBACK

        logger.debug(f"OIDC redirect URL: {redirect_url}")

        # Redirect to OIDC provider
        try:
            if not hasattr(oauth.oidc, "authorize_redirect"):
                logger.error("OIDC client authorize_redirect method not available")
                raise HTTPException(status_code=500, detail="OIDC authentication not available")

            return await oauth.oidc.authorize_redirect(  # type: ignore
                request,
                redirect_uri=redirect_url,
                state=oauth_state,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to initiate OAuth redirect: {e}")
            raise HTTPException(status_code=500, detail="Failed to initiate OIDC login")

    except HTTPException:
        # Preserve explicit HTTPExceptions raised above
        raise
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
        # Ensure OIDC client is registered (critical for multi-replica deployments)
        # This handles the case where callback hits a replica that hasn't registered the client yet
        if not is_oidc_configured():
            logger.error("OIDC is not properly configured when processing callback")
            auth_error_url = _build_ui_url(request, "/auth", {"error": ["OIDC authentication not available - configuration error"]})
            return RedirectResponse(url=auth_error_url, status_code=302)

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
                default_redirect = _build_ui_url(request, "/user")

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

    errors = []

    # Handle OIDC error response
    error_param = request.query_params.get("error")
    error_description = request.query_params.get("error_description")
    if error_param:
        safe_desc = html.escape(error_description) if error_description else ""
        errors.append("OIDC provider error")
        if safe_desc:
            errors.append(f"{safe_desc}")
        return None, errors

    # State check for CSRF protection
    state = request.query_params.get("state")
    stored_state = session.get("oauth_state")
    if not stored_state:
        errors.append("Missing OAuth state in session")
        return None, errors
    if state != stored_state:
        errors.append("Invalid state parameter")
        return None, errors

    # Clear the OAuth state after validation
    session.pop("oauth_state", None)

    # Get authorization code
    code = request.query_params.get("code")
    if not code:
        errors.append("No authorization code received")
        return None, errors

    try:
        # Exchange authorization code for tokens
        if not hasattr(oauth.oidc, "authorize_access_token"):
            errors.append("OIDC configuration error: OAuth client not properly initialized.")
            return None, errors

        token_response = await _authorize_access_token_with_retry(request)

        if not token_response:
            errors.append("Failed to exchange authorization code")
            return None, errors

        # Validate the token and get user info
        access_token = token_response.get("access_token")
        id_token = token_response.get("id_token")
        userinfo = token_response.get("userinfo")

        if not userinfo:
            errors.append("No user information received")
            return None, errors

        # Extract user details
        email = userinfo.get("email") or userinfo.get("preferred_username")
        display_name = userinfo.get("name")

        if not email:
            errors.append("No email provided in OIDC userinfo")
            return None, errors
        if not display_name:
            errors.append("No display name provided in OIDC userinfo")
            return None, errors

        # Handle user and group management
        try:
            # Use module-level config (possibly patched in tests) and call user management
            # functions via the mlflow_oidc_auth.user module so test monkeypatches apply.
            import importlib
            import mlflow_oidc_auth.user as user_module

            # Get user groups
            if config.OIDC_GROUP_DETECTION_PLUGIN:
                user_groups = importlib.import_module(config.OIDC_GROUP_DETECTION_PLUGIN).get_user_groups(access_token)
            else:
                user_groups = userinfo.get(config.OIDC_GROUPS_ATTRIBUTE, [])

            logger.debug(f"User groups: {user_groups}")

            # Check authorization
            # Determine admin and allowed groups
            is_admin = any(group in user_groups for group in config.OIDC_ADMIN_GROUP_NAME)
            if not is_admin and not any(group in user_groups for group in config.OIDC_GROUP_NAME):
                errors.append("User is not allowed to login")
                return None, errors

            # Create/update user and groups using user_module so monkeypatched functions are used in tests
            user_module.create_user(username=email.lower(), display_name=display_name, is_admin=is_admin)
            user_module.populate_groups(group_names=user_groups)
            user_module.update_user(username=email.lower(), group_names=user_groups)

            logger.info(f"User {email} successfully processed with groups: {user_groups}")

        except Exception as e:
            logger.error(f"User/group management error: {str(e)}")
            errors.append("Failed to update user/groups")
            return None, errors

        return email.lower(), []

    except Exception as e:
        logger.error("OIDC token exchange error (%s.%s): %s", type(e).__module__, type(e).__name__, str(e))
        errors.append("Failed to process authentication response")
        return None, errors
