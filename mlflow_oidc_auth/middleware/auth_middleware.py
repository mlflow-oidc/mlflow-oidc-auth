"""
Authentication Middleware for FastAPI.

This middleware handles authentication (verifying who the user is) and sets
user context in request state for use by downstream middleware and handlers.
Authorization (what the user can do) is handled by RBACMiddleware.
"""

from typing import Optional, Tuple
import asyncio
import base64
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from cachetools import TTLCache
from fastapi import Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.routers._prefix import API_PATH_PREFIXES
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode

from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.auth import validate_token
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils.oidc_field_extraction import extract_username, extract_display_name, BEARER_TOKEN_SOURCE

logger = get_logger()

# Basic auth used to run synchronously on the ASGI event loop, which limited each worker to one
# database/hash verification at a time while also blocking every unrelated request (issue #244).
# The single-thread executor keeps that per-process concurrency bound when offloading: legacy
# scrypt hashes are CPU-intensive, and an unauthenticated caller must not be able to fan out
# enough concurrent verifications to exhaust the database pool.
_BASIC_AUTH_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mlflow-oidc-basic-auth")


def _authenticate_basic_auth_sync(username: str, password: str) -> bool:
    """Resolve the lazy store and verify one basic-auth credential in a worker thread."""
    return store.authenticate_user(username, password)


# Why an authenticated-looking request was turned away. Reported separately because a deleted
# account and a deactivated one are different operational events, and an operator reading the
# audit log should not have to guess which happened (issue #306).
DENIAL_UNKNOWN_USER = "unknown_user"
DENIAL_INACTIVE = "inactive"
DENIAL_LOOKUP_ERROR = "lookup_error"

DENIAL_AUDIT_EVENTS = {
    DENIAL_UNKNOWN_USER: "auth.denied_unknown_user",
    DENIAL_INACTIVE: "auth.denied_inactive",
    DENIAL_LOOKUP_ERROR: "auth.denied_lookup_error",
}

# A revoked-but-unexpired cookie keeps arriving: a browser tab left open on the SPA issues
# subresource fetches, polls and telemetry until the cookie expires, and each one is denied. One
# audit event per request would let a single stale session write thousands of identical entries,
# burying real events — and would let anyone holding such a cookie dilute the forensic record
# deliberately. So the *first* denial for a (username, reason) is recorded and repeats within the
# window are suppressed; the denial itself still happens every time and is still visible in the
# request log.
#
# Bounded as well as time-limited: an attacker rotating usernames must not be able to grow this
# without limit. Eviction only costs a duplicate audit entry, never a missed denial.
DENIAL_AUDIT_WINDOW_SECONDS = 60
_denial_audit_seen: TTLCache = TTLCache(maxsize=1024, ttl=DENIAL_AUDIT_WINDOW_SECONDS)
_denial_audit_lock = threading.Lock()


def _should_audit_denial(username: str, reason: str) -> bool:
    """Whether this denial is the first of its kind within the window.

    Thread-safe: several ASGI worker threads can be denying the same stale session at once, and
    ``TTLCache`` is not itself synchronised.
    """
    key = (username, reason)
    with _denial_audit_lock:
        if key in _denial_audit_seen:
            return False
        _denial_audit_seen[key] = True
        return True


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

            # Store initialization, SQLAlchemy, and password verification are synchronous. Keep
            # them off the ASGI event loop; the dedicated executor preserves the previous
            # one-verification-per-process bound.
            if await asyncio.get_running_loop().run_in_executor(
                _BASIC_AUTH_EXECUTOR,
                _authenticate_basic_auth_sync,
                username.lower(),
                password,
            ):
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
        #
        # Asked of the provider that actually validated the token, not of the flat variables
        # (#313). Those two no longer describe what was enforced: a registry-configured provider
        # carries its own audience and issuer, so reading the flat pair would both credit
        # scoping that was never applied — leftover variables from before the registry — and
        # deny provisioning to a registry-only deployment that pins both properly.
        try:
            from mlflow_oidc_auth.auth import resolve_token_provider

            provider = resolve_token_provider(token)
        except Exception as e:
            logger.warning("Provisioning skipped; could not identify the provider for %s: %s", username, type(e).__name__)
            return

        if not (provider.audience and provider.issuer):
            logger.warning(
                "OIDC_PROVISION_ON_BEARER_AUTH is set but provider '%s' pins %s; refusing to provision %s from an under-scoped token",
                provider.id,
                "no audience" if not provider.audience else "no issuer",
                username,
            )
            return

        # A Kubernetes service account never reaches here: _authenticate_bearer_token sends it
        # to _authenticate_service_account instead, which applies its own policy (#314). Guarded
        # rather than assumed, because the two resolve the provider independently.
        if provider.type == "k8s":
            logger.debug("Not provisioning %s here; a service account is handled on its own path", username)
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

        # Admin is conferred from a token only when the operator has explicitly opted in *and*
        # the asserting provider is allowed to say so (#318). Without the second half, a provider
        # configured ``admin_source: none`` — the answer for a tenant whose group names you do
        # not control — could still mint administrators through this path.
        from mlflow_oidc_auth.provisioning_policy import admin_from_claims

        is_admin = is_admin_claim and config.OIDC_TRUST_BEARER_GROUP_CLAIMS and admin_from_claims(provider, user_groups, config.OIDC_ADMIN_GROUP_NAME)
        display_name, display_name_error = extract_display_name(payload, source=BEARER_TOKEN_SOURCE)
        if display_name_error:
            logger.debug("Bearer provisioning of %s falling back to username as display name: %s", username, display_name_error)
            display_name = username
        try:
            import mlflow_oidc_auth.user as user_module

            user_module.create_user(username=username, display_name=display_name, is_admin=is_admin)
            user_module.populate_groups(group_names=user_groups)
            user_module.update_user(username=username, group_names=user_groups)
            logger.info("Provisioned bearer user %s (admin=%s, groups=%d) on first authentication", username, is_admin, len(user_groups))
        except Exception as e:
            # A concurrent first request may have inserted the row (unique constraint) — benign.
            logger.warning("Bearer provisioning of %s did not complete (may already exist): %s", username, type(e).__name__)

    @staticmethod
    def _provider_for(token: str):
        """The provider that validated ``token``, or None if it cannot be identified."""
        try:
            from mlflow_oidc_auth.auth import resolve_token_provider

            return resolve_token_provider(token)
        except Exception as e:
            logger.debug("Could not identify the provider for a bearer token: %s", type(e).__name__)
            return None

    def _authenticate_service_account(self, token: str, payload, provider) -> Tuple[bool, Optional[str], str]:
        """Authenticate a Kubernetes service account (#314).

        The namespace allowlist is checked **here, on every request**, not only when the user
        record is created. Checking it at provisioning alone would mean removing a namespace from
        the list revoked nothing: every service account that had authenticated once would keep
        its user row, its group and its permissions, while kubelet went on renewing its token. It
        is a tuple membership test against configuration already in memory, so enforcing it per
        request costs no query and no round trip.
        """
        from mlflow_oidc_auth.kubernetes import ServiceAccountError, namespace_is_allowed, parse_service_account

        try:
            account = parse_service_account(payload.get("sub"))
        except ServiceAccountError as e:
            logger.warning("Rejecting a token from provider '%s': %s", provider.id, e)
            return False, None, "Invalid service account token"

        if not namespace_is_allowed(account.namespace, provider.namespace_allowlist):
            logger.info(
                "Service account %s/%s presented a valid token, but its namespace is not in provider '%s' namespace_allowlist",
                account.namespace,
                account.name,
                provider.id,
            )
            if _should_audit_denial(account.username, "namespace_not_allowed"):
                emit_audit_event(
                    "auth.denied_namespace",
                    actor=account.username,
                    resource_type="user",
                    resource_id=account.username,
                    detail={"provider": provider.id, "namespace": account.namespace},
                    status="denied",
                )
            return False, None, "Service account namespace is not allowed"

        self._provision_service_account(account, provider)
        logger.debug("Service account %s authenticated via bearer token", account.username)
        return True, account.username, ""

    def _provision_service_account(self, account, provider) -> None:
        """Create the user record for a Kubernetes service account (#314).

        Called only after :meth:`_authenticate_service_account` has allowed the namespace, so
        this is the record-keeping half: the authorization decision lives on the request path,
        where it is re-made every time rather than frozen into a row.

        The account is always non-admin. There is no claim a cluster could assert that should
        confer administrator rights on an MLflow deployment, and ``OIDC_TRUST_BEARER_GROUP_CLAIMS``
        deliberately does not reach this path: it opts into trusting a *directory's* group names,
        which is a different statement from trusting a namespace.
        """
        # ``OIDC_PROVISION_ON_BEARER_AUTH`` is deliberately *not* consulted. That flag is the
        # opt-in for provisioning from an OIDC token, where the alternative is trusting whatever
        # groups an arbitrary token from the corporate IdP carries. Here the opt-in already
        # exists and is narrower: a provider the operator configured, and a namespace they named
        # in its allowlist. Requiring a second, OIDC-named flag as well would mean the documented
        # setup returns 401 for a valid token with nothing pointing at why.
        username = account.username
        try:
            if store.has_user(username):
                return
        except Exception as e:
            logger.warning("Provisioning skipped; has_user check failed for %s: %s", username, type(e).__name__)
            return

        group = account.group
        display_name = f"{account.namespace}/{account.name} (service account)"
        try:
            import mlflow_oidc_auth.user as user_module

            user_module.create_user(username=username, display_name=display_name, is_admin=False, is_service_account=True)
            user_module.populate_groups(group_names=[group])
            user_module.update_user(username=username, group_names=[group])
            logger.info("Provisioned service account %s from namespace %s", username, account.namespace)
            emit_audit_event(
                "user.provisioned",
                actor=username,
                resource_type="user",
                resource_id=username,
                detail={"provider": provider.id, "namespace": account.namespace, "service_account": account.name, "is_service_account": True},
            )
        except Exception as e:
            # A concurrent first request may have inserted the row — benign.
            logger.warning("Provisioning of service account %s did not complete (may already exist): %s", username, type(e).__name__)

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

            provider = self._provider_for(token)

            if provider is not None and provider.type == "k8s":
                # A service-account token names itself in ``sub`` and carries no email or
                # preferred_username, so the OIDC username fields do not apply to it (#314). The
                # identity is derived here rather than from OIDC_USERNAME_FIELD: a global field
                # list that had to include ``sub`` to make this work would also change how every
                # other provider's tokens are named.
                return self._authenticate_service_account(token, payload, provider)

            # Extract username from configured fields. extract_username guarantees a
            # non-empty, normalized username whenever it returns no error.
            username, error_msg = extract_username(payload, source=BEARER_TOKEN_SOURCE)
            if error_msg:
                return False, None, error_msg

            self._maybe_provision_bearer_user(username, token, payload)
            logger.debug(f"User {username} authenticated via bearer token")
            return True, username, ""
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
                    session_id = session.get("session_id")
                    if not session_id:
                        # No server-side session id. A cookie predating #310 lands here and is
                        # treated as unauthenticated, which is the deliberate upgrade path: the
                        # old format carried the username itself, so honouring it would keep
                        # exactly the sessions that cannot be revoked.
                        return False, None, "No session authentication"

                    resolved = store.resolve_auth_session(session_id)
                    if resolved is None:
                        # Unknown, revoked or expired — indistinguishable on purpose.
                        session.clear()
                        return False, None, "Session not recognised"

                    username = resolved.username
                    # Stash the resolved row so dispatch does not look the user up again. The
                    # join already returned admin and active, so the session path costs one
                    # statement rather than two (#305 budget).
                    request.state.resolved_session = resolved

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
            True only if the user is an administrator **and** may authenticate. A deactivated or
            deleted admin returns False: the raw flag is preserved inside
            :meth:`_get_user_auth_state` so the denial path can report accurately, but a method
            named "is this an admin" must never answer True for an account that is being turned
            away (issue #306 review).
        """
        is_admin, is_active, _ = self._get_user_auth_state(username)
        return is_admin and is_active

    def _get_user_auth_state(self, username: str) -> Tuple[bool, bool, str]:
        """Read the facts the auth path needs about a user, in one lookup.

        All come off the profile row that is already fetched on every authenticated request, so
        ``active`` costs nothing: it is in the ``load_only`` list added by #333, and the
        per-request statement count stays at the #305 budget of 2.

        Args:
            username: Username to check

        Returns:
            ``(is_admin, is_active, denial_reason)``. ``denial_reason`` is ``""`` when the user
            may authenticate, and otherwise names why not, so the caller can report a deleted
            account differently from a deactivated one (issue #306).

            Any failure yields ``(False, False, ...)``: an account that cannot be read is not an
            account that may authenticate. Erring the other way would let a lookup error grant
            access, which is the fallback this repository forbids.
        """
        try:
            user = store.get_user_profile(username)
        except MlflowException as e:
            if e.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
                # Routine, not exceptional: the account was deleted while its signed cookie was
                # still valid. The browser will keep presenting it until the cookie expires, so
                # logging this at ERROR would fill the log with something nobody can act on.
                # Not logged here at all — ``dispatch`` logs the denial once, with the path and
                # the reason, and two lines per request is twice the volume for one event.
                return False, False, DENIAL_UNKNOWN_USER
            logger.error("Error reading auth state for %s: %s", username, e)
            return False, False, DENIAL_LOOKUP_ERROR
        except Exception as e:
            logger.error("Error reading auth state for %s: %s", username, e)
            return False, False, DENIAL_LOOKUP_ERROR

        if not user:
            return False, False, DENIAL_UNKNOWN_USER
        if not user.active:
            return bool(user.is_admin), False, DENIAL_INACTIVE
        return bool(user.is_admin), True, ""

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
            resolved = getattr(request.state, "resolved_session", None)
            if resolved is not None:
                # Already read, in the same statement that validated the session.
                is_admin, is_active = resolved.is_admin, resolved.is_active
                denial_reason = "" if is_active else DENIAL_INACTIVE
            else:
                is_admin, is_active, denial_reason = self._get_user_auth_state(username)

            # A deprovisioned user holds a signed cookie or a valid token that has not expired
            # yet, so credentials alone still check out. Directories deactivate rather than
            # delete (Entra sends PATCH active:false), which makes this the state a
            # deprovisioned account actually lands in — it has to be denied here, on every
            # path, rather than left to downstream permission checks (issue #311).
            if not is_active:
                logger.info("Authentication denied for %s on %s (%s)", username, path, denial_reason)
                if _should_audit_denial(username, denial_reason):
                    emit_audit_event(
                        DENIAL_AUDIT_EVENTS.get(denial_reason, DENIAL_AUDIT_EVENTS[DENIAL_LOOKUP_ERROR]),
                        actor=username,
                        resource_type="user",
                        resource_id=username,
                        status="denied",
                    )
                return await self._deny(request, path)

            # Set user context in request state for downstream middleware/handlers
            request.state.username = username
            request.state.is_admin = is_admin

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
            return await self._deny(request, path)

    async def _deny(self, request: Request, path: str) -> Response:
        """Turn an unauthenticated request away.

        Shared by "no valid credentials" and "credentials belong to an inactive user" so the
        two are indistinguishable to the caller: an inactive account must not be detectable by
        the shape of its rejection.

        Args:
            request: FastAPI request object
            path: Request path, already extracted by the caller

        Returns:
            A 401, a 403 or a redirect, depending on the surface.
        """
        # Treat certain non-/api routes as API-style endpoints (no redirects)
        # so callers get an HTTP error instead of a redirected 200.
        # "/ajax-api" is the same REST surface under the prefix the web UI
        # calls; it must 401 rather than redirect, just like "/api".
        if path.startswith(API_PATH_PREFIXES):
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
