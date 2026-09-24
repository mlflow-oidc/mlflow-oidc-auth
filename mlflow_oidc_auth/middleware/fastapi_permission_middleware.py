"""
FastAPI Permission Middleware for MLflow OIDC Auth.

This middleware enforces authorization on FastAPI-native routes (gateway invocations,
OTel trace ingestion, assistant, job API) that bypass Flask and therefore bypass
the Flask ``before_request_hook``.

It mirrors the upstream ``add_fastapi_permission_middleware`` from
``mlflow/server/auth/__init__.py`` but uses our OIDC-based authentication context
(set by ``AuthMiddleware``) instead of upstream's Basic-Auth-only approach.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Match, Mount

from mlflow_oidc_auth.bridge.user import clear_auth_context, set_auth_context
from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware import AuthAwareWSGIMiddleware
from mlflow_oidc_auth.middleware.route_path import is_unprotected_route, routed_path
from mlflow_oidc_auth.utils.permissions import can_use_gateway_endpoint

logger = get_logger()


# ---------------------------------------------------------------------------
# Route patterns that need the request body to extract the endpoint name
# (passthrough / chat-completion / embeddings / responses / messages)
# ---------------------------------------------------------------------------
_ROUTES_NEEDING_BODY = frozenset(
    (
        "/gateway/mlflow/v1/chat/completions",
        "/gateway/openai/v1/chat/completions",
        "/gateway/openai/v1/embeddings",
        "/gateway/openai/v1/responses",
        "/gateway/anthropic/v1/messages",
    )
)

# Compiled patterns for Gemini routes that embed the endpoint name in the URL
_GEMINI_GENERATE = re.compile(r"^/gateway/gemini/v1beta/models/([^/:]+):generateContent$")
_GEMINI_STREAM = re.compile(r"^/gateway/gemini/v1beta/models/([^/:]+):streamGenerateContent$")

# Pattern: /gateway/{endpoint_name}/mlflow/invocations
_INVOCATIONS_RE = re.compile(r"^/gateway/([^/]+)/mlflow/invocations$")

# MCP server registry, mounted by MLflow under both the API and the UI prefix
# (mlflow.server.mcp_server_api.get_mcp_server_api_route_prefixes)
_MCP_SERVER_PREFIXES = ("/api/3.0/mlflow/mcp-servers", "/ajax-api/3.0/mlflow/mcp-servers")


# ---------------------------------------------------------------------------
# Endpoint-name extraction (mirrors upstream _extract_gateway_endpoint_name)
# ---------------------------------------------------------------------------


def _extract_gateway_endpoint_name(path: str, body: dict[str, Any] | None) -> str | None:
    """Extract endpoint name from gateway routes.

    Supports:
    - ``/gateway/{endpoint_name}/mlflow/invocations``
    - Passthrough routes (endpoint in request body as ``model``)
    - Gemini routes (endpoint in URL path segment)
    """
    # Pattern 1: /gateway/{endpoint_name}/mlflow/invocations
    if match := _INVOCATIONS_RE.match(path):
        return match.group(1)

    # Pattern 2-6: Passthrough routes (endpoint in request body as "model")
    if path in _ROUTES_NEEDING_BODY:
        if body:
            return body.get("model")
        return None

    # Pattern 7-8: Gemini routes (endpoint in URL path)
    if match := _GEMINI_GENERATE.match(path):
        return match.group(1)
    if match := _GEMINI_STREAM.match(path):
        return match.group(1)

    return None


# ---------------------------------------------------------------------------
# Per-route validator factories
# ---------------------------------------------------------------------------


def _get_gateway_validator(
    path: str,
) -> Callable[[str, Request], Awaitable[bool]] | None:
    """Return an async validator for gateway invocation routes.

    Validates that the user has USE permission on the target gateway endpoint.
    """

    async def validator(username: str, request: Request) -> bool:
        body: dict[str, Any] | None = None
        if path in _ROUTES_NEEDING_BODY:
            try:
                body = await request.json()
                # Cache parsed body so the downstream route handler can reuse it
                # (Starlette request body can only be read once).
                request.state.cached_body = body
            except Exception:
                return False

        endpoint_name = _extract_gateway_endpoint_name(path, body)
        if endpoint_name is None:
            logger.warning("Gateway validator: no endpoint name found in request path %s", path)
            return False

        return can_use_gateway_endpoint(endpoint_name, username)

    return validator


def _get_otel_validator(path: str) -> Callable[[str, Request], Awaitable[bool]] | None:
    """Return an async validator for OTel trace ingestion routes.

    Requires UPDATE permission on the experiment identified by the
    ``X-Mlflow-Experiment-Id`` header.
    """

    async def validator(username: str, request: Request) -> bool:
        from mlflow_oidc_auth.utils import effective_experiment_permission

        experiment_id = request.headers.get("x-mlflow-experiment-id")
        if not experiment_id:
            logger.warning("OTel validator: missing X-Mlflow-Experiment-Id header")
            return False

        return effective_experiment_permission(experiment_id, username).permission.can_update

    return validator


def _get_require_authentication_validator() -> Callable[[str, Request], Awaitable[bool]]:
    """Return a validator that allows any authenticated user."""

    async def validator(username: str, request: Request) -> bool:
        return True

    return validator


def _get_mcp_server_registry_validator() -> Callable[[str, Request], Awaitable[bool]]:
    """Return a validator for the MCP server registry routes.

    The registry is a single catalog shared by every tenant, and there is no
    per-server permission model for it yet. Reading it is open to any
    authenticated user; mutating it is admin-only. Admins never reach this
    validator (the middleware short-circuits on ``is_admin``), so denying
    every write method here is what makes mutation admin-only.
    """

    async def validator(username: str, request: Request) -> bool:
        return request.method in ("GET", "HEAD")

    return validator


# ---------------------------------------------------------------------------
# Route → validator dispatcher
# ---------------------------------------------------------------------------


def _find_fastapi_validator(
    path: str,
) -> Callable[[str, Request], Awaitable[bool]] | None:
    """Find the validator for a FastAPI-native route.

    Returns a validator function for routes that need permission checks, or
    ``None`` if the route should be handled by Flask (WSGI fall-through).
    """
    if path.startswith("/gateway/"):
        return _get_gateway_validator(path)

    if path.startswith("/v1/traces"):
        return _get_otel_validator(path)

    if path.startswith("/ajax-api/3.0/jobs"):
        return _get_require_authentication_validator()

    if path.startswith("/ajax-api/3.0/mlflow/assistant"):
        return _get_require_authentication_validator()

    if path.startswith(_MCP_SERVER_PREFIXES):
        return _get_mcp_server_registry_validator()

    return None


# ---------------------------------------------------------------------------
# Which application serves a request
# ---------------------------------------------------------------------------


def _dispatches_to_flask_mount(request: Request) -> bool:
    """Return True when the router will hand this request to the Flask WSGI mount.

    Walks the application's routes in order, as the router does, and reports whether the first
    full match is the mount that wraps MLflow's Flask app. That mount authorizes every request
    itself (``before_request_hook`` denies without an ``AuthContext``); anything else — a FastAPI
    route, another mount, or no match at all — is the responsibility of this middleware.

    Parameters:
        request: Incoming request; ``request.scope["app"]`` is the application being served.

    Returns:
        True only when the request will be served by the Flask mount.
    """
    router = getattr(request.scope.get("app"), "router", None)
    for route in getattr(router, "routes", ()):
        match, _ = route.matches(request.scope)
        if match is Match.FULL:
            return isinstance(route, Mount) and isinstance(route.app, AuthAwareWSGIMiddleware)
    return False


def _authentication_required() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": "Authentication required"},
        headers={"WWW-Authenticate": 'Basic realm="mlflow"'},
    )


# ---------------------------------------------------------------------------
# Middleware registration
# ---------------------------------------------------------------------------


def add_fastapi_permission_middleware(app: FastAPI) -> None:
    """Add OIDC-aware permission middleware for FastAPI-native routes.

    This middleware runs AFTER ``AuthMiddleware`` (which has already set
    ``request.state.username`` / ``request.state.is_admin`` and the ASGI
    scope ``mlflow_oidc_auth`` dict).  It only activates for routes served
    directly by FastAPI (gateway, otel, assistant, job API) — all other
    requests fall through to the Flask WSGI mount where the Flask hooks
    handle authorization.
    """

    @app.middleware("http")
    async def fastapi_permission_middleware(request: Request, call_next):
        # Match validators on the path the router dispatches, never the raw request path.
        path = routed_path(request.scope)
        username = getattr(request.state, "username", None)

        # Find validator for this route — returns None for Flask-handled routes
        validator = _find_fastapi_validator(path)
        if validator is None:
            # Fail closed: AuthMiddleware only lets a request through without a user on an
            # unprotected route. Anything else served outside the Flask mount (which authorizes
            # on its own) must still carry an authenticated user, whether or not a validator
            # has been written for it yet.
            if not username and not is_unprotected_route(path) and not _dispatches_to_flask_mount(request):
                return _authentication_required()
            return await call_next(request)

        # Check authentication context (already set by AuthMiddleware)
        if not username:
            return _authentication_required()

        # Admins have full access
        is_admin = getattr(request.state, "is_admin", False)
        if is_admin:
            return await call_next(request)

        # Bridge AuthContext into ContextVar so downstream permission code
        # (e.g. _apply_workspace_fallback) can resolve the workspace even
        # though these routes never enter Flask
        auth_context = request.scope.get(AUTH_CONTEXT_KEY)
        auth_context_token = set_auth_context(auth_context) if isinstance(auth_context, AuthContext) else None

        # Run the validator
        try:
            if not await validator(username, request):
                return PlainTextResponse(
                    "Permission denied",
                    status_code=403,
                )
        except Exception as e:
            logger.error("FastAPI permission middleware error: %s", type(e).__name__)
            return PlainTextResponse(
                "Permission denied",
                status_code=403,
            )
        finally:
            if auth_context_token is not None:
                clear_auth_context(auth_context_token)

        return await call_next(request)
