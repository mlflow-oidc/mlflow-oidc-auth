"""
Authentication Middleware for FastAPI.

This middleware handles authentication (verifying who the user is) and sets
user context in request state for use by downstream middleware and handlers.
Authorization (what the user can do) is handled by RBACMiddleware.
"""

from typing import Optional, Tuple
import base64
import time

from fastapi import Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.auth import validate_token
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils.oidc_field_extraction import extract_username

logger = get_logger()


def normalize_workspace_header(raw_workspace: Optional[str]) -> Optional[str]:
    """Normalize the X-MLFLOW-WORKSPACE header the way MLflow itself does.

    MLflow's ``_normalize_workspace`` strips the value and treats an empty result as absent,
    then resolves an absent workspace to the default one. The auth layer must agree exactly:
    if it derived a different name than the tracking layer stores into, permissions would be
    checked against one workspace while the resource landed in another.

    Returns the trimmed name, or None when the header is missing, empty, or whitespace-only.
    """
    if not raw_workspace:
        return None
    return raw_workspace.strip() or None


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
        unprotected_prefixes = (
            "/health",
            "/login",
            "/callback",
            "/oidc/static",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/oidc/ui",
            # MLflow's React bundle is served from /static-files/<path:path> with
            # content-addressed (hashed) filenames and ships publicly on PyPI.
            # Letting it load unauthenticated lets a session-expired SPA finish
            # loading chunks instead of dying with ChunkLoadError; the next
            # navigation will redirect through the IdP for re-auth.
            "/static-files",
        )
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
            logger.warning("Basic auth error: %s: %s", type(e).__name__, e)
            logger.debug("Basic auth error traceback", exc_info=True)
            return False, None, "Invalid basic auth format"

    def _maybe_provision_bearer_user(self, username: str, token: str, payload) -> None:
        """Issue #262 (Layer 2): create a permission-DB record on first bearer authentication.

        API-first users who never logged in through the browser have no user record, so the
        after-request MANAGE grant on their first create fails and leaves an ownerless
        resource. When OIDC_PROVISION_ON_BEARER_AUTH is enabled, provision them here — before
        the request reaches the Flask hooks — mirroring the login flow.

        Hardened and conservative:
          * only when the token is scoped by BOTH audience and issuer (else refuse);
          * only when the user's group claim passes the same authorization gate as interactive
            login, so bearer is never more permissive than login;
          * NON-admin unless OIDC_TRUST_BEARER_GROUP_CLAIMS is explicitly enabled;
          * a one-time insert guarded by has_user (no per-request re-sync / demotion);
          * failures never grant access — an unprovisioned user is still denied creates by the
            before_request existence gate.
        """
        if not config.OIDC_PROVISION_ON_BEARER_AUTH:
            return
        try:
            if store.has_user(username):
                return
        except Exception as e:
            logger.warning("Provisioning skipped; has_user check failed for %s: %s", username, type(e).__name__)
            return

        # Hardening: never provision from a token that is not scoped by both aud and iss.
        if not (config.OIDC_AUDIENCE and config.OIDC_ISSUER):
            logger.warning(
                "OIDC_PROVISION_ON_BEARER_AUTH is set but OIDC_AUDIENCE/OIDC_ISSUER are not both configured; refusing to provision %s from an under-scoped token",
                username,
            )
            return

        # Derive groups from the token, mirroring the login flow's group resolution.
        try:
            if config.OIDC_GROUP_DETECTION_PLUGIN:
                import importlib

                user_groups = importlib.import_module(config.OIDC_GROUP_DETECTION_PLUGIN).get_user_groups(token)
            else:
                user_groups = payload.get(config.OIDC_GROUPS_ATTRIBUTE, [])
            if isinstance(user_groups, str):
                user_groups = [user_groups]
        except Exception as e:
            logger.warning("Failed to read groups for bearer provisioning of %s: %s", username, type(e).__name__)
            return

        # Same authorization gate as interactive login (routers/auth.py): the user must be an
        # admin-group or allowed-group member. Otherwise do NOT provision — a bearer token must
        # never be able to create an account that interactive login would reject.
        is_admin_claim = any(group in user_groups for group in config.OIDC_ADMIN_GROUP_NAME)
        if not is_admin_claim and not any(group in user_groups for group in config.OIDC_GROUP_NAME):
            logger.info("Bearer user %s is in no authorized group; not provisioning (parity with interactive login)", username)
            return

        # Admin is conferred from a token only when the operator has explicitly opted in.
        is_admin = is_admin_claim and config.OIDC_TRUST_BEARER_GROUP_CLAIMS
        display_name = payload.get("name") or username
        try:
            import mlflow_oidc_auth.user as user_module

            user_module.create_user(username=username, display_name=display_name, is_admin=is_admin)
            user_module.populate_groups(group_names=user_groups)
            user_module.update_user(username=username, group_names=user_groups)
            logger.info("Provisioned bearer user %s (admin=%s, groups=%d) on first authentication", username, is_admin, len(user_groups))
        except Exception as e:
            # A concurrent first request may have inserted the row (unique constraint) — benign.
            logger.warning("Bearer provisioning of %s did not complete (may already exist): %s", username, type(e).__name__)

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

            # Extract username from configured fields
            username, error_msg = extract_username(payload)
            if error_msg:
                return False, None, error_msg

            if username:
                username = username.lower()
                self._maybe_provision_bearer_user(username, token, payload)
                logger.debug(f"User {username} authenticated via bearer token")
                return True, username, ""
            else:
                return False, None, "Invalid token payload"
        except Exception as e:
            logger.warning("Bearer auth error: %s: %s", type(e).__name__, e)
            logger.debug("Bearer auth error traceback", exc_info=True)
            return False, None, "Invalid token"

    async def _authenticate_session(self, request: Request) -> Tuple[bool, Optional[str], str]:
        """
        Authenticate using session.

        Enforces the IdP-issued ``expires_at`` (set at OIDC callback) so a session
        cannot outlive the underlying token. When ``OIDC_USE_REFRESH_TOKEN`` is
        enabled and a refresh token is stored, an expired session is silently
        refreshed against the IdP before being rejected.

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
                    if not username:
                        return False, None, "No session authentication"

                    if self._is_session_expired(session):
                        # Try a silent refresh first; only force re-login if it fails.
                        from mlflow_oidc_auth.routers.auth import refresh_session_with_idp

                        refreshed = await refresh_session_with_idp(session)
                        if not refreshed:
                            logger.info(
                                "Session expired for user %s; clearing session to force re-authentication",
                                username,
                            )
                            session.clear()
                            return False, None, "Session expired"
                        logger.debug(f"Session for {username} refreshed against IdP")

                    logger.debug(f"User {username} authenticated via session")
                    return True, username, ""
                except Exception as session_error:
                    logger.debug("Session access error: %s", type(session_error).__name__)
                    return False, None, "Session access failed"
            else:
                logger.debug("Session middleware not available - no session attribute")
                return False, None, "Session middleware not available"
        except Exception as e:
            logger.debug("Session check error: %s", type(e).__name__)
            return False, None, "Session error"

        return False, None, "No session authentication"

    @staticmethod
    def _is_session_expired(session) -> bool:
        """Return True when the IdP-issued ``expires_at`` (minus leeway) is in the past.

        Returns False when no expiry is recorded — older sessions predating this
        feature should keep working until the cookie TTL takes them out, instead
        of being summarily logged out at deploy time.
        """

        expires_at = session.get("expires_at")
        if not isinstance(expires_at, (int, float)):
            return False
        leeway = max(0, config.OIDC_SESSION_EXPIRY_LEEWAY_SECONDS)
        return time.time() >= float(expires_at) - leeway

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
            user = store.get_user_profile(username)
            return user.is_admin if user else False
        except Exception as e:
            logger.error(f"Error checking admin status for {username}: {e}")
            return False

    async def _handle_auth_redirect(self, request: Request) -> Response:
        """
        Handle authentication redirect for unauthenticated users.

        Forwards the original request path (and query string) as ``?next=`` so
        the post-login callback can return the user to where they were instead
        of dumping them at the root.

        Args:
            request: FastAPI request object

        Returns:
            Appropriate response (redirect or auth page)
        """
        # Import here to avoid circular imports
        from urllib.parse import quote

        from mlflow_oidc_auth.utils import get_base_path

        base_path = await get_base_path(request)

        # Reconstruct the original target so the user is returned to it after
        # IdP login. We can only see path + query server-side; the SPA layer
        # also forwards the URL fragment for hash-routed apps like MLflow.
        target = request.url.path
        query = request.url.query
        if query and isinstance(query, str):
            target = f"{target}?{query}"
        next_param = f"?next={quote(target, safe='')}"

        if config.AUTOMATIC_LOGIN_REDIRECT:
            login_url = f"{base_path}/login{next_param}"
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
            # Extract workspace header only when workspaces are enabled (per WSFND-02)
            workspace = None
            if config.MLFLOW_ENABLE_WORKSPACES:
                workspace = normalize_workspace_header(request.headers.get("x-mlflow-workspace"))

            request.scope[AUTH_CONTEXT_KEY] = AuthContext(
                username=username,
                is_admin=request.state.is_admin,
                workspace=workspace,
            )
            logger.debug(f"User {username} (admin: {request.state.is_admin}) accessing {path}")

            # Proceed to the next middleware/handler
            return await call_next(request)
        else:
            # Authentication failed - for API routes return 401 JSON, else redirect to login
            logger.info(f"Authentication failed for {path}: {error_msg}")
            # Treat certain non-/api routes as API-style endpoints (no redirects)
            # so callers get an HTTP error instead of a redirected 200.
            if path.startswith("/api"):
                return JSONResponse(status_code=401, content={"detail": "Authentication required"})
            if path.startswith("/oidc/trash"):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Administrator privileges required for this operation"},
                )
            # Only redirect top-level navigation requests. Subresource fetches
            # (chunks, fetch/XHR, telemetry) must get 401 — otherwise the
            # browser silently follows the 302 and hands HTML to the JS chunk
            # loader / JSON.parse, breaking the SPA mid-session.
            if not self._is_document_request(request):
                return JSONResponse(status_code=401, content={"detail": "Authentication required"})
            return await self._handle_auth_redirect(request)

    @staticmethod
    def _is_document_request(request: Request) -> bool:
        """Return True when the request is a top-level navigation (HTML document fetch).

        Uses the ``Sec-Fetch-Dest`` header (sent by all modern browsers) and falls
        back to the ``Accept`` header for clients that don't set it. Only document
        requests should receive a 302 redirect to the login flow; everything else
        (script/style/image/fetch/XHR) needs a 401 so the SPA can react instead
        of receiving HTML in place of expected JSON or JS.
        """

        sec_fetch_dest = request.headers.get("sec-fetch-dest", "").lower()
        if sec_fetch_dest:
            return sec_fetch_dest == "document"
        # Older clients without Sec-Fetch-Dest: trust Accept. fetch()/XHR usually
        # send `application/json` or `*/*`; navigations send `text/html,...`.
        accept = request.headers.get("accept", "").lower()
        return "text/html" in accept
