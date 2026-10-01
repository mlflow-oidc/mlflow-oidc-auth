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
from contextvars import ContextVar
from concurrent.futures import ThreadPoolExecutor

from cachetools import TTLCache
from fastapi import Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities.auth_context import (
    AUTH_CONTEXT_KEY,
    AUTH_METHOD_BASIC,
    AUTH_METHOD_BEARER,
    AUTH_METHOD_WORKLOAD,
    AUTH_METHOD_SESSION,
    AuthContext,
)
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.middleware.route_path import is_unprotected_route, routed_path
from mlflow_oidc_auth.routers._prefix import API_PATH_PREFIXES
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode

from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.auth import validate_token
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils.group_detection import call_group_detection_plugin
from mlflow_oidc_auth.group_patterns import BY_PATTERN, admitting_rule, normalize_group_values
from mlflow_oidc_auth.utils.oidc_field_extraction import extract_username, extract_display_name, BEARER_TOKEN_SOURCE
from mlflow_oidc_auth.utils.service_accounts import INTERNAL_SOURCE

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


#: Set while authenticating when a bearer token came from a non-interactive provider (a Kubernetes
#: service account, a CI workload-identity issuer). Such a token is a workload's credential, not a
#: person signing in, so it is labelled apart from an IdP user token and may not issue access
#: tokens (issue #189).
_WORKLOAD_BEARER: ContextVar[bool] = ContextVar("mlflow_oidc_auth_workload_bearer", default=False)

#: Set while authenticating an IdP bearer token: ``(provider, subject)`` of the token, or
#: ``(_KUBERNETES_BEARER, provider)`` for a Kubernetes service-account token, which its own path
#: authorized.
#: Read by :func:`_service_account_denial` once the account is known.
_BEARER_IDENTITY: ContextVar[Optional[object]] = ContextVar("mlflow_oidc_auth_bearer_identity", default=None)
_KUBERNETES_BEARER = "kubernetes"


def _auth_method(request: Request, workload_bearer: bool = False) -> str:
    """The credential :meth:`AuthMiddleware._authenticate_user` tried, in the order it tries them."""
    auth_header = request.headers.get("authorization") or ""
    # Must stay in step with the scheme checks in ``_authenticate_user``.
    if auth_header.startswith("Basic "):
        return AUTH_METHOD_BASIC
    if auth_header.startswith("Bearer "):
        return AUTH_METHOD_WORKLOAD if workload_bearer else AUTH_METHOD_BEARER
    return AUTH_METHOD_SESSION


# Why an authenticated-looking request was turned away. Reported separately because a deleted
# account and a deactivated one are different operational events, and an operator reading the
# audit log should not have to guess which happened (issue #306).
DENIAL_UNKNOWN_USER = "unknown_user"
DENIAL_INACTIVE = "inactive"
DENIAL_LOOKUP_ERROR = "lookup_error"
DENIAL_SERVICE_ACCOUNT_SOURCE = "service_account_source"

DENIAL_AUDIT_EVENTS = {
    DENIAL_SERVICE_ACCOUNT_SOURCE: "auth.denied_service_account_source",
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


def _bearer_identity(provider, payload, username: str) -> Tuple[Optional[str], bool]:
    """The local user a bearer token may act as, or None to refuse it.

    With a single provider in the registry there is one identity space, and the username the claims
    produce is the user — as it always was, at no cost. With more than one — of any type, since a
    SAML login binds identities too — a token is held to what interactive login decides for the
    same provider (``routers/auth.py``, issue #309): the identity ``(provider, sub)`` decides, a
    bound identity reaches only its own user, and a name another provider's identity owns is
    refused — so a provider cannot reach an account by asserting its email or username. Read-only:
    unlike login it binds nothing (provisioning on first bearer authentication binds the account it
    creates). Fails closed.

    Parameters:
        provider: The provider that validated the token, or None if it could not be identified.
        payload: The validated claims.
        username: The username the configured claim fields produce.

    Returns:
        ``(username, creating)``: the username to authenticate as, or None when the token must be
        refused; and whether that is a user the identity would *create* — the caller accepts such
        a token only once the account exists and is bound to this identity
        (:func:`_bound_to_identity`).
    """
    from mlflow_oidc_auth.utils.bearer_identity_cache import bearer_identity_cache

    if len(config.AUTH_PROVIDERS.providers) <= 1:
        return username, False
    if provider is None:
        logger.warning("Refusing a bearer token: the provider that validated it could not be identified")
        return None, False

    subject = payload.get("sub")
    subject = subject.strip() if isinstance(subject, str) else ""
    key = "\x1f".join((provider.id, subject, username, str(payload.get("email")), str(payload.get("email_verified") is True)))
    cache = bearer_identity_cache()
    cached = cache.get(key)
    if cached is not None:
        return cached or None, False
    resolved, creating = _resolve_bearer_identity(provider, subject, payload, username)
    if not creating:
        cache.set(key, resolved or "")
    return resolved, creating


def _unbound_person(username: str) -> bool:
    """Whether ``username`` is an existing, active, non-admin person's account no identity is bound to.

    The identity migration's placeholder (``default`` with the username as its subject) is not a
    binding. A service account never counts: how it signs in is its own setting
    (:func:`_service_account_denial`).
    """
    try:
        profile = store.get_user_profile(username)
        if getattr(profile, "is_service_account", False) or getattr(profile, "is_admin", False) or not getattr(profile, "active", True):
            return False
        return not store.user_identity_repo.has_real_binding(username)
    except Exception:
        return False


def _adoptable_by(provider, username: str) -> bool:
    """Whether a provider with ``bearer_adopts_unbound_accounts`` may adopt ``username``.

    Only an account no identity has ever been recorded for — not even the identity migration's
    placeholder, so a person from before identities were recorded is not adoptable; an administrator
    who means it removes the placeholder first (``DELETE /users/{username}/identities``) — and only
    where the email-domain rule lets this provider create the account: never in a domain other
    providers' accounts own, unless listed in its ``allowed_email_domains``.
    """
    from mlflow_oidc_auth.provisioning_policy import _squats_a_domain

    if not _unbound_person(username):
        return False
    try:
        if store.user_identity_repo.list_identities_for_username(username):
            return False
        owners = lambda domain: store.user_identity_repo.providers_in_email_domain(domain, exclude_username=username)  # noqa: E731
        return _squats_a_domain(provider, username, owners) is None
    except Exception:
        return False


def _is_service_account(username: str) -> bool:
    try:
        return bool(getattr(store.get_user_profile(username), "is_service_account", False))
    except Exception:
        return False


def _service_account_denial(username: str, is_service_account: bool, source: Optional[str], method: str, bearer_identity, is_admin: bool = False) -> str:
    """Why a service account may not use this credential, or ``""`` when it may.

    A service account signs in one way only (``users.service_account_source``):

    * ``internal`` — with access tokens this plugin issues (basic auth); no IdP token reaches it,
      whatever username it claims;
    * a provider id — with that provider's tokens only, and only for the subject bound to it; the
      first token from that provider binds its subject when none is bound yet. Its lifecycle lives
      in the IdP, so access tokens this plugin issued do not work for it.

    A Kubernetes service account's token was authorized on its own path (namespace allowlist) and
    is not judged again here. A person's account is never judged here.

    Parameters:
        username: The authenticated account.
        is_service_account: Whether it is a service account.
        source: Its ``service_account_source``.
        method: The credential (``AUTH_METHOD_*``).
        bearer_identity: :data:`_BEARER_IDENTITY` for this request.
        is_admin: Whether the account is an administrator: one is never bound by a first token.
    """
    if not is_service_account:
        return ""
    recorded = source
    source = source or INTERNAL_SOURCE
    if method == AUTH_METHOD_BASIC:
        return "" if source == INTERNAL_SOURCE else "an external service account signs in with its identity provider's tokens only"
    if method not in (AUTH_METHOD_BEARER, AUTH_METHOD_WORKLOAD):
        return "a service account does not sign in interactively"
    if isinstance(bearer_identity, tuple) and bearer_identity[0] == _KUBERNETES_BEARER:
        # Authorized on its own path (namespace allowlist), and only for the accounts its own
        # cluster provider created: a second cluster allowing the same namespace, or an account an
        # administrator has re-pointed, is refused.
        from mlflow_oidc_auth.utils.service_accounts import KUBERNETES_SOURCE

        cluster = bearer_identity[1]
        # No source recorded: a Kubernetes account a replica on an older release created during a
        # rolling upgrade — reached on this path only for a Kubernetes-derived username.
        if recorded is None:
            return ""
        return (
            ""
            if source in (KUBERNETES_SOURCE, getattr(cluster, "id", None))
            else f"this service account does not sign in through '{getattr(cluster, 'id', '?')}'"
        )
    if not isinstance(bearer_identity, tuple) or source == INTERNAL_SOURCE:
        return "an internal service account signs in with access tokens issued for it only"
    provider, subject = bearer_identity
    if provider is None:
        return "the provider that validated the token could not be identified"
    if source != provider.id:
        return f"this service account signs in through provider '{source}' only"
    if not subject:
        return "the token asserts no subject"
    try:
        return _external_binding_denial(username, provider, subject, is_admin)
    except Exception as e:
        # Fail closed: a binding that cannot be read or written is no binding.
        logger.warning("Could not check the binding of service account %s: %s", username, type(e).__name__)
        return "the service account's binding could not be checked"


def _external_binding_denial(username: str, provider, subject: str, is_admin: bool) -> str:
    """The subject check of :func:`_service_account_denial` for an external service account."""
    from mlflow_oidc_auth.utils.bearer_identity_cache import bearer_identity_cache

    cache = bearer_identity_cache()
    key = "\x1fsa\x1f".join((provider.id, subject, username))
    if cache.get(key):
        return ""
    # The identity migration's placeholder (default, username) is not a subject binding.
    subjects = [s for p, s in store.user_identity_repo.list_identities_for_username(username) if p == provider.id and not (p == "default" and s == username)]
    if subjects and subject not in subjects:
        return "this service account is bound to another subject of its provider"
    if not subjects:
        if is_admin:
            # An administrator account is bound when created; whoever could mint a token naming
            # it first must not get to choose its subject.
            return "an external administrator service account has no subject bound"
        # The first token from its provider binds the account to that subject.
        store.user_identity_repo.link(provider.id, subject, username, allow_additional_provider=True)
        # Two first tokens can race: the earliest binding wins, and a later one is taken back.
        first = next(s for p, s in store.user_identity_repo.list_identities_for_username(username) if p == provider.id)
        if first != subject:
            store.user_identity_repo.unlink(provider.id, subject, username)
            return "this service account is bound to another subject of its provider"
        emit_audit_event(
            "auth.identity_adopted", actor=username, resource_type="user", resource_id=username, detail={"provider": provider.id, "method": "bearer"}
        )
    cache.set(key, "1")
    return ""


def _bound_to_identity(provider, payload, username: str) -> bool:
    """Whether the token's identity is now bound to ``username``.

    Checked after provisioning for a token whose identity would create its user: only an account
    this identity owns is accepted. Without provisioning nothing creates it, so the token is refused
    (the user would not exist anyway); with it, a failed bind — or another identity claiming the
    name in between — is refused rather than served.
    """
    from mlflow_oidc_auth.provider_registry import DEFAULT_PROVIDER_ID

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        # Only the deployment's own provider gets here without a subject; it names accounts by
        # the configured claim fields, as it always did.
        return provider.id == DEFAULT_PROVIDER_ID
    try:
        return store.user_identity_repo.get_username_by_identity(provider.id, subject.strip()) == username
    except Exception as e:
        logger.warning("Refusing a bearer token from provider '%s': the identity binding could not be read (%s)", provider.id, type(e).__name__)
        return False


def _resolve_bearer_identity(provider, subject: str, payload, username: str) -> Tuple[Optional[str], bool]:
    """The uncached decision behind :func:`_bearer_identity`.

    Returns:
        ``(username or None, creating)``. A decision to reach an existing user, and a refusal, are
        cached by the caller. One that would *create* a user is not: until the account exists the
        name is free, and once another identity claims it the answer must change at once.
    """
    from mlflow_oidc_auth.identity_resolution import IdentityDecision, Resolution, resolve_identity
    from mlflow_oidc_auth.provider_registry import DEFAULT_PROVIDER_ID
    from mlflow_oidc_auth.provisioning_policy import apply_provisioning_policy

    try:
        if not subject:
            if provider.id != DEFAULT_PROVIDER_ID:
                logger.warning("Refusing a bearer token from provider '%s': it asserts no subject", provider.id)
                return None, False
            # As on login: the deployment's own provider without a subject names accounts by the
            # configured claim fields, as it always did.
            decision = IdentityDecision(Resolution.CREATE, reason="no subject asserted")
        else:
            decision = resolve_identity(provider, subject, payload, store.user_identity_repo, user_lookup=store.has_user, username=username)

        def providers_bound_to(name: str) -> list:
            try:
                return list(store.user_identity_repo.list_providers_for_username(name))
            except Exception:
                # An unknown binding set must not read as "bound to nobody".
                return ["<unknown>"]

        if decision.resolution is not Resolution.MATCHED and provider.id != DEFAULT_PROVIDER_ID and store.has_user(username):
            # An existing account this identity is not bound to.
            if _is_service_account(username):
                # A service account's own setting decides, once the request is authenticated
                # (_service_account_denial): which provider and subject it accepts.
                return username, False
            # (Not over a refusal: an email-bound provider's domain policy still decides.)
            adoptable = decision.resolution is Resolution.CREATE and getattr(provider, "bearer_adopts_unbound_accounts", False)
            if adoptable and _adoptable_by(provider, username):
                # The provider opted in: bind the account to this identity on first use (for one
                # its bearer provisioning created before identities were bound), so afterwards
                # only this identity reaches it.
                store.user_identity_repo.link(provider.id, subject, username, allow_additional_provider=True)
                logger.info("Bound an unbound account to provider '%s' on its first bearer use", provider.id)
                emit_audit_event(
                    "auth.identity_adopted", actor=username, resource_type="user", resource_id=username, detail={"provider": provider.id, "method": "bearer"}
                )
                return username, False
        outcome = apply_provisioning_policy(
            provider,
            decision,
            derived_username=username,
            user_exists=store.has_user,
            providers_bound_to=providers_bound_to,
            providers_in_domain=lambda domain: store.user_identity_repo.providers_in_email_domain(domain),
        )
    except Exception as e:
        logger.warning("Refusing a bearer token from provider '%s': identity could not be resolved (%s)", provider.id, type(e).__name__)
        # Not cached: a transient failure must not refuse the identity for a whole TTL.
        return None, True
    if not outcome.allowed:
        logger.warning("Refusing a bearer token from provider '%s': %s", provider.id, outcome.reason)
        emit_audit_event(
            "auth.identity_refused",
            actor=username,
            resource_type="user",
            resource_id=username,
            detail={"provider": provider.id, "reason": outcome.reason, "method": "bearer"},
            status="denied",
        )
        return None, False
    return outcome.username or username, bool(outcome.create)


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
            path: Routed path (``routed_path(request.scope)``), not the raw request path

        Returns:
            True if the route is unprotected, False otherwise
        """
        return is_unprotected_route(path)

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

        # Derive groups from the token, mirroring the login flow's group resolution. A plugin
        # that declares a ``token_response`` parameter also receives the validated claims under
        # ``claims``; a plugin written against the original single-argument signature is
        # unaffected (#250).
        try:
            if config.OIDC_GROUP_DETECTION_PLUGIN:
                user_groups = call_group_detection_plugin(config.OIDC_GROUP_DETECTION_PLUGIN, token, {"access_token": token, "claims": payload})
            else:
                user_groups = payload.get(config.OIDC_GROUPS_ATTRIBUTE, [])
            user_groups = normalize_group_values(user_groups)
        except Exception as e:
            logger.warning("Failed to read groups for bearer provisioning of %s: %s", username, type(e).__name__)
            return

        from mlflow_oidc_auth.provisioning_policy import admin_from_claims, groups_to_apply

        # Same authorization gate as interactive login (routers/auth.py): the user must be an
        # admin-group member *by this provider's say-so* or an allowed-group member. Otherwise do
        # NOT provision — a bearer token must never create an account interactive login would
        # reject. An admin group name only admits when the provider may confer admin (#318): a
        # provider configured ``admin_source: none`` — a tenant whose group names you do not
        # control — gets no say through it here either.
        may_be_admin = admin_from_claims(provider, user_groups, config.OIDC_ADMIN_GROUP_NAME)
        admission = None if may_be_admin else admitting_rule(user_groups, config.OIDC_GROUP_NAME, config.OIDC_GROUP_NAME_PATTERN)
        if not may_be_admin and admission is None:
            logger.info("Bearer user %s is in no authorized group; not provisioning (parity with interactive login)", username)
            return

        # Login creates an unknown user only for a provider whose provisioning is ``jit``; with
        # ``scim`` the directory decides who exists, and a token must not either.
        if provider.provisioning != "jit":
            logger.info(
                "Not provisioning %s: provider '%s' has provisioning '%s' (parity with interactive login)", username, provider.id, provider.provisioning
            )
            return

        # Admin is conferred from a token only when the operator has explicitly opted in as well.
        is_admin = may_be_admin and config.OIDC_TRUST_BEARER_GROUP_CLAIMS
        # The membership login would write: namespaced as ``<provider-id>:<group>`` for any provider
        # but the deployment's own, so another provider's group never joins a local group of the
        # same name, and nothing at all for a provider configured ``group_sync: none``.
        groups = groups_to_apply(provider, user_groups, [], is_new_user=True)
        display_name, display_name_error = extract_display_name(payload, source=BEARER_TOKEN_SOURCE)
        if display_name_error:
            logger.debug("Bearer provisioning of %s falling back to username as display name: %s", username, display_name_error)
            display_name = username
        try:
            import mlflow_oidc_auth.user as user_module

            # Attributed like an interactive login from the same provider (#360), so the guard sees
            # who is writing and the memberships are owned by that provider rather than ``manual``.
            written_by = f"oidc:{provider.id}"
            user_module.create_user(username=username, display_name=display_name, is_admin=is_admin, written_by=written_by)
            if groups is not None:
                arrived = user_module.populate_groups(group_names=groups, written_by=written_by)
                user_module.update_user(username=username, group_names=groups, written_by=written_by)
                # Groups this created get their workspace group rules (#418), as on login.
                if arrived:
                    from mlflow_oidc_auth.workspace_rules import apply_rules_for_groups

                    apply_rules_for_groups(arrived, source=written_by)
            # Bound like a login binds it, so this account answers to this provider's subject
            # alone and another provider cannot later adopt it by asserting the same name. A bind
            # that fails (the subject already names another account) leaves the account unbound:
            # with several providers its token is then refused (_bound_to_identity).
            subject = payload.get("sub")
            if isinstance(subject, str) and subject.strip():
                try:
                    store.user_identity_repo.link(provider.id, subject.strip(), username)
                except Exception as e:
                    logger.warning("Bearer provisioning of %s could not bind its identity: %s", username, type(e).__name__)
            logger.info("Provisioned bearer user %s (admin=%s, groups=%d) on first authentication", username, is_admin, len(groups or []))
            if admission is not None and admission.kind == BY_PATTERN:
                emit_audit_event(
                    "auth.admitted_by_group_pattern",
                    actor=username,
                    resource_type="user",
                    resource_id=username,
                    detail={"provider": provider.id, "method": "bearer", "pattern": admission.rule, "group": admission.group},
                )
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

            # Attributed to the Kubernetes provider (#360): the namespace group membership is its,
            # not ``manual``, so no other source's sync can quietly remove it under ``enforce``.
            written_by = f"oidc:{provider.id}"
            user_module.create_user(
                username=username,
                display_name=display_name,
                is_admin=False,
                is_service_account=True,
                written_by=written_by,
                # Its cluster provider's alone: reached by that provider's tokens on their own path.
                service_account_source=provider.id,
            )
            user_module.populate_groups(group_names=[group], written_by=written_by)
            user_module.update_user(username=username, group_names=[group], written_by=written_by)
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
            if provider is not None and not getattr(provider, "interactive", True):
                # A token-only issuer (Kubernetes, a CI workload-identity issuer) vouches for a
                # workload, not a person signing in; such a token may not issue access tokens.
                _WORKLOAD_BEARER.set(True)

            if provider is not None and provider.type == "k8s":
                # A service-account token names itself in ``sub`` and carries no email or
                # preferred_username, so the OIDC username fields do not apply to it (#314). The
                # identity is derived here rather than from OIDC_USERNAME_FIELD: a global field
                # list that had to include ``sub`` to make this work would also change how every
                # other provider's tokens are named.
                _WORKLOAD_BEARER.set(True)
                _BEARER_IDENTITY.set((_KUBERNETES_BEARER, provider))
                return self._authenticate_service_account(token, payload, provider)

            # Extract username from configured fields. extract_username guarantees a
            # non-empty, normalized username whenever it returns no error.
            username, error_msg = extract_username(payload, source=BEARER_TOKEN_SOURCE)
            if error_msg:
                return False, None, error_msg

            username, creating = _bearer_identity(provider, payload, username)
            if username is None:
                return False, None, "This account cannot be used here"

            self._maybe_provision_bearer_user(username, token, payload)
            if creating and not _bound_to_identity(provider, payload, username):
                return False, None, "This account cannot be used here"
            subject = payload.get("sub")
            _BEARER_IDENTITY.set((provider, subject.strip() if isinstance(subject, str) else ""))
            logger.debug(f"User {username} authenticated via bearer token")
            return True, username, ""
        except Exception as e:
            logger.warning("Bearer auth error: %s: %s", type(e).__name__, e)
            logger.debug("Bearer auth error traceback", exc_info=True)
            return False, None, "Invalid token"

    async def _authenticate_session(self, request: Request) -> Tuple[bool, Optional[str], str]:
        """
        Authenticate using session.

        Enforces the IdP-issued ``expires_at`` so a session cannot outlive the
        underlying token. When ``OIDC_USE_REFRESH_TOKEN`` is enabled and a refresh
        token is stored, an expired session is silently refreshed against the IdP
        before being rejected.

        Both live on the session row, encrypted, since #367 — not in the cookie.
        They arrive with the same joined lookup that resolves the session, so
        reading them costs no statement.

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

                    # A cookie from before #367 may still carry token material. Its refresh token
                    # is never used — only the session row's is — and is dropped at once.
                    if "refresh_token" in session:
                        session.pop("refresh_token", None)

                    from mlflow_oidc_auth.session.token_vault import SessionTokens, get_token_vault

                    encrypted_tokens = getattr(resolved, "encrypted_tokens", None)
                    tokens = get_token_vault().decrypt(encrypted_tokens)

                    # Its ``expires_at`` is different. A row opened by a release before #367 has
                    # no tokens, so the (signed) cookie holds the only IdP expiry this session
                    # has. Dropping it would let the session run to the row's lifetime with no
                    # IdP bound at all, so it is honoured as an upper bound — and kept until it
                    # passes or a new login replaces the session. Where the row has tokens, the
                    # row is authoritative and the cookie value is discarded.
                    legacy_expiry = session.get("expires_at")
                    legacy_bound = not encrypted_tokens and isinstance(legacy_expiry, (int, float)) and not isinstance(legacy_expiry, bool)
                    if not legacy_bound and "expires_at" in session:
                        session.pop("expires_at", None)
                    if legacy_bound and self._is_session_expired(SessionTokens(expires_at=int(legacy_expiry))):
                        # Nothing on the row to refresh with: the legacy session ends here.
                        logger.info("Legacy session expired for user %s; clearing session to force re-authentication", username)
                        session.clear()
                        return False, None, "Session expired"
                    # Tokens that exist but cannot be decrypted (key rotated, row tampered with)
                    # carry an expiry we can no longer read. Fail closed: treat the session as
                    # expired, which — with nothing to refresh with — sends the user to log in.
                    unreadable = bool(encrypted_tokens) and tokens is None
                    if unreadable or self._is_session_expired(tokens):
                        # Try a silent refresh first; only force re-login if it fails.
                        from mlflow_oidc_auth.routers.auth import refresh_session_with_idp

                        refreshed = await refresh_session_with_idp(session_id, resolved)
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

    @staticmethod
    def _is_session_expired(tokens) -> bool:
        """Return True when the IdP-issued ``expires_at`` (minus leeway) is in the past.

        ``tokens`` is the session's decrypted ``SessionTokens`` (or None). Returns False
        when no expiry is recorded — the IdP gave none, or the tokens are absent or
        unreadable — so the session's own lifetime bounds it, as before.
        """

        expires_at = getattr(tokens, "expires_at", None) if tokens is not None else None
        if isinstance(expires_at, bool) or not isinstance(expires_at, (int, float)):
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
        """``(is_admin, is_active, denial_reason)``; see :meth:`_get_user_auth_facts`."""
        is_admin, is_active, denial_reason, _ = self._get_user_auth_facts(username)
        return is_admin, is_active, denial_reason

    def _get_user_auth_facts(self, username: str) -> Tuple[bool, bool, str, Tuple[bool, Optional[str]]]:
        """Read the facts the auth path needs about a user, in one lookup.

        All come off the profile row that is already fetched on every authenticated request, so
        ``active`` and the service-account facts cost nothing: they are in its ``load_only`` list,
        and the per-request statement count stays at the #305 budget of 2.

        Args:
            username: Username to check

        Returns:
            ``(is_admin, is_active, denial_reason, (is_service_account, service_account_source))``.
            ``denial_reason`` is ``""`` when the user may authenticate, and otherwise names why not, so the caller can report a deleted
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
                return False, False, DENIAL_UNKNOWN_USER, (False, None)
            logger.error("Error reading auth state for %s: %s", username, e)
            return False, False, DENIAL_LOOKUP_ERROR, (False, None)
        except Exception as e:
            logger.error("Error reading auth state for %s: %s", username, e)
            return False, False, DENIAL_LOOKUP_ERROR, (False, None)

        if not user:
            return False, False, DENIAL_UNKNOWN_USER, (False, None)
        source = getattr(user, "service_account_source", None)
        account = (getattr(user, "is_service_account", False) is True, source if isinstance(source, str) else None)
        if not user.active:
            return bool(user.is_admin), False, DENIAL_INACTIVE, account
        return bool(user.is_admin), True, "", account

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
        # Decide on the path the router will dispatch, which excludes any root_path prefix
        # recorded for the deployment. ProxyHeadersMiddleware runs outside this middleware, so a
        # forwarded prefix from a trusted proxy is already reflected in the scope here.
        path = routed_path(request.scope)

        # Skip authentication for unprotected routes
        if self._is_unprotected_route(path):
            return await call_next(request)

        # Attempt authentication
        workload_marker = _WORKLOAD_BEARER.set(False)
        identity_marker = _BEARER_IDENTITY.set(None)
        try:
            is_authenticated, username, error_msg = await self._authenticate_user(request)
            workload_bearer = _WORKLOAD_BEARER.get()
            bearer_identity = _BEARER_IDENTITY.get()
        finally:
            _WORKLOAD_BEARER.reset(workload_marker)
            _BEARER_IDENTITY.reset(identity_marker)

        if is_authenticated and username:
            resolved = getattr(request.state, "resolved_session", None)
            if resolved is not None:
                # Already read, in the same statement that validated the session.
                is_admin, is_active = resolved.is_admin, resolved.is_active
                denial_reason = "" if is_active else DENIAL_INACTIVE
                if is_active and getattr(resolved, "is_service_account", False) is True:
                    # A service account never signs in through the browser; a session it holds
                    # (from before the account became one) is not honoured.
                    logger.info("Authentication denied for service account %s on %s: a browser session", username, path)
                    if _should_audit_denial(username, DENIAL_SERVICE_ACCOUNT_SOURCE):
                        emit_audit_event(
                            DENIAL_AUDIT_EVENTS[DENIAL_SERVICE_ACCOUNT_SOURCE],
                            actor=username,
                            resource_type="user",
                            resource_id=username,
                            detail={"reason": "a service account does not sign in interactively"},
                            status="denied",
                        )
                    return await self._deny(request, path)
            else:
                is_admin, is_active, denial_reason, account = self._get_user_auth_facts(username)
                if is_active:
                    method = _auth_method(request, workload_bearer=workload_bearer)
                    refusal = _service_account_denial(username, account[0], account[1], method, bearer_identity, is_admin)
                    if refusal:
                        logger.info("Authentication denied for service account %s on %s: %s", username, path, refusal)
                        if _should_audit_denial(username, DENIAL_SERVICE_ACCOUNT_SOURCE):
                            emit_audit_event(
                                DENIAL_AUDIT_EVENTS[DENIAL_SERVICE_ACCOUNT_SOURCE],
                                actor=username,
                                resource_type="user",
                                resource_id=username,
                                detail={"reason": refusal},
                                status="denied",
                            )
                        return await self._deny(request, path)

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
            # Which credential authenticated this request. Token issuance refuses a request that
            # authenticated with an access token (issue #189); see ``require_interactive_login``.
            request.state.auth_method = _auth_method(request, workload_bearer=workload_bearer)

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
