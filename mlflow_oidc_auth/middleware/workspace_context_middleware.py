"""
Workspace Context Middleware for FastAPI.

This middleware sets the MLflow workspace context (via ContextVar) for each request,
ensuring that all downstream tracking-store operations (search_experiments,
list_gateway_endpoints, etc.) execute within the correct workspace scope.

Without this middleware, MLflow 3.10's workspace-aware tracking store raises
"Active workspace is required" errors on any store operation when workspaces
are enabled.

The implementation mirrors MLflow's own ``workspace_context_middleware`` in
``mlflow.server.fastapi_app``, adapted for the OIDC auth plugin's middleware
stack.
"""

import json

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


class WorkspaceContextMiddleware(BaseHTTPMiddleware):
    """
    Sets the MLflow workspace ContextVar for the lifetime of each request.

    When ``MLFLOW_ENABLE_WORKSPACES`` is enabled this middleware:
    1. Reads the ``X-MLFLOW-WORKSPACE`` header from the request.
    2. Resolves the active workspace via MLflow's ``resolve_workspace_for_request_if_enabled``.
    3. Calls ``set_server_request_workspace()`` so that all downstream
       ``_get_tracking_store()`` calls operate in the correct workspace.
    4. Clears the ContextVar in a ``finally`` block after the response is sent.

    When workspaces are disabled this middleware is a transparent pass-through.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        if not config.MLFLOW_ENABLE_WORKSPACES:
            return await call_next(request)

        from mlflow.exceptions import MlflowException
        from mlflow.utils.workspace_context import (
            clear_server_request_workspace,
            set_server_request_workspace,
        )
        from mlflow.server.workspace_helpers import (
            WORKSPACE_HEADER_NAME,
            resolve_workspace_for_request_if_enabled,
        )

        try:
            workspace = resolve_workspace_for_request_if_enabled(
                request.url.path,
                request.headers.get(WORKSPACE_HEADER_NAME),
            )
        except MlflowException as e:
            logger.warning(f"Workspace resolution failed for {request.url.path}: {e}")
            return JSONResponse(
                status_code=e.get_http_status_code(),
                content=json.loads(e.serialize_as_json()),
            )

        set_server_request_workspace(workspace.name if workspace else None)
        try:
            response = await call_next(request)
        finally:
            clear_server_request_workspace()

        return response
