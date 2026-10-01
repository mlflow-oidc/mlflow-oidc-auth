"""
FastAPI Permission Middleware for MLflow OIDC Auth.

This middleware enforces authorization on FastAPI-native routes (gateway invocations,
OTel trace ingestion, assistant, job API, MCP server registry) that bypass Flask and
therefore bypass the Flask ``before_request_hook``.

It mirrors the upstream ``add_fastapi_permission_middleware`` from
``mlflow/server/auth/__init__.py`` but uses our OIDC-based authentication context
(set by ``AuthMiddleware``) instead of upstream's Basic-Auth-only approach.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Match, Mount

from mlflow_oidc_auth.bridge.user import clear_auth_context, set_auth_context
from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware import AuthAwareWSGIMiddleware
from mlflow_oidc_auth.middleware.mcp_server_registry import finalize_mcp_response, get_mcp_server_validator, is_mcp_server_path
from mlflow_oidc_auth.middleware.route_path import is_unprotected_route, routed_path
from mlflow_oidc_auth.utils.permissions import can_use_gateway_endpoint
from mlflow_oidc_auth.validators.job_submission import can_submit_job

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
        # MLflow 3.17+: TypeSafe System One passthrough (mlflow.server.gateway_api)
        "/gateway/typesafe/v1/systemone",
    )
)

# MLflow 3.17+: OpenAI-compatible model discovery. Each listed model's ``id`` is a gateway endpoint
# name; the list is narrowed to the endpoints the caller may USE (see
# _filtered_gateway_models_response), as MLflow's own auth plugin does.
_GATEWAY_MODELS_PATH = "/gateway/mlflow/v1/models"

# Compiled patterns for Gemini routes that embed the endpoint name in the URL
_GEMINI_GENERATE = re.compile(r"^/gateway/gemini/v1beta/models/([^/:]+):generateContent$")
_GEMINI_STREAM = re.compile(r"^/gateway/gemini/v1beta/models/([^/:]+):streamGenerateContent$")

# Pattern: /gateway/{endpoint_name}/mlflow/invocations
_INVOCATIONS_RE = re.compile(r"^/gateway/([^/]+)/mlflow/invocations$")

# Pattern: /gateway/proxy/{endpoint_name}/{path:path} — MLflow's raw provider passthrough
# (mlflow.server.gateway_api.raw_proxy). The endpoint is the first segment after /proxy/; the rest
# is the provider path, which — like Starlette's ``{path:path}`` — may be empty.
_RAW_PROXY_RE = re.compile(r"^/gateway/proxy/([^/]+)/.*$")

# MLflow's FastAPI job API (mlflow.server.job_api.job_api_router)
_JOBS_PREFIX = "/ajax-api/3.0/jobs"
_JOBS_SEARCH_PATH = _JOBS_PREFIX + "/search"


# This plugin's credentials: the session cookie and the Basic/Bearer ``Authorization`` header.
# MLflow's gateway forwards the caller's headers to the endpoint's provider on its passthrough and
# proxy routes, stripping only its own ``X-MLflow-Authorization`` — see _strip_client_credentials.
_GATEWAY_PREFIX = "/gateway/"

# The gateway routes that never forward the caller's headers to a provider: MLflow's typed
# invocations and chat-completions handlers call the provider's own chat/embeddings methods, which
# send only the provider's headers. ``Authorization`` is kept on these, because a "sanitize"
# guardrail makes MLflow call back into its own invocations route with the caller's Authorization.
_TYPED_GATEWAY_ROUTE = re.compile(r"^/gateway/(?:[^/]+/mlflow/invocations|mlflow/v1/chat/completions)$")


def _strip_client_credentials(request: Request, path: str) -> None:
    """Remove this plugin's credentials from a gateway request before MLflow handles it.

    MLflow's AI gateway copies the caller's headers onto the request it sends to a third-party
    provider (``dict(request.headers)`` on the passthrough and proxy routes, merged under the
    provider's own headers). The session cookie would then reach every provider, and the caller's
    IdP token or access token would reach any provider that puts its API key in a header of its own
    (``api-key``, ``x-api-key``, ``x-goog-api-key``). Authentication and authorization have already
    run when this is called.

    The cookie is removed on every gateway route: nothing downstream reads it. ``Authorization`` is
    removed everywhere except the typed routes that never forward headers (``_TYPED_GATEWAY_ROUTE``)
    — including on any gateway route MLflow adds later, so an unknown route is the safe case. The
    one thing that costs: a sanitize guardrail on a passthrough or proxy route cannot call back into
    MLflow with the caller's token, so it fails closed.

    Mutates ``request.scope["headers"]``, which the route handler reads.
    """
    drop = {b"cookie"} if _TYPED_GATEWAY_ROUTE.match(path) else {b"cookie", b"authorization"}
    request.scope["headers"] = [(name, value) for name, value in request.scope.get("headers", []) if name.lower() not in drop]


# ---------------------------------------------------------------------------
# Endpoint-name extraction (mirrors upstream _extract_gateway_endpoint_name)
# ---------------------------------------------------------------------------


def _extract_gateway_endpoint_name(path: str, body: dict[str, Any] | None) -> str | None:
    """Extract endpoint name from gateway routes.

    Supports:
    - ``/gateway/{endpoint_name}/mlflow/invocations``
    - Passthrough routes (endpoint in request body as ``model``)
    - Gemini routes (endpoint in URL path segment)
    - ``/gateway/proxy/{endpoint_name}/{path}`` (raw provider passthrough)
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

    # Pattern 9: raw provider passthrough, endpoint in the first path segment after /proxy/
    if match := _RAW_PROXY_RE.match(path):
        return match.group(1)

    return None


# ---------------------------------------------------------------------------
# Per-route validator factories
# ---------------------------------------------------------------------------


def _get_gateway_validator(
    path: str,
) -> Callable[[str, Request], Awaitable[bool]] | None:
    """Return an async validator for gateway invocation routes.

    Validates that the user has USE permission on the target gateway endpoint. Model discovery
    names no endpoint: any authenticated user may list, and the response is filtered instead.
    """
    if path == _GATEWAY_MODELS_PATH:
        return _get_require_authentication_validator()

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


def _job_id_from_path(path: str) -> str | None:
    """Return the job id a job API path addresses, or None for the submit and search routes.

    ``GET /jobs/{job_id}`` and ``PATCH /jobs/cancel/{job_id}`` carry a job id. ``POST /jobs/``
    (submit) and ``POST /jobs/search`` do not. Any other path under the prefix is treated as
    addressing a job, so it goes through the ownership check and fails closed.

    Parameters:
        path: Routed request path, starting with the job API prefix.

    Returns:
        The job id, or None when the path addresses no single job.
    """
    tail = path[len(_JOBS_PREFIX) :].strip("/")
    if not tail or tail == "search":
        return None
    if tail.startswith("cancel/"):
        return tail[len("cancel/") :]
    return tail


def _job_creator(job_id: str) -> str | None:
    """Return the username recorded as the creator of a job, or None if it cannot be resolved.

    Parameters:
        job_id: The job id.

    Returns:
        The creator's username; None if the job does not exist, has no recorded creator, or the
        lookup fails.
    """
    try:
        from mlflow.server.jobs import get_job

        creator = getattr(get_job(job_id), "creator", None)
    except Exception:
        logger.debug("Could not resolve job creator for authorization")
        return None
    return creator if isinstance(creator, str) and creator else None


def _is_job_search(path: str, request: Request) -> bool:
    """True when the request is a job search, whose response is narrowed to the caller's jobs."""
    return request.method == "POST" and path.rstrip("/") == _JOBS_SEARCH_PATH


def _get_job_validator(path: str) -> Callable[[str, Request], Awaitable[bool]]:
    """Return a validator for MLflow's FastAPI job API.

    Jobs carry no experiment scope on this API, so the recorded creator is the boundary, as in
    MLflow's own auth plugin: fetching or cancelling a job by id requires being its creator
    (admins never reach the validator). A job that does not exist or has no recorded creator is
    denied. Searching jobs needs only authentication; the results are narrowed to the caller's
    own jobs after the handler runs. Submitting a job (``POST`` on the prefix) is authorized
    against the resources its params name (see ``validators.job_submission``). Any other method
    on the prefix is refused.
    """
    job_id = _job_id_from_path(path)

    async def validator(username: str, request: Request) -> bool:
        if job_id is None:
            if path[len(_JOBS_PREFIX) :].strip("/") == "search":
                return _is_job_search(path, request)
            if request.method != "POST":
                return False
            try:
                payload = await request.json()
            except Exception:
                return False
            return can_submit_job(payload, username)
        creator = _job_creator(job_id)
        return creator is not None and creator == username

    return validator


def _filter_job_search_response(username: str, body: bytes) -> bytes:
    """Keep only the jobs created by ``username`` in a job search response body.

    The creator is taken from each job's ``creator`` field when MLflow includes it, otherwise
    looked up in the job store. A job whose creator cannot be resolved is dropped.

    Parameters:
        username: The caller.
        body: The JSON body returned by the search handler.

    Returns:
        The filtered JSON body.

    Raises:
        ValueError: If the body is not a job search response.
    """
    data = json.loads(body)
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        raise ValueError("unexpected job search response")
    kept = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if "creator" in job:
            creator = job.get("creator")
        else:
            job_id = job.get("job_id")
            creator = _job_creator(str(job_id)) if job_id else None
        if creator is not None and creator == username:
            kept.append(job)
    data["jobs"] = kept
    return json.dumps(data).encode()


async def _filtered_job_search_response(username: str, response: Response) -> Response:
    """Buffer a job search response and return it narrowed to the caller's jobs.

    Non-2xx responses carry no job list and are returned unchanged. If the body cannot be
    filtered, an error is returned instead of the unfiltered list.
    """
    if not 200 <= response.status_code < 300:
        return response
    body = b"".join([chunk async for chunk in response.body_iterator])
    try:
        filtered = _filter_job_search_response(username, body)
    except Exception:
        logger.error("Failed to filter job search response")
        return JSONResponse(status_code=500, content={"detail": "Failed to filter response"})
    headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
    return Response(content=filtered, status_code=response.status_code, headers=headers, media_type=response.media_type)


def _is_gateway_models_list(path: str, request: Request) -> bool:
    """True for model discovery, whose response is narrowed to the endpoints the caller may USE."""
    return request.method == "GET" and path == _GATEWAY_MODELS_PATH


def _filter_gateway_models_response(username: str, body: bytes) -> bytes:
    """Keep only the models backed by gateway endpoints ``username`` may USE.

    Each model's ``id`` is the endpoint name MLflow's chat and passthrough routes take in
    ``model``. A model whose permission lookup fails is left out rather than shown.

    Raises:
        ValueError: The body is not a models list.
    """
    data = json.loads(body)
    models = data.get("data") if isinstance(data, dict) else None
    if not isinstance(models, list):
        raise ValueError("models response carries no data list")
    visible = []
    for model in models:
        endpoint_name = model.get("id") if isinstance(model, dict) else None
        if not isinstance(endpoint_name, str) or not endpoint_name:
            continue
        try:
            if can_use_gateway_endpoint(endpoint_name, username):
                visible.append(model)
        except Exception as e:
            logger.error("Gateway model discovery: permission check failed: %s", type(e).__name__)
    data["data"] = visible
    return json.dumps(data).encode()


async def _filtered_gateway_models_response(username: str, response: Response, auth_context: Any) -> Response:
    """Buffer a model discovery response and return it narrowed to the caller's usable endpoints.

    The caller's ``AuthContext`` is bridged while the permissions are resolved, as it is for the
    validators: with workspaces enabled, an endpoint with no grant of its own falls back to the
    caller's workspace permission, which cannot be found without it. Non-2xx responses carry no
    list and are returned unchanged; a body that cannot be filtered is an error, never the
    unfiltered list. Response headers are kept, repeated ones included.
    """
    if not 200 <= response.status_code < 300:
        return response
    body = b"".join([chunk async for chunk in response.body_iterator])
    token = set_auth_context(auth_context) if isinstance(auth_context, AuthContext) else None
    try:
        filtered = _filter_gateway_models_response(username, body)
    except Exception as e:
        logger.error("Failed to filter gateway model discovery response: %s", type(e).__name__)
        return JSONResponse(status_code=500, content={"detail": "Failed to filter response"})
    finally:
        if token is not None:
            clear_auth_context(token)
    filtered_response = Response(content=filtered, status_code=response.status_code, media_type="application/json", background=response.background)
    filtered_response.raw_headers.extend((k, v) for k, v in response.raw_headers if k.lower() not in (b"content-length", b"content-type"))
    return filtered_response


def _is_mcp_server_path(path: str) -> bool:
    """Whether ``path`` is on the MCP server registry, with or without MLflow's static prefix.

    See :mod:`mlflow_oidc_auth.middleware.mcp_server_registry`, which also holds the validator.
    """
    return is_mcp_server_path(path)


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

    if path.startswith(_JOBS_PREFIX):
        return _get_job_validator(path)

    if path.startswith("/ajax-api/3.0/mlflow/assistant"):
        return _get_require_authentication_validator()

    if _is_mcp_server_path(path):
        return get_mcp_server_validator(path)

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
            # Routes without a validator authorize in their own dependencies (this plugin's
            # permission API, among others). Bridge the caller's AuthContext for them as for the
            # validators, so a resource without a grant of its own falls back to the caller's
            # permission on the request's workspace rather than the global default. Flask reads
            # the same context from its environ, so bridging it for the mount changes nothing.
            auth_context = request.scope.get(AUTH_CONTEXT_KEY)
            auth_context_token = set_auth_context(auth_context) if isinstance(auth_context, AuthContext) else None
            try:
                return await call_next(request)
            finally:
                if auth_context_token is not None:
                    clear_auth_context(auth_context_token)

        # Check authentication context (already set by AuthMiddleware)
        if not username:
            return _authentication_required()

        # Admins have full access — but their credentials must not reach a provider either.
        is_admin = getattr(request.state, "is_admin", False)
        if is_admin:
            if path.startswith(_GATEWAY_PREFIX):
                _strip_client_credentials(request, path)
            response = await call_next(request)
            if _is_mcp_server_path(path):
                # Admins are never filtered or granted anything, but a server they delete takes its grants with it.
                return await finalize_mcp_response(path, username, request, response, request.scope.get(AUTH_CONTEXT_KEY), is_admin=True)
            return response

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

        if path.startswith(_GATEWAY_PREFIX):
            _strip_client_credentials(request, path)
        response = await call_next(request)
        if _is_job_search(path, request):
            return await _filtered_job_search_response(username, response)
        if _is_gateway_models_list(path, request):
            return await _filtered_gateway_models_response(username, response, auth_context)
        if _is_mcp_server_path(path):
            return await finalize_mcp_response(path, username, request, response, auth_context)
        return response
