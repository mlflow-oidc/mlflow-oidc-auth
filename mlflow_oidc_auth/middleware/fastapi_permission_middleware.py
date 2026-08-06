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

from mlflow_oidc_auth.logger import get_logger
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

    return None


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
        path = request.url.path

        # Find validator for this route — returns None for Flask-handled routes
        validator = _find_fastapi_validator(path)
        if validator is None:
            return await call_next(request)

        # Check authentication context (already set by AuthMiddleware)
        username = getattr(request.state, "username", None)
        if not username:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
                headers={"WWW-Authenticate": 'Basic realm="mlflow"'},
            )

        # Admins have full access
        is_admin = getattr(request.state, "is_admin", False)
        if is_admin:
            return await call_next(request)

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

        return await call_next(request)
