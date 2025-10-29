"""
Authentication Middleware for FastAPI.

This middleware handles authentication (verifying who the user is) and sets
user context in request state for use by downstream middleware and handlers.
Authorization (what the user can do) is handled by RBACMiddleware.
"""

from typing import Optional, Tuple
import base64

from fastapi import Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.auth import validate_token
from mlflow_oidc_auth.store import store

logger = get_logger()


class AuthMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for user authentication.

    This middleware:
    1. Checks if a route requires authentication
    2. Attempts to authenticate the user via various methods
    3. Sets user context in request.state for downstream use
    4. Redirects unauthenticated users to login for protected routes
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    def _is_unprotected_route(self, path: str) -> bool:
        """
        Check if the route is unprotected and doesn't require authentication.

        Args:
            path: Request path

        Returns:
            True if the route is unprotected, False otherwise
        """
        unprotected_prefixes = ("/health", "/login", "/callback", "/oidc/static", "/metrics", "/docs", "/redoc", "/openapi.json", "/oidc/ui")
        return path.startswith(unprotected_prefixes)

    async def _authenticate_basic_auth(self, auth_header: str) -> Tuple[bool, Optional[str], str]:
        """
        Authenticate using basic auth.

        Args:
            auth_header: Authorization header value

        Returns:
            Tuple of (success, username, error_message)
        """
        try:
            # Extract credentials
            encoded_credentials = auth_header.split(" ", 1)[1]
            decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")
            username, password = decoded_credentials.split(":", 1)

            # Authenticate against store
            if store.authenticate_user(username.lower(), password):
                logger.debug(f"User {username} authenticated via basic auth")
                return True, username.lower(), ""
            else:
                return False, None, "Invalid basic auth credentials"
        except Exception as e:
            logger.error(f"Basic auth error: {e}")
            return False, None, "Invalid basic auth format"

    async def _authenticate_bearer_token(self, auth_header: str) -> Tuple[bool, Optional[str], str]:
        """
        Authenticate using bearer token.

        Args:
            auth_header: Authorization header value

        Returns:
            Tuple of (success, username, error_message)
        """
        try:
            token = auth_header.split(" ", 1)[1]
            # Validate token and extract user info
            payload = validate_token(token)
            username = payload.get("email") or payload.get("preferred_username")
            if username:
                logger.debug(f"User {username} authenticated via bearer token")
                return True, username.lower(), ""
            else:
                return False, None, "Invalid token payload"
        except Exception as e:
            logger.error(f"Bearer auth error: {e}")
            return False, None, "Invalid token"

    async def _authenticate_session(self, request: Request) -> Tuple[bool, Optional[str], str]:
        """
        Authenticate using session.

        Args:
            request: FastAPI request object

        Returns:
            Tuple of (success, username, error_message)
        """
        try:
            # Check if SessionMiddleware is installed and accessible
            if hasattr(request, "session"):
                try:
                    session = request.session
                    username = session.get("username")
                    if username:
                        logger.debug(f"User {username} authenticated via session")
                        return True, username, ""
                except Exception as session_error:
                    logger.debug(f"Session access error: {session_error}")
                    return False, None, f"Session access failed: {session_error}"
            else:
                logger.debug("Session middleware not available - no session attribute")
                return False, None, "Session middleware not available"
        except Exception as e:
            logger.debug(f"Session check error: {e}")
            return False, None, f"Session error: {e}"

        return False, None, "No session authentication"

    async def _authenticate_user(self, request: Request) -> Tuple[bool, Optional[str], str]:
        """
        Attempt to authenticate the user via multiple methods.

        Args:
            request: FastAPI request object

        Returns:
            Tuple of (success, username, error_message)
        """
        # Try basic authentication first
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Basic "):
            return await self._authenticate_basic_auth(auth_header)

        # Try bearer token authentication
        if auth_header and auth_header.startswith("Bearer "):
            return await self._authenticate_bearer_token(auth_header)

        # Try session-based authentication
        return await self._authenticate_session(request)

    def _get_user_admin_status(self, username: str) -> bool:
        """
        Check if a user is an admin.

        Args:
            username: Username to check

        Returns:
            True if user is admin, False otherwise
        """
        try:
            user = store.get_user(username)
            return user.is_admin if user else False
        except Exception as e:
            logger.error(f"Error checking admin status for {username}: {e}")
            return False

    async def _handle_auth_redirect(self, request: Request) -> Response:
        """
        Handle authentication redirect for unauthenticated users.

        Args:
            request: FastAPI request object

        Returns:
            Appropriate response (redirect or auth page)
        """
        # Import here to avoid circular imports
        from mlflow_oidc_auth.utils import get_base_path

        base_path = await get_base_path(request)

        if config.AUTOMATIC_LOGIN_REDIRECT:
            login_url = f"{base_path}/login"
            return RedirectResponse(url=login_url, status_code=302)

        ui_url = f"{base_path}/oidc/ui"
        return RedirectResponse(url=ui_url, status_code=302)

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Main middleware dispatch method.

        Args:
            request: FastAPI request object
            call_next: Next middleware/handler in the chain

        Returns:
            Response from the application or an authentication redirect
        """
        path = request.url.path

        # Skip authentication for unprotected routes
        if self._is_unprotected_route(path):
            return await call_next(request)

        # Attempt authentication
        is_authenticated, username, error_msg = await self._authenticate_user(request)

        if is_authenticated and username:
            # Set user context in request state for downstream middleware/handlers
            request.state.username = username
            request.state.is_admin = self._get_user_admin_status(username)

            # ROBUST: Store user info in ASGI scope for WSGI compatibility
            # This ensures Flask RBAC middleware can access user information reliably
            request.scope["mlflow_oidc_auth"] = {"username": username, "is_admin": request.state.is_admin}
            logger.debug(f"User {username} (admin: {request.state.is_admin}) accessing {path}")

            # Proceed to the next middleware/handler
            return await call_next(request)
        else:
            # Authentication failed - for API routes return 401 JSON, else redirect to login
            logger.info(f"Authentication failed for {path}: {error_msg}")
            if path.startswith("/api"):
                return JSONResponse(status_code=401, content={"detail": "Authentication required"})
            return await self._handle_auth_redirect(request)
