"""SAML 2.0 routes: ACS, single logout and SP metadata (issues #328, #329).

``GET /login/{provider_id}`` for a SAML provider is served by ``routers.auth`` and hands off to
:func:`begin_saml_login`; everything the IdP sends back lands here.

**No route here reads the session cookie to decide anything.** The ACS is a cross-site POST, and
under ``SESSION_COOKIE_SAMESITE=lax`` — the default, and not to be weakened for this — the browser
does not send the cookie with it. The login is correlated through ``RelayState`` instead, which is
the ``state`` of the ``auth_state`` row ``/login`` created: single use, 15-minute lifetime, and
bound to the provider it was created for. The session cookie is set fresh on the ACS response;
``Set-Cookie`` on a top-level navigation is honoured whatever the SameSite attribute.

**Browser binding (#374).** ``RelayState`` alone proves a Response answers *some* attempt, not that
the browser delivering it started that attempt — an attacker could complete a login for their own
account and have a victim's browser post it (login CSRF). So ``/login`` also sets a nonce cookie,
``HttpOnly; Secure; SameSite=None``, path-scoped to this provider's ACS and short-lived, and stores
only its SHA-256 on the attempt's row; the ACS requires the cookie's hash to match the row it
consumed. ``SameSite=None`` is what lets this one cookie ride the cross-site POST; the session
cookie keeps its own policy and is still never read here. The cookie is named per attempt, so two
logins started in two tabs do not overwrite each other's nonce. It is on when
``SESSION_COOKIE_SECURE`` is (``SAML_LOGIN_BINDING=auto``): a ``Secure`` cookie never comes back
over plain http, so without https the binding would refuse every login.

Every refusal answers with one fixed string; why it was refused goes to the log and, where it is
security-relevant, to the audit trail.
"""

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.provider_registry import ProviderConfig
from mlflow_oidc_auth.saml import (
    ACS_PATH,
    METADATA_PATH,
    SLS_PATH,
    SamlError,
    SamlIdentity,
    SamlLogoutRequest,
    acs_url,
    build_authn_redirect,
    build_logout_redirect,
    process_logout_request,
    process_logout_response,
    process_response,
    saml_available,
    sp_base_url,
    sp_metadata,
)
from mlflow_oidc_auth.session.token_vault import SessionTokens, get_token_vault
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.repository.user import normalize_username

logger = get_logger()

saml_router = APIRouter(tags=["auth"], responses={404: {"description": "Not found"}})

# A signed Response with a few hundred group attributes is tens of kilobytes; this leaves an
# order of magnitude of headroom and still bounds what an anonymous POST can make us buffer.
MAX_SAML_POST_BYTES = 512 * 1024

# The only thing a refused SAML message ever tells the browser.
REFUSED = "SAML sign-in failed"
LOGOUT_REFUSED = "SAML logout failed"

#: Name prefix of the per-attempt browser-binding cookie (#374). The rest of the name is derived
#: from the attempt's RelayState, so the ACS can find the cookie for the attempt it consumed.
BINDING_COOKIE_PREFIX = "mlflow_saml_binding_"
#: Lifetime of the binding cookie and of the bound ``auth_state`` row, kept equal (see
#: :func:`begin_saml_login`). Unbound SAML attempts keep the row's default 15 minutes.
BINDING_COOKIE_MAX_AGE_SECONDS = 10 * 60
#: 256 bits, like the ``state`` itself.
BINDING_NONCE_BYTES = 32
#: What ``secrets.token_urlsafe(BINDING_NONCE_BYTES)`` produces (43 characters), with slack.
_NONCE_SHAPE = re.compile(r"[A-Za-z0-9_-]{16,128}")


def _saml_provider(provider_id: str) -> Optional[ProviderConfig]:
    """The interactive SAML provider named ``provider_id``, or None."""
    provider = config.AUTH_PROVIDERS.by_id(provider_id)
    if provider is None or provider.type != "saml" or not provider.interactive:
        return None
    return provider


def _require_provider(provider_id: str) -> ProviderConfig:
    provider = _saml_provider(provider_id)
    if provider is None or not saml_available():
        raise HTTPException(status_code=404, detail="Unknown identity provider")
    return provider


async def _read_form(request: Request) -> Dict[str, str]:
    """Parse an ``application/x-www-form-urlencoded`` body, bounded, without python-multipart.

    A field given twice is refused rather than resolved: which copy a parser keeps differs
    between parsers, and a SAMLResponse or RelayState that two layers read differently is the
    parameter-pollution setup.
    """
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(status_code=400, detail=REFUSED)
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdigit() or int(declared) > MAX_SAML_POST_BYTES):
        raise HTTPException(status_code=413, detail=REFUSED)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_SAML_POST_BYTES:
            raise HTTPException(status_code=413, detail=REFUSED)
    try:
        parsed = parse_qs(bytes(body).decode("ascii"), keep_blank_values=True, max_num_fields=16)
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=400, detail=REFUSED)
    if any(len(values) != 1 for values in parsed.values()):
        raise HTTPException(status_code=400, detail=REFUSED)
    return {key: values[0] for key, values in parsed.items()}


def _query_data(request: Request) -> Dict[str, str]:
    """Query parameters as a flat dict, refusing any given twice (see :func:`_read_form`)."""
    data: Dict[str, str] = {}
    for key in request.query_params.keys():
        values = request.query_params.getlist(key)
        if len(values) != 1:
            raise HTTPException(status_code=400, detail=LOGOUT_REFUSED)
        data[key] = values[0]
    return data


async def begin_saml_login(request: Request, provider: ProviderConfig) -> RedirectResponse:
    """Start SP-initiated SSO: record the attempt, then send the browser to the IdP.

    The attempt's ``state`` is the ``RelayState``, and the AuthnRequest ``ID`` is derived from it,
    so the Response can be tied to this request without anything in the cookie.
    """
    from mlflow_oidc_auth.routers.auth import _sanitize_next

    if not saml_available():
        # Unreachable while the registry drops SAML providers without the extra; kept so a
        # library that fails after startup degrades to an error page rather than a stack trace.
        raise HTTPException(status_code=500, detail="SAML sign-in is not available")

    next_target = _sanitize_next(request.query_params.get("next"))
    nonce = secrets.token_urlsafe(BINDING_NONCE_BYTES) if config.saml_login_binding_enabled else None
    if nonce:
        # The row lives exactly as long as the cookie: a slow login then fails as an expired
        # RelayState, never as a live attempt whose cookie is gone (which reads like login CSRF).
        relay_state = store.create_auth_state(
            provider.id, redirect_after_login=next_target, binding_hash=_binding_hash(nonce), lifetime_seconds=BINDING_COOKIE_MAX_AGE_SECONDS
        )
    else:
        relay_state = store.create_auth_state(provider.id, redirect_after_login=next_target)
    base_url = sp_base_url(request)
    try:
        url = build_authn_redirect(provider, base_url, relay_state)
    except Exception as exc:
        logger.error("Could not build a SAML AuthnRequest for provider '%s': %s", provider.id, type(exc).__name__)
        raise HTTPException(status_code=500, detail="SAML sign-in is misconfigured; see the server logs")
    response = RedirectResponse(url=url, status_code=302, headers={"Cache-Control": "no-store"})
    if nonce:
        response.set_cookie(
            _binding_cookie_name(relay_state),
            nonce,
            max_age=BINDING_COOKIE_MAX_AGE_SECONDS,
            path=_binding_cookie_path(provider, base_url),
            secure=True,
            httponly=True,
            samesite="none",
        )
    return response


def _binding_hash(nonce: str) -> str:
    """What the ``auth_state`` row stores for a binding nonce. The nonce itself is never stored or logged."""
    return hashlib.sha256(nonce.encode("ascii")).hexdigest()


def _binding_cookie_name(relay_state: str) -> str:
    """The binding cookie's name for the attempt ``relay_state`` names (see the module docstring)."""
    return BINDING_COOKIE_PREFIX + hashlib.sha256(relay_state.encode("utf-8")).hexdigest()[:16]


def _binding_cookie_path(provider: ProviderConfig, base_url: str) -> str:
    """The ACS path the IdP posts to, which is the only place the binding cookie is sent."""
    return urlparse(acs_url(provider, base_url)).path or "/"


#: :func:`_binding_verdict` outcomes.
BINDING_OK = "ok"
BINDING_MISSING = "missing"
BINDING_MISMATCH = "mismatch"


def _binding_verdict(request: Request, attempt, cookie_name: str) -> str:
    """Whether the browser posting to the ACS is the one that started ``attempt``.

    Returns :data:`BINDING_OK`; :data:`BINDING_MISSING` when no binding cookie arrived (the usual
    cause is a browser that dropped or outlived it, not an attack); or :data:`BINDING_MISMATCH`
    when one arrived that does not belong to this attempt — the login-CSRF shape. Both refuse.

    An attempt recorded with a binding needs the matching cookie, whatever the switch says now.
    An attempt recorded without one passes only while the binding is off: with it on, an unbound
    row (one started before the switch flipped) is refused as missing rather than trusted.
    """
    expected = attempt.binding_hash
    if not expected:
        return BINDING_MISSING if config.saml_login_binding_enabled else BINDING_OK
    nonce = request.cookies.get(cookie_name)
    if not nonce:
        return BINDING_MISSING
    # The value is attacker-controlled and Starlette decodes it as latin-1: anything that is not
    # the shape /login mints is refused, never passed on to be encoded.
    if not _NONCE_SHAPE.fullmatch(nonce):
        return BINDING_MISMATCH
    return BINDING_OK if hmac.compare_digest(_binding_hash(nonce), expected) else BINDING_MISMATCH


def _clear_binding_cookie(response: Response, provider: ProviderConfig, base_url: str, cookie_name: str) -> None:
    response.delete_cookie(cookie_name, path=_binding_cookie_path(provider, base_url), secure=True, httponly=True, samesite="none")


def _first(attributes: Dict[str, list], name: str) -> Optional[str]:
    values = attributes.get(name) or []
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _identity_to_login(provider: ProviderConfig, identity: SamlIdentity) -> Tuple[str, str, dict, list]:
    """Map a validated assertion to ``(username, display_name, userinfo, groups)``.

    The username comes from ``attribute_username`` and falls back to the NameID; it names the
    account but does not identify it — the binding is on (provider, NameID), exactly as OIDC
    binds on (provider, ``sub``), so an attribute the user can edit at the IdP cannot move them
    into someone else's account.
    """
    attributes = identity.attributes
    username = normalize_username(_first(attributes, provider.attribute_username) or identity.name_id)
    display_name = _first(attributes, provider.attribute_display_name) or username
    groups = [value for value in (attributes.get(provider.attribute_groups) or []) if isinstance(value, str) and value]
    userinfo = {name: (values[0] if len(values) == 1 else list(values)) for name, values in attributes.items()}
    userinfo["sub"] = identity.name_id
    return username, display_name, userinfo, groups


def _refuse(event: str, provider: ProviderConfig, reason: str, status_code: int = 400, detail: str = REFUSED) -> HTTPException:
    """Log and audit a refusal; return the exception to raise."""
    logger.warning("Refusing a SAML message for provider '%s': %s", provider.id, reason)
    emit_audit_event(event, actor="<anonymous>", detail={"provider": provider.id}, status="denied")
    return HTTPException(status_code=status_code, detail=detail)


@saml_router.post(f"{ACS_PATH}/{{provider_id}}")
async def saml_acs(request: Request, provider_id: str):
    """Assertion Consumer Service (HTTP-POST binding).

    Order matters and each step is a refusal point: the ``RelayState`` must name a live attempt
    for *this* provider (consumed, so it cannot be used twice); the browser must hold that
    attempt's binding cookie (#374); the Response must validate against that attempt; its
    assertion must not have been seen before. Only then is anything written — the previous login
    retired, the user provisioned, a session opened.

    The attempt's binding cookie is cleared on every outcome: it is single use, like the row.
    """
    provider = _require_provider(provider_id)
    form = await _read_form(request)
    relay_state = form.get("RelayState") or ""
    cookie_name = _binding_cookie_name(relay_state)

    try:
        response = await _complete_saml_login(request, provider, form, relay_state, cookie_name)
    except HTTPException as exc:
        if cookie_name not in request.cookies:
            raise
        response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
    except Exception as exc:
        # Answered here rather than by the default 500 handler, whose response cannot carry the
        # cookie deletion. The audit gets the exception type only; the traceback goes to the log.
        # Fixed message: the provider id is in the audit event, not interpolated here.
        logger.exception("Unexpected error in the SAML ACS")
        emit_audit_event("auth.saml_acs_error", actor="<anonymous>", detail={"provider": provider.id, "error": type(exc).__name__}, status="denied")
        response = JSONResponse({"detail": REFUSED}, status_code=500)
    if cookie_name in request.cookies:
        _clear_binding_cookie(response, provider, sp_base_url(request), cookie_name)
    return response


async def _complete_saml_login(request: Request, provider: ProviderConfig, form: Dict[str, str], relay_state: str, cookie_name: str) -> Response:
    """The ACS itself, less the binding cookie's cleanup (see :func:`saml_acs`)."""
    from mlflow_oidc_auth.routers.auth import _build_ui_url, _open_server_session, _provision_login, _retire_previous_login

    attempt = store.consume_auth_state(relay_state)
    if attempt is None or attempt.provider_id != provider.id:
        # Unknown, expired, already used, or started at a different provider. A RelayState minted
        # for provider A and delivered to B's ACS is the SAML shape of a mix-up.
        raise _refuse("auth.saml_relaystate_rejected", provider, "RelayState names no live login attempt for this provider")

    verdict = _binding_verdict(request, attempt, cookie_name)
    # Either way the row is already consumed. Audited apart so a timeout or a cookie-blocking
    # browser does not read as an attack in the trail.
    if verdict == BINDING_MISSING:
        raise _refuse("auth.saml_binding_missing", provider, "no browser-binding cookie arrived for this login attempt")
    if verdict != BINDING_OK:
        # A live attempt, delivered with a nonce that is not this attempt's: login CSRF.
        raise _refuse("auth.saml_binding_rejected", provider, "the browser posting the response did not start this login attempt")

    base_url = sp_base_url(request)
    try:
        identity = process_response(provider, base_url, form, relay_state)
    except SamlError as exc:
        raise _refuse("auth.saml_response_rejected", provider, exc.reason)

    try:
        first_use = store.record_saml_assertion(identity.assertion_id, provider.id, datetime.fromtimestamp(identity.replay_until, tz=timezone.utc))
    except Exception as exc:
        # Fail closed: an assertion that cannot be recorded cannot be proven unused.
        logger.error("Could not record SAML assertion for provider '%s': %s", provider.id, type(exc).__name__)
        raise HTTPException(status_code=503, detail=REFUSED)
    if not first_use:
        raise _refuse("auth.saml_replay_rejected", provider, "the assertion was already consumed")

    session = request.session
    # Same placement as the OIDC callback: after the response is proven, before anything of
    # this login is written. Usually a no-op here — the cross-site POST carries no cookie.
    _retire_previous_login(session)

    username, display_name, userinfo, groups = _identity_to_login(provider, identity)
    try:
        username, errors = _provision_login(
            provider,
            username=username,
            display_name=display_name,
            userinfo=userinfo,
            user_groups=groups,
            access_token=None,
            method="saml",
        )
    except Exception as exc:
        logger.error("User/group management error during SAML login: %s", exc)
        username, errors = None, ["Failed to update user/groups"]
    if errors or not username:
        return RedirectResponse(url=_build_ui_url(request, "/auth", {"error": errors or ["Authentication failed"]}), status_code=302)

    tokens = SessionTokens(
        provider_id=provider.id,
        expires_at=identity.session_not_on_or_after,
        saml_name_id=identity.name_id,
        saml_name_id_format=identity.name_id_format,
        saml_session_index=identity.session_index,
    )
    try:
        session["session_id"] = _open_server_session(username, provider_id=provider.id, tokens=tokens)
    except Exception as exc:
        logger.error("Could not open a session for %s: %s", username, exc)
        session.clear()
        return RedirectResponse(url=_build_ui_url(request, "/auth", {"error": "session_error"}), status_code=302)
    session["authenticated"] = True

    logger.info("User %s authenticated successfully via SAML provider '%s'", username, provider.id)
    emit_audit_event("auth.login", actor=username, detail={"method": "saml", "provider": provider.id})

    redirect = attempt.redirect_after_login
    if not redirect:
        redirect = _build_ui_url(request, "/user") if config.DEFAULT_LANDING_PAGE_IS_PERMISSIONS else str(request.base_url).rstrip("/")
    return RedirectResponse(url=redirect, status_code=302)


def saml_logout_context(request: Request, session_id: Optional[str]) -> Optional[Tuple[ProviderConfig, Optional[SessionTokens]]]:
    """The SAML provider and tokens behind ``session_id``, when a SAML login opened it.

    Read by ``/logout`` *before* it revokes the session — a revoked row no longer resolves.
    Best effort: logout never fails over this.
    """
    if not session_id:
        return None
    try:
        resolved = getattr(getattr(request, "state", None), "resolved_session", None)
        if resolved is None or getattr(resolved, "session_id", session_id) != session_id:
            resolved = store.resolve_auth_session(session_id)
        if resolved is None:
            return None
        provider = config.AUTH_PROVIDERS.by_id(resolved.provider_id or "")
        if provider is None or provider.type != "saml":
            return None
        tokens = get_token_vault().decrypt(getattr(resolved, "encrypted_tokens", None))
        if tokens is not None and tokens.provider_id not in (None, provider.id):
            tokens = None
        return provider, tokens
    except Exception as exc:
        logger.debug("Could not read the session's SAML context for logout: %s", type(exc).__name__)
        return None


def saml_logout_redirect(request: Request, provider: ProviderConfig, tokens: Optional[SessionTokens]) -> Optional[str]:
    """The IdP LogoutRequest URL for SP-initiated SLO, or None when there is none to send.

    Called only after the local session is revoked and the cookie cleared, so a None here — no
    SLO endpoint, no NameID, the request failed to build — costs the user nothing but the IdP
    session, which they still hold with the IdP either way.
    """
    if not provider.idp_slo_url or tokens is None or not tokens.saml_name_id or not saml_available():
        return None
    try:
        relay_state = store.create_auth_state(provider.id)
        return build_logout_redirect(
            provider,
            sp_base_url(request),
            name_id=tokens.saml_name_id,
            name_id_format=tokens.saml_name_id_format,
            session_index=tokens.saml_session_index,
            relay_state=relay_state,
        )
    except Exception as exc:
        logger.warning("Could not start SAML single logout at provider '%s': %s", provider.id, getattr(exc, "reason", type(exc).__name__))
        return None


def _revoke_for_logout_request(provider: ProviderConfig, logout: SamlLogoutRequest) -> Tuple[Optional[str], int, int]:
    """End the sessions an IdP LogoutRequest names. Returns ``(username, revoked, failed)``.

    Only sessions this provider opened are candidates, so a SAML logout never reaches the same
    user's OIDC sessions. Among them, those whose ``SessionIndex`` is listed — or all of them
    when the request lists none. A session whose tokens cannot be read (a rotated vault key) or
    that recorded no index is revoked too: over-revoking costs a re-login, while a session the
    IdP believes ended but that stays live here is the failure SLO exists to prevent.
    """
    username = store.user_identity_repo.get_username_by_identity(provider.id, logout.name_id)
    if not username:
        return None, 0, 0

    vault = get_token_vault()
    revoked = failed = 0
    for session_id, blob in store.list_live_auth_sessions_for_provider(username, provider.id):
        tokens = vault.decrypt(blob)
        if logout.session_indexes and tokens is not None and tokens.saml_session_index and tokens.saml_session_index not in logout.session_indexes:
            continue
        try:
            if store.revoke_auth_session(session_id):
                revoked += 1
        except Exception as exc:
            logger.error("Could not revoke a session during SAML single logout for %s: %s", username, type(exc).__name__)
            failed += 1
    return username, revoked, failed


@saml_router.get(f"{SLS_PATH}/{{provider_id}}")
async def saml_sls(request: Request, provider_id: str):
    """Single Logout Service (#329). HTTP-Redirect binding only.

    * ``SAMLResponse``: the IdP completing a logout this SP started. The local session is already
      gone; this only decides the landing page, after checking the response answers our request.
    * ``SAMLRequest``: the IdP asking us to end a user's sessions. Must be signed by the IdP. The
      matching sessions are revoked, then a LogoutResponse is sent back to the IdP.

    POST is refused (405): python3-saml verifies only redirect-binding signatures on logout
    messages, so a POST-bound LogoutRequest could never validate and a POST-bound LogoutResponse
    would be accepted with no signature check. The SP metadata advertises only HTTP-Redirect.
    """
    from mlflow_oidc_auth.routers.auth import _build_ui_url

    provider = _require_provider(provider_id)
    data = _query_data(request)
    query_string = request.url.query or None
    base_url = sp_base_url(request)

    if "SAMLResponse" in data and "SAMLRequest" not in data:
        relay_state = data.get("RelayState") or ""
        attempt = store.consume_auth_state(relay_state)
        if attempt is None or attempt.provider_id != provider.id:
            raise _refuse("auth.saml_relaystate_rejected", provider, "logout RelayState names no live attempt for this provider", detail=LOGOUT_REFUSED)
        try:
            process_logout_response(provider, base_url, data, query_string, relay_state)
        except SamlError as exc:
            raise _refuse("auth.slo_response_rejected", provider, exc.reason, detail=LOGOUT_REFUSED)
        return RedirectResponse(url=_build_ui_url(request, "/auth"), status_code=302)

    if "SAMLRequest" in data and "SAMLResponse" not in data:
        try:
            logout = process_logout_request(provider, base_url, data, query_string)
        except SamlError as exc:
            # Nothing is revoked for a request that did not validate.
            raise _refuse("auth.slo_request_rejected", provider, exc.reason, detail=LOGOUT_REFUSED)

        # Single use, recorded before anything is revoked: a leaked signed URL replayed later
        # must not end sessions opened since. Namespaced so it can never collide with an
        # assertion ID in the same table.
        try:
            first_use = store.record_saml_assertion(f"logout:{logout.request_id}", provider.id, datetime.fromtimestamp(logout.replay_until, tz=timezone.utc))
        except Exception as exc:
            logger.error("Could not record SAML LogoutRequest for provider '%s': %s", provider.id, type(exc).__name__)
            raise HTTPException(status_code=503, detail=LOGOUT_REFUSED)
        if not first_use:
            raise _refuse("auth.slo_replay_rejected", provider, "the LogoutRequest was already processed", detail=LOGOUT_REFUSED)

        username, revoked, failed = None, 0, 0
        try:
            username, revoked, failed = _revoke_for_logout_request(provider, logout)
        except Exception as exc:
            logger.error("SAML single logout for provider '%s' failed: %s", provider.id, type(exc).__name__)
            failed += 1
        if failed:
            # The IdP retries a refused logout. Left recorded, the retry would be refused as a
            # replay and the session it names would stay live for good — so a failed attempt
            # releases the ID. What it did revoke stays revoked; a retry only finishes the job.
            try:
                store.release_saml_assertion(f"logout:{logout.request_id}")
            except Exception as exc:
                logger.error("Could not release SAML LogoutRequest for provider '%s' after a failed logout: %s", provider.id, type(exc).__name__)
        emit_audit_event(
            "auth.slo_idp_initiated",
            actor=username or "<unknown>",
            resource_type="user" if username else None,
            resource_id=username,
            detail={"provider": provider.id, "revoked": revoked, "failed": failed, "session_indexes": len(logout.session_indexes)},
            status="denied" if failed else "success",
        )
        if failed:
            # Telling the IdP "success" while a session it named is still live would be the
            # one wrong answer. Whatever could be revoked, was.
            raise HTTPException(status_code=400, detail=LOGOUT_REFUSED)
        return RedirectResponse(url=logout.response_url, status_code=302, headers={"Cache-Control": "no-store"})

    raise HTTPException(status_code=400, detail=LOGOUT_REFUSED)


@saml_router.get(f"{METADATA_PATH}/{{provider_id}}")
async def saml_metadata(request: Request, provider_id: str):
    """This SP's metadata for ``provider_id``, for the IdP administrator to import.

    Unauthenticated by necessity (the IdP side is configured before anyone can log in) and
    harmless: entity id, endpoint URLs and the public signing certificate — nothing secret.
    """
    provider = _require_provider(provider_id)
    try:
        document = sp_metadata(provider, sp_base_url(request))
    except Exception as exc:
        logger.error("Could not generate SAML metadata for provider '%s': %s", provider.id, getattr(exc, "reason", type(exc).__name__))
        raise HTTPException(status_code=500, detail="SAML metadata is not available")
    return Response(content=document, media_type="application/samlmetadata+xml", headers={"Cache-Control": "no-store"})
