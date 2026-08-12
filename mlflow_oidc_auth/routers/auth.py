"""
Authentication router for FastAPI application.

This router handles OIDC authentication flows including login, logout, and callback.
"""

import secrets
import time
from collections.abc import Awaitable
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode, urlparse

from authlib.jose.errors import BadSignatureError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.authorization_response import IssuerMismatchError, validate_response_issuer
from mlflow_oidc_auth.identity_resolution import IdentityDecision, Resolution, resolve_identity
from mlflow_oidc_auth.provisioning_policy import admin_from_claims, apply_provisioning_policy, groups_to_apply
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.provider_registry import DEFAULT_PROVIDER_ID
from mlflow_oidc_auth.oauth import PKCEUnsupportedError, assert_pkce_supported, get_client, is_oidc_configured, oauth
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import get_configured_or_dynamic_redirect_uri, extract_username, extract_display_name

from ._prefix import UI_ROUTER_PREFIX

logger = get_logger()

# Lifetime for a server-side session when the cookie itself carries no expiry. A cookie with no
# max_age lasts until the browser closes, which is unbounded from the server's point of view — and
# a row that never expires is a row that can never be swept (#310).
DEFAULT_SESSION_LIFETIME_SECONDS = 14 * 24 * 60 * 60


auth_router = APIRouter(
    tags=["auth"],
    responses={404: {"description": "Not found"}},
)

CALLBACK = "/callback"
LOGIN = "/login"
PROVIDERS = "/providers"
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


async def _call_authorize_access_token(request: Request, provider_id: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Invoke authorize_access_token while supporting sync or async implementations.

    The exchange goes to the token endpoint of the provider the attempt started at — never one
    derived from the response, which is the other half of the RFC 9207 defence.
    """

    client = _client_for_exchange(provider_id)
    token_call = client.authorize_access_token(request)  # type: ignore
    return await _maybe_await(token_call)


def _client_for_exchange(provider_id: Optional[str]):
    """The client whose token endpoint an authorization code may be exchanged at.

    A named provider resolves to its own client or to nothing. Falling back to ``oauth.oidc``
    would post a code minted by one issuer to another issuer's token endpoint, with that other
    issuer's client id — handing one IdP a credential belonging to a different one, which is the
    confusion the rest of this flow exists to prevent.
    """
    if provider_id and provider_id != DEFAULT_PROVIDER_ID:
        client = get_client(provider_id)
        if client is None:
            raise RuntimeError(f"No registered OAuth client for provider '{provider_id}'")
        return client
    # ``default`` keeps resolving to the legacy client, for a deployment that never adopted the
    # registry.
    return get_client(DEFAULT_PROVIDER_ID) or oauth.oidc


async def _authorize_access_token_with_key_refresh(
    request: Request,
    provider_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Exchange the code for tokens; on failure refresh the JWKS and raise what actually went wrong.

    This used to retry the exchange once. **The retry could never succeed**, and it destroyed the
    diagnosis of every failure it touched: authlib removes the per-attempt state from the session
    — the PKCE verifier, the nonce, the redirect URI — *before* it sends the token request
    (``starlette_client/apps.py``: ``clear_state_data`` then ``fetch_access_token``). A second
    call therefore finds nothing, raises ``MismatchingStateError``, and that error replaced the
    real one, so a provider rejecting the exchange with ``invalid_grant`` was reported to the
    operator as a CSRF state mismatch. The authorization code is single-use in any case, so even
    with the state intact the provider would refuse the second attempt.

    The JWKS refresh is kept and still does its job: a signing key rotated mid-session is picked
    up so the **next** login works, rather than every login failing until the cache expires. What
    is gone is the pretence that this attempt can be salvaged.

    Returns:
        The token response, or None if authlib returned nothing.

    Raises:
        Exception: Whatever the exchange raised, unchanged.
    """

    try:
        return await _call_authorize_access_token(request, provider_id)
    except BadSignatureError as exc:
        logger.warning("OIDC token exchange failed with bad signature: %s", exc)
        # Most likely a rotated signing key. Refresh so the next login is not affected too.
        await _refresh_oidc_jwks()
        raise
    except Exception as exc:
        logger.warning("OIDC token exchange failed: %s", exc)
        await _refresh_oidc_jwks()
        raise


async def refresh_session_with_idp(session) -> bool:
    """Attempt to refresh an expired session against the IdP using the stored refresh token.

    Returns True on success (session updated in place with new ``expires_at`` and,
    when rotated, a new ``refresh_token``). Returns False on any failure — the
    caller is expected to clear the session and force re-authentication.

    No-op (returns False) when ``OIDC_USE_REFRESH_TOKEN`` is disabled or no
    refresh token is stored, so this is safe to call unconditionally from the
    middleware.
    """

    if not config.OIDC_USE_REFRESH_TOKEN:
        return False

    refresh_token = session.get("refresh_token") if session is not None else None
    if not refresh_token:
        return False

    fetch_fn = getattr(oauth.oidc, "fetch_access_token", None)
    if fetch_fn is None:
        logger.warning("OIDC client has no fetch_access_token; cannot refresh session")
        return False

    try:
        new_token = await _maybe_await(fetch_fn(grant_type="refresh_token", refresh_token=refresh_token))
    except Exception as exc:
        logger.warning("OIDC refresh token exchange failed: %s", exc)
        return False

    if not new_token:
        return False

    _persist_session_auth(session, new_token)
    return True


def _extract_session_expiry(token_response: dict[str, Any]) -> Optional[int]:
    """Extract the session expiry timestamp (Unix seconds) from an OIDC token response.

    Prefers ``expires_at`` (set by Authlib from ``expires_in``), then the ``exp``
    claim of the validated id_token, then falls back to computing
    ``now + expires_in``. Returns None when no expiry information is available
    (in which case the caller should leave the session unchanged so behaviour
    matches the legacy ~14-day cookie window).
    """

    expires_at = token_response.get("expires_at")
    if isinstance(expires_at, (int, float)) and expires_at > 0:
        return int(expires_at)

    userinfo = token_response.get("userinfo") or {}
    id_token_exp = userinfo.get("exp")
    if isinstance(id_token_exp, (int, float)) and id_token_exp > 0:
        return int(id_token_exp)

    expires_in = token_response.get("expires_in")
    if isinstance(expires_in, (int, float)) and expires_in > 0:
        return int(time.time()) + int(expires_in)

    return None


def _persist_session_auth(session, token_response: dict[str, Any]) -> None:
    """Store IdP-issued expiry (and optionally the refresh token) in the session.

    Called after a successful OIDC token exchange. ``OIDC_USE_REFRESH_TOKEN``
    gates persistence of the refresh token because storing one in a signed
    (but not encrypted) cookie has security implications, and many enterprises
    disallow ``offline_access`` outright.
    """

    expiry = _extract_session_expiry(token_response)
    if expiry is not None:
        session["expires_at"] = expiry
    else:
        # No reliable expiry from the IdP; remove any stale value from a prior login.
        session.pop("expires_at", None)

    if config.OIDC_USE_REFRESH_TOKEN:
        refresh_token = token_response.get("refresh_token")
        if refresh_token:
            session["refresh_token"] = refresh_token
        # If the response has no refresh_token, keep the existing one. Many
        # IdPs only emit refresh_token on the initial token exchange and reuse
        # it across subsequent refreshes (Microsoft Entra, some Keycloak
        # configs, etc.). Popping it here would break the next refresh.
    else:
        session.pop("refresh_token", None)


async def _iss_parameter_supported(provider) -> bool:
    """Whether the provider advertises ``authorization_response_iss_parameter_supported``.

    RFC 9207 is recent and plenty of deployed servers do not implement it, so a missing ``iss``
    is only fatal when the provider says it always sends one. Discovery being unreachable reads
    as "does not advertise": this decides how strict to be about a *missing* parameter, and a
    mismatch is refused either way.
    """
    client = get_client(provider.id)
    loader = getattr(client, "load_server_metadata", None)
    if loader is None:
        return False
    try:
        metadata = await loader() or {}
    except Exception as exc:
        logger.debug("Could not load metadata for the RFC 9207 check on '%s': %s", provider.id, exc)
        return False
    return bool(metadata.get("authorization_response_iss_parameter_supported"))


def _current_groups(username: str) -> Optional[list]:
    """The user's groups as stored, for an additive sync, or None when they cannot be read.

    None rather than an empty list: an additive sync that reads an unreadable membership as empty
    writes only the claimed groups, which *deletes* everything managed elsewhere — the exact
    thing the additive mode exists to prevent.
    """
    try:
        return list(store.get_groups_for_user(username))
    except Exception as exc:
        logger.warning("Could not read current groups for %s: %s", username, exc)
        return None


def _sanitize_next(value: Optional[str]) -> Optional[str]:
    """Validate a ``next`` redirect target. Only same-origin relative paths are
    accepted to prevent open-redirect attacks. Returns None on rejection.

    Accepts: ``/users``, ``/oidc/ui/groups``, ``/#/experiments/0``.
    Rejects: ``http://evil``, ``//evil``, ``javascript:...``, ``/\\evil.com``,
    ``/<tab>/evil.com``, and anything not starting with a single ``/``.
    """

    if not value:
        return None
    if not isinstance(value, str):
        return None
    if not value.startswith("/"):
        return None
    if value.startswith("//"):  # protocol-relative URL — would escape origin
        return None
    # Browsers do not read this the way a prefix check does. WHATWG parsing treats ``\`` as ``/``
    # for special schemes, so ``/\evil.com`` navigates to https://evil.com/, and leading C0
    # controls are stripped before parsing, so ``/%09/evil.com`` becomes ``//evil.com``. Both
    # start with a single ``/`` and would otherwise be accepted — and land the victim on an
    # attacker's page immediately after authenticating, which is the ideal phishing moment.
    if "\\" in value:
        return None
    if any(character in value for character in "\x00\t\n\r\x0b\x0c"):
        return None

    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return None
    return value


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


def _interactive_provider(provider_id: str):
    """The provider a browser login may use, or None.

    Only interactive providers are reachable here. A Kubernetes service-account issuer verifies
    tokens exactly as an OIDC provider does but has no authorization endpoint to redirect to, so
    naming it in a login URL must be a 404 rather than a broken redirect.
    """
    for provider in config.AUTH_PROVIDERS.interactive_providers():
        if provider.id == provider_id:
            return provider
    return None


@auth_router.get(PROVIDERS)
async def providers(request: Request):
    """List the providers a browser may log in with (#317's login picker reads this).

    Deliberately unauthenticated and deliberately thin: an id, a label and a login URL. It is
    reachable before anyone has logged in — that is its purpose — so it carries nothing beyond
    what a login page has to render, and nothing about how a provider is configured.
    """
    return JSONResponse(
        content={
            "providers": [
                {
                    "id": provider.id,
                    "display_name": provider.display_name or provider.id,
                    "type": provider.type,
                    "login_url": _absolute_path(request, f"{LOGIN}/{provider.id}"),
                }
                for provider in config.AUTH_PROVIDERS.interactive_providers()
            ]
        }
    )


def _absolute_path(request: Request, path: str) -> str:
    """Join ``path`` onto the deployment's own base URL.

    Prefers the configured redirect URI's origin over ``request.base_url``, which is the ``Host``
    header. These URLs are the buttons a login page offers, on an unauthenticated and cacheable
    endpoint: one poisoned response would otherwise send every later visitor to an attacker's
    host to authenticate.
    """
    configured = getattr(config, "OIDC_REDIRECT_URI", None)
    if configured:
        parsed = urlparse(configured)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}{path}"
    return str(request.base_url).rstrip("/") + path


@auth_router.get(f"{LOGIN}/{{provider_id}}")
async def login_with_provider(request: Request, provider_id: str):
    """Begin a login against a named provider (#316).

    The legacy ``/login`` is this with ``default``, so redirect URIs already registered at
    customers' IdPs keep working.
    """
    if _interactive_provider(provider_id) is None:
        raise HTTPException(status_code=404, detail="Unknown identity provider")
    return await _begin_login(request, provider_id)


@auth_router.get(LOGIN)
async def login(request: Request):
    """The legacy login, which is the ``default`` provider's.

    ``provider_id`` is deliberately not a parameter of this handler: FastAPI would expose it as a
    *query* parameter, and `?provider_id=` would then reach the flow without passing the
    interactive-provider check that the path-scoped route applies.
    """
    return await _begin_login(request, DEFAULT_PROVIDER_ID)


async def _begin_login(request: Request, provider_id: str):
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
        if not is_oidc_configured(provider_id):
            logger.error("OIDC is not properly configured for provider '%s'", provider_id)
            raise HTTPException(
                status_code=500,
                detail="OIDC authentication not available - configuration error",
            )

        # Get session for storing OAuth state (using Starlette's built-in session)
        session = request.session

        # Capture an optional ?next= return target so the callback can return the user to where
        # they were before the session expired. Validated to be a same-origin relative path;
        # anything else is dropped silently.
        next_target = _sanitize_next(request.query_params.get("next"))

        # The CSRF state, and everything this attempt needs to remember, is a row rather than a
        # cookie key (#316). One key held one attempt, so a second tab overwrote the first and
        # whichever came back second failed a check it should have passed — and nothing recorded
        # *which* provider had been asked, which is the question RFC 9207 exists to answer.
        oauth_state = store.create_auth_state(provider_id, redirect_after_login=next_target)

        # Get redirect URI (configured or dynamic). Use a safe fallback if dynamic calculation fails
        try:
            # The default provider keeps the legacy callback path: redirect URIs already
            # registered at customers' IdPs must not break. Every other provider gets its own,
            # which is what lets the callback know who is answering before it reads anything.
            callback_path = CALLBACK if provider_id == DEFAULT_PROVIDER_ID else f"{CALLBACK}/{provider_id}"
            redirect_url = get_configured_or_dynamic_redirect_uri(
                request=request,
                callback_path=callback_path,
                configured_uri=config.OIDC_REDIRECT_URI if provider_id == DEFAULT_PROVIDER_ID else None,
            )
        except Exception as e:
            logger.warning(f"Failed to get dynamic redirect URI: {e}")
            # Fallback to base_url + callback when request.url or other internals are not available in tests
            base = str(getattr(request, "base_url", "http://localhost:8000"))
            redirect_url = base.rstrip("/") + (CALLBACK if provider_id == DEFAULT_PROVIDER_ID else f"{CALLBACK}/{provider_id}")

        logger.debug(f"OIDC redirect URL: {redirect_url}")

        # ``default`` resolves to the legacy ``oauth.oidc`` client, so a deployment that never
        # adopted the registry keeps the client it already had.
        client = get_client(provider_id) or (oauth.oidc if provider_id == DEFAULT_PROVIDER_ID else None)
        if client is None:
            logger.error("No registered OAuth client for provider '%s'", provider_id)
            raise HTTPException(status_code=500, detail="OIDC authentication not available")

        # Redirect to OIDC provider
        try:
            if not hasattr(client, "authorize_redirect"):
                logger.error("OIDC client authorize_redirect method not available")
                raise HTTPException(status_code=500, detail="OIDC authentication not available")

            # PKCE is on by default (#312). Checked here so a provider that cannot do it says so
            # in one sentence, rather than as an unexplained ``invalid_grant`` at the exchange.
            await assert_pkce_supported(client, provider_id)

            return await client.authorize_redirect(  # type: ignore
                request,
                redirect_uri=redirect_url,
                state=oauth_state,
            )
        except HTTPException:
            raise
        except PKCEUnsupportedError as e:
            # The full sentence — provider id, the methods it advertises, the variable to change
            # — goes to the log, where the operator is. ``/login`` is unauthenticated, and every
            # other failure on this route answers with a fixed string; naming an internal
            # registry id to an anonymous caller would be the one exception.
            logger.error("%s", e)
            raise HTTPException(status_code=500, detail="OIDC login is misconfigured; see the server logs")
        except Exception as e:
            logger.error(f"Failed to initiate OAuth redirect: {e}")
            raise HTTPException(status_code=500, detail="Failed to initiate OIDC login")

    except HTTPException:
        # Preserve explicit HTTPExceptions raised above
        raise
    except Exception as e:
        logger.error(f"Error initiating OIDC login: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate OIDC login")


# Everything a completed login leaves in the cookie. All of it belongs to the user who logged
# in, so all of it has to go when a different login starts in the same browser.
_LOGIN_SESSION_KEYS = ("session_id", "username", "authenticated", "refresh_token", "expires_at")


def _retire_previous_login(session) -> None:
    """Drop — and revoke — whatever login this browser was already carrying.

    Called before the token exchange, not after. ``_persist_session_auth`` deliberately keeps an
    existing ``refresh_token`` when the new token response carries none (many IdPs only emit one
    on the first exchange), so anything still here when the exchange runs is inherited by the
    next user: their session would then be refreshed with the previous user's grant, and would
    die when *that* user was deprovisioned rather than when they were.

    The old session is revoked outright rather than merely forgotten. Its id is leaving the
    cookie either way, so nothing the user can still reach is being taken from them — and if
    this login fails, a session belonging to whoever was here before should not survive it.
    """
    previous_session_id = session.pop("session_id", None)
    for key in _LOGIN_SESSION_KEYS:
        session.pop(key, None)

    if previous_session_id:
        try:
            store.revoke_auth_session(previous_session_id)
        except Exception as exc:  # best effort: the cookie no longer names it regardless
            logger.warning("Could not revoke the previous session on re-login: %s", exc)


def _open_server_session(username: str) -> str:
    """Open a server-side session for ``username`` and return its opaque id.

    The row's lifetime mirrors the cookie's, so a session cannot outlive the credential that
    carries it, and an unbounded cookie still yields a bounded row — one that never expires
    could never be swept.
    """
    max_age = config.SESSION_COOKIE_MAX_AGE_SECONDS or DEFAULT_SESSION_LIFETIME_SECONDS
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max_age)
    return store.create_auth_session(username, expires_at=expires_at)


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
        # request.state is set by AuthMiddleware for an authenticated request; read it
        # defensively so logout never fails on the way out.
        username = getattr(getattr(request, "state", None), "username", None)
        session_id = session.get("session_id")

        if session_id:
            # Revoke the row, not just the cookie: clearing the cookie alone left the session
            # usable by anyone who had already copied it (#310).
            #
            # A failure here is not cosmetic and must not be swallowed by the handler's outer
            # ``except``: the cookie is gone from *this* browser, but the session stays live for
            # its full lifetime, and telling the user they are logged out when a copied cookie
            # still works is the worst of both. Surface it.
            #
            # Revoked *before* the cookie is cleared. Clearing first would delete the only copy
            # of the session id the browser has, so the 503 below would ask the user to retry
            # something they can no longer do: the retry would find no id, take the success
            # path, and leave the session live for its full lifetime.
            try:
                store.revoke_auth_session(session_id)
            except Exception as exc:
                logger.error("Logout could not revoke session for %s: %s", username or "<unknown>", exc)
                emit_audit_event(
                    "auth.logout_failed",
                    actor=username or "<unknown>",
                    detail={"reason": "revocation_failed"},
                    status="denied",
                )
                raise HTTPException(status_code=503, detail="Logout failed: the session could not be revoked. Please try again.")

        session.clear()

        if username:
            logger.info(f"User {username} logged out successfully")
            emit_audit_event("auth.logout", actor=username)

        # Check if OIDC provider supports logout
        if hasattr(oauth.oidc, "server_metadata"):
            metadata = getattr(oauth.oidc, "server_metadata", {})
            end_session_endpoint = metadata.get("end_session_endpoint")

            if end_session_endpoint:
                # Redirect to OIDC provider logout with post-logout redirect to auth page.
                # client_id is sent alongside post_logout_redirect_uri because providers
                # such as Keycloak (>= 18) reject RP-initiated logout with "Missing
                # parameters: id_token_hint" unless either id_token_hint or client_id is
                # present. The session is already cleared, so client_id is the reliable
                # choice here.
                post_logout_redirect = _build_ui_url(request, "/auth")
                params = urlencode(
                    {
                        "post_logout_redirect_uri": post_logout_redirect,
                        "client_id": config.OIDC_CLIENT_ID,
                    }
                )
                logout_url = f"{end_session_endpoint}?{params}"
                return RedirectResponse(url=logout_url, status_code=302)

        # Default redirect to auth page using the helper function
        auth_url = _build_ui_url(request, "/auth")
        return RedirectResponse(url=auth_url, status_code=302)

    except HTTPException:
        # Revocation failure. The user must be told, not redirected to a page that implies success.
        raise
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        # Still clear session even if redirect fails - redirect to auth page
        auth_url = _build_ui_url(request, "/auth")
        return RedirectResponse(url=auth_url, status_code=302)


@auth_router.get(f"{CALLBACK}/{{provider_id}}")
async def callback_for_provider(request: Request, provider_id: str):
    """Complete a login that began at ``/login/{provider_id}`` (#316).

    A separate path per provider so an authorization response cannot be delivered to a provider
    it did not come from — the first thing a mix-up attack tries.
    """
    if _interactive_provider(provider_id) is None:
        raise HTTPException(status_code=404, detail="Unknown identity provider")
    return await _complete_login(request, provider_id)


@auth_router.get(CALLBACK)
async def callback(request: Request):
    """The legacy callback, for a login that began at ``/login``.

    As with ``login``, the provider is not a query parameter — it comes from the path or not at
    all, so the 404 gate on the scoped route cannot be stepped around.
    """
    return await _complete_login(request, None)


async def _complete_login(request: Request, provider_id: Optional[str]):
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
        if not is_oidc_configured(provider_id or DEFAULT_PROVIDER_ID):
            logger.error("OIDC is not properly configured when processing the callback for '%s'", provider_id or DEFAULT_PROVIDER_ID)
            auth_error_url = _build_ui_url(
                request,
                "/auth",
                {"error": ["OIDC authentication not available - configuration error"]},
            )
            return RedirectResponse(url=auth_error_url, status_code=302)

        # Get session (using Starlette's built-in session)
        session = request.session

        # Process OIDC callback using FastAPI-native implementation. The state check inside is
        # what makes this callback attributable to a login this browser started; nothing
        # destructive may happen before it, or an unauthenticated cross-site GET to /callback
        # would log the victim out on demand.
        username, errors = await _process_oidc_callback_fastapi(request, session, provider_id=provider_id)

        if errors:
            # Handle authentication errors
            logger.error(f"OIDC callback errors: {errors}")

            # Redirect to auth page with error parameters for frontend display
            auth_error_url = _build_ui_url(request, "/auth", {"error": errors})

            logger.debug(f"Redirecting to auth error page: {auth_error_url}")
            return RedirectResponse(url=auth_error_url, status_code=302)

        if username:
            # Successful authentication. The cookie carries an opaque session id; the row it
            # names is what can be revoked (#310). ``username`` is no longer written to the
            # cookie — authenticating from it is precisely what could not be revoked.
            # Any previous login was already retired before the exchange, so nothing in this
            # cookie belongs to anyone else by the time the new session id is written.
            try:
                session["session_id"] = _open_server_session(username)
            except Exception as exc:
                # The user is provisioned earlier in this callback, so this should not happen —
                # but a login that cannot open a session must fail as a login, not as a stack
                # trace. The cookie is cleared so the failure cannot leave the browser holding a
                # half-authenticated state or another user's credentials.
                logger.error("Could not open a session for %s: %s", username, exc)
                session.clear()
                return RedirectResponse(url=_build_ui_url(request, "/auth", {"error": "session_error"}), status_code=302)
            session["authenticated"] = True

            logger.info(f"User {username} authenticated successfully via OIDC")
            emit_audit_event("auth.login", actor=username, detail={"method": "oidc"})

            # Redirect to UI home page or original destination
            default_redirect = session.pop("redirect_after_login", None)
            if not default_redirect:
                if config.DEFAULT_LANDING_PAGE_IS_PERMISSIONS:
                    default_redirect = _build_ui_url(request, "/user")
                else:
                    default_redirect = str(request.base_url).rstrip("/")

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
        # Resolve the opaque session id rather than reading a username from the cookie (#310).
        # A query here is fine: this is a status endpoint, not the per-request auth path.
        resolved = store.resolve_auth_session(session.get("session_id", ""))
        # ``resolve`` reports the active flag rather than filtering on it, so the middleware can
        # audit "deactivated" separately. Here a deactivated account is simply not authenticated
        # — reporting otherwise would render a logged-in UI that 401s on its first API call.
        username = resolved.username if resolved and resolved.is_active else None
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
        raise HTTPException(status_code=500, detail="Failed to get authentication status")


async def _process_oidc_callback_fastapi(request: Request, session, provider_id: Optional[str] = None) -> tuple[Optional[str], list[str]]:
    """
    Process the OIDC callback logic using FastAPI-native implementation.

    Args:
        request: FastAPI request object
        session: SessionManager instance
        provider_id: The provider whose callback path this is, when it is a scoped one. The
            attempt has to have been started at the same provider.

    Returns:
        Tuple of (username, error_list)
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

    # The attempt this callback belongs to. Consuming the row *is* the CSRF check: an unknown,
    # already-used or expired state finds nothing, so a replayed authorization response — from a
    # browser history entry, a proxy log, an attacker who captured the redirect — is refused
    # rather than exchanged a second time (#316).
    state = request.query_params.get("state")
    attempt = store.consume_auth_state(state or "")
    if attempt is None:
        errors.append("Invalid state parameter")
        return None, errors

    provider = config.AUTH_PROVIDERS.by_id(attempt.provider_id)
    if provider is None:
        # The provider was reconfigured or removed while this login was in flight. Refusing is
        # the only safe answer: there is no policy left to apply to the response.
        logger.error("Login attempt named provider '%s', which is no longer configured", attempt.provider_id)
        errors.append("Identity provider is no longer configured")
        return None, errors

    # The response has to arrive at the callback belonging to the provider the attempt started
    # at. ``provider_id`` is None on the legacy unscoped path, which belongs to ``default`` — not
    # to "whoever asks". Treating None as "no opinion" would let anyone who can deliver a
    # response to the unscoped URL opt out of the path check entirely.
    expected_callback_provider = provider_id if provider_id is not None else DEFAULT_PROVIDER_ID
    if provider.id != expected_callback_provider:
        logger.error("Login attempt for provider '%s' arrived at the callback for '%s'", provider.id, expected_callback_provider)
        errors.append("Invalid state parameter")
        return None, errors

    # RFC 9207: the response must say which issuer sent it, and it must be the one this
    # transaction began with. An authorization response is otherwise unattributable — code and
    # state look identical whichever authorization server produced them — which is the whole
    # mix-up attack.
    try:
        validate_response_issuer(
            request.query_params.getlist("iss") if hasattr(request.query_params, "getlist") else request.query_params.get("iss"),
            provider.issuer,
            iss_parameter_supported=await _iss_parameter_supported(provider),
        )
    except IssuerMismatchError as exc:
        logger.error("Refusing an authorization response for provider '%s': %s", provider.id, exc)
        errors.append("Authorization response came from an unexpected issuer")
        return None, errors

    session["redirect_after_login"] = attempt.redirect_after_login or session.get("redirect_after_login")

    # A new login supersedes whatever this browser was carrying, and must not inherit any of it:
    # _persist_session_auth below keeps an existing refresh token when the new response has none,
    # so anything left here would be inherited by the next user (#351).
    #
    # Both halves of the placement matter. After the state check, because retiring a session for
    # a callback that turned out to be forged would be a drive-by logout any page could trigger.
    # Before the exchange, because the exchange writes this login's tokens into the same cookie.
    _retire_previous_login(session)

    # Get authorization code
    code = request.query_params.get("code")
    if not code:
        errors.append("No authorization code received")
        return None, errors

    try:
        # Exchange authorization code for tokens
        try:
            exchange_client = _client_for_exchange(provider.id)
        except RuntimeError as client_error:
            logger.error("%s", client_error)
            errors.append("OIDC configuration error: OAuth client not properly initialized.")
            return None, errors

        if not hasattr(exchange_client, "authorize_access_token"):
            errors.append("OIDC configuration error: OAuth client not properly initialized.")
            return None, errors

        token_response = await _authorize_access_token_with_key_refresh(request, provider.id)

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

        # Extract user details using utility functions
        username, username_error = extract_username(userinfo)
        if username_error:
            errors.append(username_error)
            return None, errors

        # A missing display name doesn't block login — fall back to the username,
        # matching the bearer-token provisioning path (auth_middleware.py).
        display_name, display_name_error = extract_display_name(userinfo)
        if display_name_error:
            logger.debug("Falling back to username as display name for %s: %s", username, display_name_error)
            display_name = username

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

            # With jumpcloud, if the groups attribute is a single group, it will be sent as a string.
            # To process the groups correctly, bring the group into a list of groups.
            if isinstance(user_groups, str):
                user_groups = [user_groups]

            logger.debug(f"User groups: {user_groups}")

            # Whether this provider may confer administrator rights at all, and whether these
            # claims do (#318). ``admin_source: none`` is the answer for a partner tenant whose
            # group names you do not control; the admin group name itself stays server-side.
            is_admin = admin_from_claims(provider, user_groups, config.OIDC_ADMIN_GROUP_NAME)
            if not is_admin and not any(group in user_groups for group in config.OIDC_GROUP_NAME):
                errors.append("User is not allowed to login")
                return None, errors

            # Which local user this identity reaches (#309), and whether this provider may bring
            # it into existence (#318). Together these are what make a second provider safe: an
            # unknown (provider, subject) is a *new* principal, never matched to an existing
            # account by anything the token says about them, and a name already taken by another
            # identity is refused rather than claimed.
            subject = userinfo.get("sub")
            if not isinstance(subject, str) or not subject.strip():
                if provider.id == DEFAULT_PROVIDER_ID:
                    # Today's behaviour, preserved. The single-provider login has never read
                    # ``sub`` — it names accounts from the configured claim fields — and a
                    # provider whose userinfo omits it (non-conformant, but deployed) would
                    # otherwise stop working on upgrade. There is nothing to confuse it with:
                    # one provider means one identity space.
                    logger.debug("No subject in userinfo for the default provider; using the derived username")
                    subject = None
                else:
                    logger.warning("Provider '%s' asserted no subject; refusing", provider.id)
                    errors.append("This account cannot be used to sign in here")
                    return None, errors

            def _providers_bound_to(name: str) -> list:
                try:
                    return list(store.user_identity_repo.list_providers_for_username(name))
                except Exception as lookup_error:
                    # Fail closed: an unknown binding set must not read as "bound to nobody",
                    # which is what would let a provider adopt someone else's account.
                    logger.warning("Could not read bound providers for %s: %s", name, lookup_error)
                    return ["<unknown>"]

            if subject is None:
                # The default provider whose userinfo carries no subject — non-conformant, but
                # deployed, and it worked before. The username is the identity, as it always was.
                decision = IdentityDecision(Resolution.CREATE, reason="no subject asserted")
            else:
                decision = resolve_identity(
                    provider,
                    subject,
                    userinfo,
                    store.user_identity_repo,
                    user_lookup=store.has_user,
                    username=username,
                )

            outcome = apply_provisioning_policy(
                provider,
                decision,
                derived_username=username,
                user_exists=store.has_user,
                providers_bound_to=_providers_bound_to,
            )
            if not outcome.allowed:
                logger.warning("Refusing login via provider '%s': %s", provider.id, outcome.reason)
                emit_audit_event(
                    "auth.identity_refused",
                    actor=username,
                    resource_type="user",
                    resource_id=username,
                    detail={"provider": provider.id, "reason": outcome.reason},
                    status="denied",
                )
                errors.append("This account cannot be used to sign in here")
                return None, errors

            username = outcome.username or username

            if outcome.create or provider.admin_source == "claims":
                # ``create_user`` updates an existing row, so this is also how administrator
                # status is *revoked*: losing the admin group has always demoted the user at
                # their next login, and a provider allowed to grant admin must be allowed to take
                # it away. A provider with ``admin_source: none`` says nothing either way, so it
                # neither promotes nor demotes.
                user_module.create_user(username=username, display_name=display_name, is_admin=is_admin)

            # Bind the identity so the next login matches on it rather than on a claim.
            #
            # A failure here fails the login. Continuing would leave a user row with no binding,
            # so every later login for this subject would take the create path, find the name
            # taken and be refused — a permanent lockout from one transient error. It also means
            # a login racing another provider's is refused rather than quietly issued a session
            # for an account it does not own.
            if subject:
                try:
                    store.user_identity_repo.link(provider.id, subject.strip(), username)
                except Exception as link_error:
                    logger.error("Could not bind identity for %s at provider '%s': %s", username, provider.id, link_error)
                    emit_audit_event(
                        "auth.identity_bind_failed",
                        actor=username,
                        resource_type="user",
                        resource_id=username,
                        detail={"provider": provider.id},
                        status="denied",
                    )
                    errors.append("Could not complete sign-in for this account")
                    return None, errors

            groups = groups_to_apply(
                provider,
                user_groups,
                _current_groups(username),
                is_new_user=outcome.create,
            )
            if groups is not None:
                user_module.populate_groups(group_names=groups)
                user_module.update_user(username=username, group_names=groups)

            # Workspace detection (per D-07, D-08, WSOIDC-01/02/03)
            # Layered approach: plugin first, JWT claim fallback, then auto-assign
            if config.MLFLOW_ENABLE_WORKSPACES:
                user_workspaces: list[str] = []
                if config.OIDC_WORKSPACE_DETECTION_PLUGIN:
                    try:
                        user_workspaces = importlib.import_module(config.OIDC_WORKSPACE_DETECTION_PLUGIN).get_user_workspaces(access_token)
                    except Exception as ws_plugin_err:
                        logger.warning(f"Workspace detection plugin error: {ws_plugin_err}")
                else:
                    # JWT claim fallback
                    claim_value = userinfo.get(config.OIDC_WORKSPACE_CLAIM_NAME, [])
                    if isinstance(claim_value, str):
                        user_workspaces = [claim_value]
                    elif isinstance(claim_value, list):
                        user_workspaces = [str(w) for w in claim_value]

                # Auto-create workspaces that don't exist yet (WSOIDC-04)
                try:
                    from mlflow.server.handlers import _get_workspace_store

                    ws_mlflow_store = _get_workspace_store()
                except Exception as ws_store_err:
                    logger.warning(f"Cannot access MLflow workspace store for auto-create: {ws_store_err}")
                    ws_mlflow_store = None

                # Auto-assign workspace memberships
                from mlflow_oidc_auth.store import store as ws_store

                for ws_name in user_workspaces:
                    if not ws_name:
                        continue

                    # Auto-create workspace if it doesn't exist (WSOIDC-04)
                    if ws_mlflow_store is not None:
                        try:
                            ws_mlflow_store.get_workspace(ws_name)
                        except Exception:
                            # Workspace doesn't exist — try to create it
                            try:
                                from mlflow.store.workspace import (
                                    Workspace as MlflowWorkspace,
                                )

                                ws_mlflow_store.create_workspace(
                                    MlflowWorkspace(name=ws_name, description=""),
                                )
                                logger.info(f"Auto-created workspace '{ws_name}' during OIDC login for user {username}")
                            except Exception as create_err:
                                # Creation may fail if name is invalid or race condition
                                logger.warning(f"Failed to auto-create workspace '{ws_name}': {create_err}")

                    # Assign permission (existing logic)
                    try:
                        ws_store.create_workspace_permission(
                            ws_name,
                            username,
                            config.OIDC_WORKSPACE_DEFAULT_PERMISSION,
                        )
                        logger.info(f"Auto-assigned user {username} to workspace '{ws_name}' with {config.OIDC_WORKSPACE_DEFAULT_PERMISSION}")
                    except Exception:
                        # Permission already exists — not an error (idempotent)
                        logger.debug(f"Workspace permission already exists for {username} in '{ws_name}'")

            logger.info(f"User {username} successfully processed with groups: {user_groups}")

        except Exception as e:
            logger.error(f"User/group management error: {str(e)}")
            errors.append("Failed to update user/groups")
            return None, errors

        _persist_session_auth(session, token_response)

        return username, []

    except Exception as e:
        logger.error(
            "OIDC token exchange error (%s.%s): %s",
            type(e).__module__,
            type(e).__name__,
            str(e),
        )
        # PKCE is on by default (#312), and a provider that silently ignored the challenge at
        # the authorization endpoint rejects the exchange here with a bare ``invalid_grant``
        # that names nothing. The pre-redirect check catches providers that *advertise* their
        # methods; this covers the ones that advertise nothing, so the log still points at the
        # one setting worth trying.
        if config.OIDC_CODE_CHALLENGE and "invalid_grant" in str(e).lower():
            logger.error(
                "The token exchange was rejected with invalid_grant while PKCE is enabled (OIDC_CODE_CHALLENGE=%s). "
                "If this provider does not support PKCE, set OIDC_CODE_CHALLENGE=none. Otherwise the usual causes are "
                "a reused authorization code, an expired code, or a redirect_uri that differs from the one registered.",
                config.OIDC_CODE_CHALLENGE,
            )
        errors.append("Failed to process authentication response")
        return None, errors
