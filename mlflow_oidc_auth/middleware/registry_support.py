"""Helpers shared by the authorization of the registries MLflow serves from FastAPI.

The MCP server registry (``mcp_server_registry``) and the skill registry (``skill_registry``) each
authorize their own routes; what they have in common lives here so neither depends on the other:
bridging the caller's ``AuthContext``, the workspace rule for creating a resource, and rewriting a
response body after MLflow's handler has run.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from starlette.responses import Response

from mlflow_oidc_auth.bridge.user import clear_auth_context, set_auth_context
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities.auth_context import AuthContext


@contextmanager
def bridged_auth_context(auth_context: Any) -> Iterator[None]:
    """Bridge the caller's ``AuthContext`` while permissions are resolved or grants written.

    The grant workspace and the workspace fallback both come from it.
    """
    token = set_auth_context(auth_context) if isinstance(auth_context, AuthContext) else None
    try:
        yield
    finally:
        if token is not None:
            clear_auth_context(token)


def can_create_in_request_workspace(username: str) -> bool:
    """Whether ``username`` may create a registry resource in the workspace MLflow serves the request from.

    Only meaningful with workspaces enabled. ``OIDC_WORKSPACE_CREATION_PERMISSION`` (``MANAGE`` by
    default, or ``EDIT``) on that workspace — the one the request names, else MLflow's default —
    subject to ``OIDC_WORKSPACE_REQUIRE_CREATION_CONTEXT`` and ``OIDC_WORKSPACE_DENY_DEFAULT_CREATION``:
    the same threshold as creating experiments, models and gateway resources. Shared by the
    registries MLflow serves from FastAPI (MCP servers and skills).

    Parameters:
        username: The caller.

    Returns:
        True when the caller may create there.
    """
    from mlflow.utils.workspace_utils import DEFAULT_WORKSPACE_NAME

    from mlflow_oidc_auth.bridge.user import get_request_workspace
    from mlflow_oidc_auth.utils.grant_workspace import current_grant_workspace
    from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached

    workspace = get_request_workspace()
    # MLflow's resolved workspace for a request that names none: its default, which a workspace
    # provider may call something other than ``default``.
    effective = workspace or current_grant_workspace()
    if workspace is None and config.OIDC_WORKSPACE_REQUIRE_CREATION_CONTEXT:
        return False
    if effective == DEFAULT_WORKSPACE_NAME and config.OIDC_WORKSPACE_DENY_DEFAULT_CREATION:
        return False
    from mlflow_oidc_auth.permissions import meets_workspace_creation_threshold

    permission = get_workspace_permission_cached(username, effective)
    return meets_workspace_creation_threshold(permission, config.OIDC_WORKSPACE_CREATION_PERMISSION)


async def buffer_body(response: Response) -> bytes:
    """Read a streamed response body to the end."""
    return b"".join([chunk async for chunk in response.body_iterator])


def rebuilt_response(response: Response, body: bytes) -> Response:
    """``body`` as a response with ``response``'s status, headers (repeated ones included) and background."""
    rebuilt = Response(content=body, status_code=response.status_code, media_type="application/json", background=response.background)
    rebuilt.raw_headers.extend((k, v) for k, v in response.raw_headers if k.lower() not in (b"content-length", b"content-type"))
    return rebuilt
