"""
Authentication router for FastAPI application.

This router handles OIDC authentication flows including login, logout, and callback.
"""

import asyncio
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
from mlflow_oidc_auth.repository.auth_session import REFRESH_GUARD_TIMEOUT_SECONDS
from mlflow_oidc_auth.session.refresh_lock import local_refresh_turn
from mlflow_oidc_auth.session.token_vault import SessionTokens, get_token_vault
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


def _client_for_refresh(provider_id: Optional[str]):
    """The client whose token endpoint may receive this session's refresh token.

    A refresh token belongs to the issuer that minted it. A session from a named provider is
    refreshed at that provider or not at all — never at the default one, which would hand one
    IdP another's credential. Sessions from the default provider, or recorded before the
    provider was stored, keep using the legacy client.
    """
    if provider_id and provider_id != DEFAULT_PROVIDER_ID:
        return get_client(provider_id)
    return oauth.oidc


def _session_is_fresh(tokens: Optional[SessionTokens]) -> bool:
    """Whether ``tokens`` carries an IdP expiry that has not passed (leeway included)."""
    return tokens is not None and tokens.expires_at is not None and not tokens.is_expired(config.OIDC_SESSION_EXPIRY_LEEWAY_SECONDS)


def _release_guard_when_entered(enter_task: "asyncio.Future", guard_cm) -> None:
    """Release a guard whose acquisition finishes after its waiter was cancelled.

    The acquisition runs in a worker thread that cancellation cannot stop; without this the lock
    it eventually takes would never be released, and every later refresh of the session would
    time out.
    """

    def _done(task):
        if not task.cancelled() and task.exception() is None:
            try:
                guard_cm.__exit__(None, None, None)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Releasing an abandoned refresh guard failed: %s", type(exc).__name__)

    enter_task.add_done_callback(_done)


async def refresh_session_with_idp(session_id: Optional[str], resolved=None) -> bool:
    """Refresh an expired session against the IdP, at most once across concurrent requests.

    Single-flight (#367). Concurrent requests that all find the session expired queue — on an
    ``asyncio.Lock`` per session within this event loop (no thread held while waiting), then on
    ``store.auth_session_refresh_guard`` across loops and replicas. The first exchanges the
    refresh token and stores the result on the session row; each one after it re-reads the row,
    finds a fresh expiry, and adopts it without calling the IdP. With refresh-token rotation and reuse
    detection a second exchange of the same token would end the session at the IdP — which is
    exactly what the cookie-held token used to cause, since every concurrent response wrote its
    own copy back.

    Parameters:
        session_id: The server-side session to refresh.
        resolved: The ``ResolvedSession`` the middleware already loaded, if any. Used only to
            skip the guard when there is nothing to refresh with; the decision to exchange is
            always taken on a re-read inside the guard.

    Returns:
        True when the session is fresh — refreshed here or by a concurrent request. False when
        it cannot be refreshed: refresh disabled, no refresh token, or the IdP refused. The
        caller is expected to clear the session and force re-authentication on False.
    """

    if not config.OIDC_USE_REFRESH_TOKEN or not session_id:
        return False

    vault = get_token_vault()
    if resolved is not None:
        # Cheap pre-check on the row already in hand: no refresh token, nothing to serialise.
        known = vault.decrypt(getattr(resolved, "encrypted_tokens", None))
        if known is None or not known.has_refresh_token:
            return False

    try:
        # In-process queue: awaited on the event loop, so a burst of waiters holds no threads.
        async with local_refresh_turn(session_id, REFRESH_GUARD_TIMEOUT_SECONDS):
            # The request ahead in the queue may have refreshed already. One statement, no
            # thread, and no IdP call when it has.
            if _session_is_fresh(_read_row_tokens(session_id, vault)):
                logger.debug("Session was refreshed by a concurrent request; not exchanging again")
                return True
            return await _refresh_holding_turn(session_id, vault, resolved)
    except TimeoutError:
        logger.warning("Timed out waiting for a concurrent refresh of a session")
        # The refresh ahead held the turn for longer than we wait. It may still have succeeded.
        return _session_is_fresh(_read_row_tokens(session_id, vault))


# Indirection so tests can observe which requests use a worker thread (only the refresher may).
_run_blocking = asyncio.to_thread


def _read_row_tokens(session_id: str, vault) -> Optional[SessionTokens]:
    """The session row's tokens as stored now, or None if it is gone or unreadable."""
    try:
        latest = store.resolve_auth_session(session_id)
    except Exception as exc:
        logger.warning("Could not re-read a session during refresh: %s", type(exc).__name__)
        return None
    return vault.decrypt(getattr(latest, "encrypted_tokens", None)) if latest is not None else None


async def _refresh_holding_turn(session_id: str, vault, resolved) -> bool:
    """Take the cross-process guard, then refresh. Only the holder of the local turn gets here."""
    guard_cm = store.auth_session_refresh_guard(session_id)
    # Acquiring may block on another replica's row lock, so it runs in a worker thread and never
    # stalls the event loop. Only one request per session per loop is ever here.
    enter_task = asyncio.ensure_future(_run_blocking(guard_cm.__enter__))
    try:
        guard = await asyncio.shield(enter_task)
    except asyncio.CancelledError:
        _release_guard_when_entered(enter_task, guard_cm)
        raise
    except Exception as exc:
        logger.warning("Could not acquire the refresh guard for a session: %s", type(exc).__name__)
        return _session_is_fresh(_read_row_tokens(session_id, vault))

    wrote = False
    try:
        refreshed_ok, wrote = await _refresh_inside_guard(guard, vault, resolved)
    except Exception as exc:
        logger.warning("Session refresh failed: %s", type(exc).__name__)
        refreshed_ok = False
    finally:
        try:
            # Commits the new tokens where the guard holds a row lock.
            guard_cm.__exit__(None, None, None)
        except Exception as exc:
            logger.warning("Releasing the refresh guard failed: %s", type(exc).__name__)
            if wrote:
                # The rotated token did not reach the database; the one stored is already spent
                # at the IdP. Honouring this request would only defer the failure.
                refreshed_ok = False
    return refreshed_ok


async def _refresh_inside_guard(guard, vault, resolved) -> tuple[bool, bool]:
    """The part of a refresh that runs while holding the guard. Returns (fresh, wrote)."""
    if not guard.live:
        return False, False

    tokens = vault.decrypt(guard.encrypted_tokens)
    if tokens is None or not tokens.has_refresh_token:
        return False, False

    if _session_is_fresh(tokens):
        # Another request refreshed while this one waited. Adopt its result.
        logger.debug("Session was refreshed by a concurrent request; not exchanging again")
        return True, False

    provider_id = tokens.provider_id or getattr(resolved, "provider_id", None)
    client = _client_for_refresh(provider_id)
    fetch_fn = getattr(client, "fetch_access_token", None) if client is not None else None
    if fetch_fn is None:
        logger.warning("No OIDC client able to refresh a session for provider '%s'", provider_id or DEFAULT_PROVIDER_ID)
        return False, False

    try:
        new_token = await _maybe_await(fetch_fn(grant_type="refresh_token", refresh_token=tokens.refresh_token))
    except Exception as exc:
        logger.warning("OIDC refresh token exchange failed: %s", type(exc).__name__)
        new_token = None

    if not new_token:
        # A winner elsewhere (another replica on a database without row locks) may have
        # refreshed between our read and the IdP's refusal. Look once more before giving up.
        return _session_is_fresh(vault.decrypt(guard.reread())), False

    refreshed = _session_tokens_from_response(new_token, provider_id=tokens.provider_id, previous=tokens)
    if not guard.write(vault.encrypt(refreshed)):
        # The session was revoked while we refreshed. The new tokens die with it.
        return False, False
    return True, True


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


# Keys that a cookie issued before #367 may still carry. They are no longer read — the session
# row is authoritative — and are dropped wherever they are seen.
_LEGACY_TOKEN_COOKIE_KEYS = ("expires_at", "refresh_token")


def _drop_legacy_token_keys(session) -> bool:
    """Remove token material an older release left in the cookie. True if any was present."""
    found = False
    for key in _LEGACY_TOKEN_COOKIE_KEYS:
        if key in session:
            session.pop(key, None)
            found = True
    return found


def _session_tokens_from_response(
    token_response: dict[str, Any],
    provider_id: Optional[str] = None,
    previous: Optional[SessionTokens] = None,
) -> SessionTokens:
    """Build the ``SessionTokens`` a token response leaves on the session row.

    ``OIDC_USE_REFRESH_TOKEN`` gates whether a refresh token is retained at all — many
    enterprises disallow ``offline_access`` outright. When it is on and the response carries no
    refresh token, the previous one is kept: many IdPs (Microsoft Entra, some Keycloak configs)
    emit one only on the first exchange and reuse it across refreshes.

    Parameters:
        token_response: The IdP's token response.
        provider_id: The provider that issued it.
        previous: The session's tokens before this response, on a refresh.

    Returns:
        The tokens to store.
    """
    refresh_token = None
    if config.OIDC_USE_REFRESH_TOKEN:
        refresh_token = token_response.get("refresh_token") or (previous.refresh_token if previous else None)
    id_token = token_response.get("id_token") or (previous.id_token if previous else None)
    return SessionTokens(
        provider_id=provider_id if provider_id is not None else (previous.provider_id if previous else None),
        expires_at=_extract_session_expiry(token_response),
        refresh_token=refresh_token or None,
        id_token=id_token if isinstance(id_token, str) and id_token else None,
    )


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
                    "login_url": _login_path(request, f"{LOGIN}/{provider.id}"),
                }
                for provider in config.AUTH_PROVIDERS.interactive_providers()
            ]
        },
        # Unauthenticated, and the browser turns each entry into a button it will navigate to.
        # A shared cache in front of the deployment must not be able to hand one visitor's
        # response to another.
        headers={"Cache-Control": "no-store"},
    )


def _login_path(request: Request, path: str) -> str:
    """Build the login URL for a provider as a path on this deployment.

    Deliberately origin-less. The alternative — an absolute URL — has to get its origin from
    somewhere, and the only candidate available per-request is the ``Host`` header, which any
    client can set and which a proxy can forward from any client. These strings become the
    ``href`` of the sign-in button on an unauthenticated page, so an origin taken from a request
    is an origin an attacker can choose. A path is same-origin by construction and needs no
    configuration to be correct.

    ``root_path`` is included so a deployment mounted under a prefix gets a URL that resolves.
    It is dropped when it does not look like a path, because it is not always the mount:
    ``ProxyHeadersMiddleware`` also sets it from ``X-Forwarded-Prefix`` when the connecting client
    is a proxy listed in ``TRUSTED_PROXIES``. A value beginning with ``//`` would otherwise
    make this return a protocol-relative URL — ``//evil.example/login/entra`` is off-origin the
    moment a browser resolves it, which is the one thing this function promises cannot happen.
    A prefix that has to be discarded means a broken link, not a login somewhere else.
    """
    root_path = request.scope.get("root_path", "") or ""
    if not root_path.startswith("/") or root_path.startswith("//"):
        root_path = ""
    return f"{root_path.rstrip('/')}{path}"


@auth_router.get(f"{LOGIN}/{{provider_id}}")
async def login_with_provider(request: Request, provider_id: str):
    """Begin a login against a named provider (#316).

    The legacy ``/login`` is this with ``default``, so redirect URIs already registered at
    customers' IdPs keep working.
    """
    provider = _interactive_provider(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Unknown identity provider")
    if provider.type == "saml":
        # SP-initiated SAML SSO (#328). Imported here: routers.saml imports this module.
        from mlflow_oidc_auth.routers.saml import begin_saml_login

        return await begin_saml_login(request, provider)
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

    Called before the token exchange, not after. ``_session_tokens_from_response`` deliberately keeps an
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


def _open_server_session(username: str, provider_id: Optional[str] = None, tokens: Optional[SessionTokens] = None) -> str:
    """Open a server-side session for ``username`` and return its opaque id.

    The row's lifetime mirrors the cookie's, so a session cannot outlive the credential that
    carries it, and an unbounded cookie still yields a bounded row — one that never expires
    could never be swept.

    The provider tokens are encrypted onto the row as it is created (#367), so the session id is
    only ever placed in a cookie after its tokens are stored server-side, and no token transits
    the cookie at any point.

    Parameters:
        username: The user logging in.
        provider_id: Registry id of the provider that authenticated them.
        tokens: The provider tokens to keep with the session.

    Returns:
        The session id.
    """
    max_age = config.SESSION_COOKIE_MAX_AGE_SECONDS or DEFAULT_SESSION_LIFETIME_SECONDS
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max_age)
    if provider_id is None and tokens is not None:
        provider_id = tokens.provider_id
    encrypted = get_token_vault().encrypt(tokens) if tokens is not None else None
    return store.create_auth_session(username, expires_at=expires_at, provider_id=provider_id, encrypted_tokens=encrypted)


# How long logout waits on the IdP — for its discovery document, or for a token revocation —
# before giving up on it. Logout is interactive and the local session is already gone by then, so
# a slow or unreachable IdP may cost the user a few seconds, never the logout itself.
IDP_LOGOUT_TIMEOUT_SECONDS = 5.0


class _RevocationRefused(Exception):
    """The IdP answered the RFC 7009 revocation request with an error status."""


def _logout_context(request: Request, session_id: Optional[str]) -> tuple[str, Optional[SessionTokens]]:
    """The provider that opened ``session_id`` and the tokens it issued, read before revocation.

    The provider is the one the session row records, else the one recorded with its tokens, else
    ``default`` — a session from before providers were recorded belongs to the legacy client.
    Tokens recorded for a provider other than the one the row names are dropped: a credential is
    only ever offered back to the issuer that minted it. Best effort — logout never fails over
    this; anything unreadable yields ``("default", None)``, which is the pre-#367 behaviour.

    Parameters:
        request: The logout request (its ``state`` may already hold the resolved session).
        session_id: The session being logged out, if any.

    Returns:
        ``(provider_id, tokens)``.
    """
    if not session_id:
        return DEFAULT_PROVIDER_ID, None
    try:
        resolved = getattr(getattr(request, "state", None), "resolved_session", None)
        if resolved is None or getattr(resolved, "session_id", session_id) != session_id:
            resolved = store.resolve_auth_session(session_id)
        if resolved is None:
            return DEFAULT_PROVIDER_ID, None
        tokens = get_token_vault().decrypt(getattr(resolved, "encrypted_tokens", None))
    except Exception as exc:
        logger.debug("Could not read the session's provider and tokens for logout: %s", type(exc).__name__)
        return DEFAULT_PROVIDER_ID, None
    row_provider = getattr(resolved, "provider_id", None)
    token_provider = tokens.provider_id if tokens is not None else None
    provider_id = row_provider or token_provider or DEFAULT_PROVIDER_ID
    if tokens is not None and token_provider not in (None, provider_id):
        tokens = None
    return provider_id, tokens


async def _provider_metadata(client) -> dict:
    """The provider's discovery metadata, loading it if this process has not yet, or ``{}``.

    A worker that never served this provider's login may not have fetched its discovery
    document; loading it here (bounded by ``IDP_LOGOUT_TIMEOUT_SECONDS``) is what lets that
    worker still find the end-session and revocation endpoints.
    """
    loader = getattr(client, "load_server_metadata", None)
    if callable(loader):
        try:
            loaded = await asyncio.wait_for(_maybe_await(loader()), IDP_LOGOUT_TIMEOUT_SECONDS)
            if isinstance(loaded, dict):
                return loaded
        except Exception as exc:
            logger.debug("Could not load provider metadata for logout: %s", type(exc).__name__)
    metadata = getattr(client, "server_metadata", None)
    return metadata if isinstance(metadata, dict) else {}


async def _revoke_at_revocation_endpoint(client, refresh_token: str) -> bool:
    """Send ``refresh_token`` to the provider's RFC 7009 endpoint. False when it advertises none."""
    metadata = await _provider_metadata(client)
    endpoint = metadata.get("revocation_endpoint")
    if not isinstance(endpoint, str) or not endpoint:
        return False
    # The same authlib session factory the client's own token exchange uses, so the request
    # carries this provider's client credentials, auth method and TLS settings — and only its.
    async with client._get_oauth_client(**metadata) as session:
        response = await session.revoke_token(endpoint, token=refresh_token, token_type_hint="refresh_token")
    status_code = getattr(response, "status_code", 200)
    if not isinstance(status_code, int) or not 200 <= status_code < 300:
        raise _RevocationRefused(f"HTTP {status_code}")
    return True


async def _revoke_refresh_token_at_idp(provider_id: str, tokens: Optional[SessionTokens], username: Optional[str]) -> None:
    """Revoke the session's refresh token at the provider that issued it (RFC 7009). Best effort.

    Without this, the ``offline_access`` grant behind ``OIDC_USE_REFRESH_TOKEN`` outlives logout:
    RP-initiated logout ends the IdP's browser session, not an offline one, so the refresh token
    would stay valid at the IdP until its offline idle timeout. The token goes only to the
    provider recorded for the session, through that provider's own client. A provider that
    advertises no ``revocation_endpoint`` is skipped silently. Any failure is logged (exception
    type only — never the token) and audited as ``auth.token_revocation_failed``; it never blocks
    the logout, whose local half has already happened.
    """
    if tokens is None or not tokens.has_refresh_token:
        return
    client = _client_for_refresh(provider_id)
    if client is None or not hasattr(client, "_get_oauth_client"):
        # The provider is no longer configured (or is not OIDC): nothing here holds the client
        # credentials to revoke with, so the grant lives until the IdP expires it. Say so.
        logger.warning("No OIDC client for provider '%s'; the session's refresh token cannot be revoked", provider_id)
        emit_audit_event(
            "auth.token_revocation_failed",
            actor=username or "<unknown>",
            detail={"provider_id": provider_id, "reason": "no_client"},
            status="denied",
        )
        return
    try:
        revoked = await asyncio.wait_for(_revoke_at_revocation_endpoint(client, tokens.refresh_token), IDP_LOGOUT_TIMEOUT_SECONDS)
    except Exception as exc:
        reason = type(exc).__name__
        logger.warning("Could not revoke the session's refresh token at provider '%s': %s", provider_id, reason)
        emit_audit_event(
            "auth.token_revocation_failed",
            actor=username or "<unknown>",
            detail={"provider_id": provider_id, "reason": reason},
            status="denied",
        )
        return
    if revoked:
        logger.debug("Revoked the session's refresh token at provider '%s'", provider_id)


async def _named_provider_end_session_url(request: Request, provider_id: str, tokens: Optional[SessionTokens]) -> Optional[str]:
    """RP-initiated logout at the named OIDC provider that opened the session, or None.

    Uses that provider's own ``end_session_endpoint`` and client id, and offers its own ID token
    as ``id_token_hint``. None — local logout only — when the provider has no registered client
    (not OIDC, or no longer configured) or advertises no end-session endpoint. Never falls back to
    the default provider, which did not authenticate this session.
    """
    client = get_client(provider_id)
    if client is None:
        logger.debug("No OIDC client for provider '%s'; ending the local session only", provider_id)
        return None
    metadata = await _provider_metadata(client)
    end_session_endpoint = metadata.get("end_session_endpoint")
    if not isinstance(end_session_endpoint, str) or not end_session_endpoint:
        return None
    logout_params = {"post_logout_redirect_uri": _build_ui_url(request, "/auth")}
    client_id = getattr(client, "client_id", None)
    if isinstance(client_id, str) and client_id:
        logout_params["client_id"] = client_id
    if tokens is not None and tokens.id_token:
        logout_params["id_token_hint"] = tokens.id_token
    return f"{end_session_endpoint}?{urlencode(logout_params)}"


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
        # Read before revocation: a revoked row no longer resolves. The provider that opened the
        # session decides where RP-initiated logout and token revocation go.
        provider_id, session_tokens = _logout_context(request, session_id)
        # Likewise the SAML NameID and SessionIndex for single logout (#329).
        from mlflow_oidc_auth.routers.saml import saml_logout_context, saml_logout_redirect

        saml_context = saml_logout_context(request, session_id)

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

        if saml_context is not None:
            # SP-initiated SAML single logout (#329). Only now, with the row revoked and the
            # cookie cleared: whatever happens at the IdP — it is down, it refuses, the user
            # closes the tab — nothing live is left here. A session from a SAML provider never
            # goes to the OIDC end-session endpoint below, which belongs to another IdP.
            slo_url = saml_logout_redirect(request, *saml_context)
            return RedirectResponse(url=slo_url or _build_ui_url(request, "/auth"), status_code=302)

        # End the IdP grant too, before the browser leaves: RP-initiated logout does not end the
        # offline session a refresh token belongs to. Never raises.
        await _revoke_refresh_token_at_idp(provider_id, session_tokens, username)

        if provider_id != DEFAULT_PROVIDER_ID:
            # A named OIDC provider opened this session: log out there, or nowhere.
            logout_url = await _named_provider_end_session_url(request, provider_id, session_tokens)
            return RedirectResponse(url=logout_url or _build_ui_url(request, "/auth"), status_code=302)

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
                logout_params = {
                    "post_logout_redirect_uri": post_logout_redirect,
                    "client_id": config.OIDC_CLIENT_ID,
                }
                if session_tokens is not None and session_tokens.id_token:
                    # Held on the (now revoked) session row since #367, so it can be offered.
                    logout_params["id_token_hint"] = session_tokens.id_token
                params = urlencode(logout_params)
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
            # Tokens first, cookie second (#367): the row is created with this login's tokens
            # already on it, and only then does the cookie name it.
            pending_tokens = getattr(getattr(request, "state", None), "pending_session_tokens", None)
            if not isinstance(pending_tokens, SessionTokens):
                pending_tokens = None
            try:
                if pending_tokens is not None:
                    session_id = _open_server_session(username, provider_id=pending_tokens.provider_id, tokens=pending_tokens)
                else:
                    session_id = _open_server_session(username)
                session["session_id"] = session_id
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


def _session_provider_display_name(resolved) -> str:
    """Display name of the provider that opened the session, else ``OIDC_PROVIDER_DISPLAY_NAME``.

    A SAML or named-OIDC session is reported under its own provider, not the default one. A
    session from before providers were recorded, or from a provider no longer configured, falls
    back to the deployment-wide name.
    """
    provider_id = getattr(resolved, "provider_id", None)
    if isinstance(provider_id, str) and provider_id:
        try:
            provider = config.AUTH_PROVIDERS.by_id(provider_id)
        except Exception as exc:
            logger.debug("Could not look up the session's provider: %s", type(exc).__name__)
            provider = None
        display_name = getattr(provider, "display_name", None) if provider is not None else None
        if isinstance(display_name, str) and display_name:
            return display_name
    return config.OIDC_PROVIDER_DISPLAY_NAME


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
                "provider": _session_provider_display_name(resolved) if is_authenticated else None,
            }
        )

    except Exception as e:
        logger.error(f"Error getting auth status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get authentication status")


def _account_is_inactive(username: str) -> bool:
    """Whether ``username`` names an existing account that is deactivated.

    An account that does not exist is not inactive — the provisioning policy decides whether it
    may be created. Any other failure to read the flag counts as inactive: a login that cannot
    prove the account is enabled does not proceed.
    """
    from mlflow.exceptions import MlflowException
    from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode

    try:
        user = store.get_user(username)
    except MlflowException as exc:
        if exc.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
            return False
        logger.warning("Could not read the active flag for %s: %s", username, type(exc).__name__)
        return True
    except Exception as exc:
        logger.warning("Could not read the active flag for %s: %s", username, type(exc).__name__)
        return True
    return getattr(user, "active", True) is False


def _provision_login(
    provider,
    *,
    username: str,
    display_name: str,
    userinfo: dict[str, Any],
    user_groups: list,
    access_token: Optional[str],
    method: str = "oidc",
) -> tuple[Optional[str], list[str]]:
    """Everything a login does once the provider has proven who the user is.

    Shared by the OIDC callback and the SAML ACS (#328) so both apply one policy: the group gate,
    identity resolution (#309), the provisioning policy (#318), the identity binding, group sync
    and workspace assignment. Nothing here knows which protocol delivered the identity.

    Parameters:
        provider: The registry entry that authenticated the user.
        username: The username derived from the provider's claims or attributes.
        display_name: The display name to record.
        userinfo: Claims (OIDC) or attributes (SAML). ``sub`` is the provider's subject.
        user_groups: Group names the provider asserted.
        access_token: The OAuth access token, for detection plugins; None for SAML.
        method: ``oidc`` or ``saml``, recorded as who wrote the user row.

    Returns:
        ``(username, [])`` on success, ``(None, errors)`` when the login is refused.

    Raises:
        Exception: Whatever user or group management raised; the caller reports it.
    """
    import importlib

    import mlflow_oidc_auth.user as user_module

    errors: list[str] = []

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

    # A deactivated account completes nothing. Checked before any write: otherwise the login
    # would refresh the row's admin flag, groups and workspaces and open a session that the
    # middleware refuses today but that would start working again the moment the directory
    # reactivates the account — reviving a credential minted while it was disabled.
    if _account_is_inactive(username):
        from mlflow_oidc_auth.middleware.auth_middleware import DENIAL_AUDIT_EVENTS, DENIAL_INACTIVE

        logger.info("Refusing login via provider '%s' for a deactivated account", provider.id)
        emit_audit_event(
            DENIAL_AUDIT_EVENTS[DENIAL_INACTIVE],
            actor=username,
            resource_type="user",
            resource_id=username,
            detail={"method": method, "provider": provider.id},
            status="denied",
        )
        errors.append("This account cannot be used to sign in here")
        return None, errors

    if outcome.create or provider.admin_source == "claims":
        # ``create_user`` updates an existing row, so this is also how administrator
        # status is *revoked*: losing the admin group has always demoted the user at
        # their next login, and a provider allowed to grant admin must be allowed to take
        # it away. A provider with ``admin_source: none`` says nothing either way, so it
        # neither promotes nor demotes.
        user_module.create_user(username=username, display_name=display_name, is_admin=is_admin, written_by=f"{method}:{provider.id}")

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
        user_module.populate_groups(group_names=groups, written_by=f"{method}:{provider.id}")
        # Attributed to the provider (#360): the memberships this creates are owned by it, and an
        # authoritative sync removes only what the guard lets it — its own rows and unowned
        # ``manual`` ones everywhere, another source's only outside ``enforce``.
        user_module.update_user(username=username, group_names=groups, written_by=f"{method}:{provider.id}")

    # Workspace detection (per D-07, D-08, WSOIDC-01/02/03)
    # Layered approach: plugin first, JWT claim fallback, then auto-assign
    if config.MLFLOW_ENABLE_WORKSPACES:
        user_workspaces: list[str] = []
        if config.OIDC_WORKSPACE_DETECTION_PLUGIN:
            # A configured plugin is the only source of workspace membership. It reads an OAuth
            # access token; a login without one (SAML) is assigned nothing rather than falling
            # back to a claim or attribute the operator chose not to trust.
            if access_token is not None:
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
                logger.info("Auto-assigned user %s to workspace %r with the configured default permission", username, ws_name)
            except Exception:
                # Permission already exists — not an error (idempotent)
                logger.debug(f"Workspace permission already exists for {username} in '{ws_name}'")

    logger.info(f"User {username} successfully processed with groups: {user_groups}")
    return username, []


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
    # _session_tokens_from_response keeps a previous refresh token when the new response has none,
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
            # Use module-level config (possibly patched in tests). User management goes through
            # the mlflow_oidc_auth.user module inside _provision_login so test monkeypatches apply.
            import importlib

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

            username, provision_errors = _provision_login(
                provider,
                username=username,
                display_name=display_name,
                userinfo=userinfo,
                user_groups=user_groups,
                access_token=access_token,
            )
            if provision_errors:
                errors.extend(provision_errors)
                return None, errors

        except Exception as e:
            logger.error(f"User/group management error: {str(e)}")
            errors.append("Failed to update user/groups")
            return None, errors

        # The tokens go onto the session row when ``_complete_login`` opens it — never into the
        # cookie (#367). Held on the request until then.
        _drop_legacy_token_keys(session)
        request_state = getattr(request, "state", None)
        if request_state is not None:
            request_state.pending_session_tokens = _session_tokens_from_response(token_response, provider_id=provider.id)

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
