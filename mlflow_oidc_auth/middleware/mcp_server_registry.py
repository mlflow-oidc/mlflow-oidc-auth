"""Authorization for MLflow's MCP server registry (``mlflow.server.mcp_server_api``, MLflow 3.15+).

MLflow serves the registry from FastAPI under ``/api/3.0/mlflow/mcp-servers`` and
``/ajax-api/3.0/mlflow/mcp-servers`` (each behind ``--static-prefix`` when one is set), so it never
reaches the Flask hooks: ``fastapi_permission_middleware`` runs the validator built here before
MLflow's handler and :func:`finalize_mcp_response` after it.

MLflow keeps MCP servers unique per ``(workspace, name)``; a name is ``<namespace>/<slug>``
(exactly one ``/``). Permissions mirror MLflow's own auth plugin (``mlflow/server/auth``):

==========================================  ===================================================
Route                                       Requires
==========================================  ===================================================
``POST   /mcp-servers``                     MANAGE on the workspace (see :func:`can_create_mcp_server`);
                                            the creator is granted ``MANAGE`` once MLflow
                                            returns success
``GET    /mcp-servers``                     authentication; the list is narrowed to READ
``GET    /mcp-servers/endpoints``           authentication; narrowed to servers with READ
``GET    /mcp-servers/{name}[/...]``        ``READ`` on the server
``POST|PATCH /mcp-servers/{name}[/...]``    ``EDIT`` on the server (tags, aliases, versions,
                                            access endpoints, the server itself)
``POST   /mcp-servers/{name}/versions``     ``EDIT`` on the server; on a server that does not
                                            exist yet (MLflow creates it) create rights, and the
                                            creator is granted ``MANAGE``
``DELETE /mcp-servers/{name}[/...]``        ``MANAGE`` on the server; deleting the server also
                                            deletes its grants in the request's workspace
==========================================  ===================================================

The permission on a server is the caller's user grant, then group grants, then their permission
on the request's workspace (see ``effective_mcp_server_permission``). A grant on a server applies
whether or not the grantee is a member of its workspace — sharing one server with a non-member is
what a resource grant is for, as for every other resource type in this plugin. Admins never reach
any of this: the middleware lets them through first.

Routes are resolved the way Starlette's router resolves MLflow's (same templates, same order, the
first one whose path and method match), so the server name judged here is the name MLflow's
handler will use. A request that resolves to no registry route, or to a name MLflow could never
have stored, is denied.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, Optional

from fastapi import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import compile_path

from mlflow_oidc_auth.bridge.user import clear_auth_context, set_auth_context
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

#: The bare mount points; MLflow also mounts both behind ``--static-prefix`` (see :func:`mcp_route_prefixes`).
MCP_SERVER_PREFIXES = ("/api/3.0/mlflow/mcp-servers", "/ajax-api/3.0/mlflow/mcp-servers")

# Actions a registry route maps to.
CREATE = "create"
CREATE_VERSION = "create_version"
SEARCH = "search"
SEARCH_ENDPOINTS = "search_endpoints"
READ = "read"
READ_SERVER = "read_server"
UPDATE = "update"
DELETE = "delete"
DELETE_SERVER = "delete_server"

# MLflow's ``mcp_server_router`` route table, in registration order (Starlette serves the first
# route whose path and method match). Templates are relative to the mount prefix.
_ROUTE_TABLE = (
    ("POST", "", CREATE),
    ("GET", "", SEARCH),
    ("GET", "/endpoints", SEARCH_ENDPOINTS),
    ("POST", "/{name:path}/versions/{version:path}/tags", UPDATE),
    ("DELETE", "/{name:path}/versions/{version:path}/tags/{key:path}", DELETE),
    ("GET", "/{name:path}/versions/{version:path}", READ),
    ("PATCH", "/{name:path}/versions/{version:path}", UPDATE),
    ("DELETE", "/{name:path}/versions/{version:path}", DELETE),
    ("POST", "/{name:path}/versions", CREATE_VERSION),
    ("GET", "/{name:path}/versions", READ),
    ("POST", "/{name:path}/endpoints", UPDATE),
    ("GET", "/{name:path}/endpoints/{endpoint_id}", READ),
    ("PATCH", "/{name:path}/endpoints/{endpoint_id}", UPDATE),
    ("DELETE", "/{name:path}/endpoints/{endpoint_id}", DELETE),
    ("GET", "/{name:path}/endpoints", READ),
    ("POST", "/{name:path}/tags", UPDATE),
    ("DELETE", "/{name:path}/tags/{key:path}", DELETE),
    ("POST", "/{name:path}/aliases", UPDATE),
    ("GET", "/{name:path}/aliases/{alias:path}", READ),
    ("DELETE", "/{name:path}/aliases/{alias:path}", DELETE),
    ("GET", "/{name:path}", READ_SERVER),
    ("PATCH", "/{name:path}", UPDATE),
    ("DELETE", "/{name:path}", DELETE_SERVER),
)

_COMPILED_ROUTES = tuple((method, compile_path(template)[0], action) for method, template, action in _ROUTE_TABLE)

# A name MLflow can have stored: ``validate_mcp_server_name`` requires exactly ``<namespace>/<slug>``.
_STORABLE_NAME = re.compile(r"[^/]+/[^/]+")

# Upstream's ``allowed_actions`` stamp, which MLflow's UI reads to enable its edit and delete controls.
_ALLOWED_ACTIONS = (("can_use", "USE"), ("can_update", "UPDATE"), ("can_delete", "DELETE"), ("can_manage", "MANAGE"))


@dataclass(frozen=True)
class MCPRoute:
    """A resolved registry request: what it does and, for per-server routes, which server."""

    action: str
    name: Optional[str] = None


def mcp_route_prefixes() -> tuple[str, ...]:
    """Every prefix the registry may be served under: the bare paths and the static-prefixed ones.

    MLflow mounts the registry at ``get_mcp_server_api_route_prefixes()``, which puts its static
    prefix in front of both paths. On an MLflow without the registry the static prefix is applied
    here the same way, so the match never depends on the installed version.
    """
    prefixes = list(MCP_SERVER_PREFIXES)
    try:
        from mlflow.server.mcp_server_api import get_mcp_server_api_route_prefixes

        prefixes.extend(get_mcp_server_api_route_prefixes())
    except ImportError:
        try:
            from mlflow.server.handlers import _add_static_prefix

            prefixes.extend(_add_static_prefix(p) for p in MCP_SERVER_PREFIXES)
        except Exception:
            logger.debug("Could not apply MLflow's static prefix to the MCP registry paths")
    # Longest first, so a static-prefixed mount is never mistaken for a bare one.
    return tuple(sorted(set(prefixes), key=len, reverse=True))


def is_mcp_server_path(path: str) -> bool:
    """Whether ``path`` is on the MCP server registry, with or without MLflow's static prefix.

    Deliberately wide: anything starting with a registry prefix is routed to the registry validator,
    which denies whatever it cannot resolve to one of MLflow's routes.
    """
    return path.startswith(mcp_route_prefixes())


def resolve_mcp_route(path: str, method: str) -> Optional[MCPRoute]:
    """The registry route MLflow will serve ``method path`` with, or None if it serves none.

    ``HEAD`` is judged as ``GET``. A per-server route whose name MLflow could never have stored
    (not exactly ``<namespace>/<slug>``) resolves to None as well.
    """
    method = "GET" if method.upper() == "HEAD" else method.upper()
    for prefix in mcp_route_prefixes():
        if path == prefix or path.startswith(prefix + "/"):
            suffix = path[len(prefix) :]
            break
    else:
        return None
    for route_method, regex, action in _COMPILED_ROUTES:
        if route_method != method:
            continue
        match = regex.match(suffix)
        if match is None:
            continue
        name = match.groupdict().get("name")
        if name is None:
            return MCPRoute(action)
        if not _STORABLE_NAME.fullmatch(name):
            return None
        return MCPRoute(action, name)
    return None


@contextmanager
def _bridged(auth_context: Any) -> Iterator[None]:
    """Bridge the caller's ``AuthContext`` while permissions are resolved or grants written.

    The grant workspace and the workspace fallback both come from it.
    """
    token = set_auth_context(auth_context) if isinstance(auth_context, AuthContext) else None
    try:
        yield
    finally:
        if token is not None:
            clear_auth_context(token)


def can_create_mcp_server(username: str) -> bool:
    """Whether ``username`` may create an MCP server in the request's workspace.

    With workspaces enabled: ``MANAGE`` on the workspace MLflow serves the request from — the one it
    names, else the default workspace — subject to ``OIDC_WORKSPACE_REQUIRE_CREATION_CONTEXT`` and
    ``OIDC_WORKSPACE_DENY_DEFAULT_CREATION``, the same threshold as creating experiments, models and
    gateway resources. (MLflow's own plugin asks for a workspace grant that carries ``can_use``.)

    With workspaces disabled: administrators only, as before per-server permissions.
    """
    from mlflow.utils.workspace_utils import DEFAULT_WORKSPACE_NAME

    if not config.MLFLOW_ENABLE_WORKSPACES:
        # One registry and no workspace to delegate through: registering a server stays an
        # administrator's job, as before per-server permissions (admins never reach this check).
        return False

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
    permission = get_workspace_permission_cached(username, effective)
    return permission is not None and permission.can_manage


def can_search_mcp_servers(username: str) -> bool:
    """Whether ``username`` may search the request's workspace's MCP registry: ``READ`` on it.

    With workspaces disabled there is one registry and no tenant boundary: any authenticated user.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return True
    from mlflow_oidc_auth.bridge.user import get_request_workspace
    from mlflow_oidc_auth.utils.grant_workspace import current_grant_workspace
    from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached

    permission = get_workspace_permission_cached(username, get_request_workspace() or current_grant_workspace())
    return permission is not None and permission.can_read


def _may_read(name: str, username: str) -> bool:
    """Whether ``username`` may read MCP server ``name``.

    With workspaces disabled the registry is readable by every authenticated user, as it was before
    per-server permissions: a server with no grant of its own is readable, and a grant on it — a
    ``NO_PERMISSIONS`` included — decides otherwise. With workspaces enabled ``READ`` on the server
    decides, a workspace permission standing in for a missing grant.
    """
    from mlflow_oidc_auth.utils.permissions import effective_mcp_server_permission

    result = effective_mcp_server_permission(name, username)
    if not config.MLFLOW_ENABLE_WORKSPACES and result.kind not in ("user", "group"):
        return True
    return result.permission.can_read


def _mcp_server_exists(name: str) -> bool:
    """Whether the request's workspace holds an MCP server called ``name``.

    Raises:
        Exception: Any lookup failure other than "does not exist" — the caller denies.
    """
    from mlflow.exceptions import MlflowException
    from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode
    from mlflow.server.handlers import _get_tracking_store

    try:
        _get_tracking_store().get_mcp_server(name)
        return True
    except MlflowException as e:
        if e.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
            return False
        raise


def get_mcp_server_validator(path: str) -> Callable[[str, Request], Awaitable[bool]]:
    """Return the validator for an MCP server registry request (see the module docstring)."""
    from mlflow_oidc_auth.utils.permissions import can_delete_mcp_server, can_update_mcp_server

    async def validator(username: str, request: Request) -> bool:
        route = resolve_mcp_route(path, request.method)
        if route is None:
            return False
        if route.action in (SEARCH, SEARCH_ENDPOINTS):
            # The response is narrowed to readable servers afterwards, but MLflow's page token
            # still tells how many rows matched the caller's filter — an oracle on the hidden
            # ones. So searching a workspace's registry needs READ on that workspace, as before
            # per-server permissions; a server shared with a non-member is reached by name.
            return can_search_mcp_servers(username)
        if route.action == CREATE:
            return can_create_mcp_server(username)
        name = route.name
        if route.action == CREATE_VERSION:
            # MLflow creates the server when it does not exist yet, so that request is a creation.
            if _mcp_server_exists(name):
                request.state.mcp_server_parent_auto_created = False
                return can_update_mcp_server(name, username)
            # MLflow's handler then creates the server first and, should another request have
            # created it in between, asks this recheck instead (``_ensure_version_create_parent_access``).
            # It runs inside the handler, after the bridged context is gone, so it bridges its own.
            auth_context = request.scope.get(AUTH_CONTEXT_KEY)
            request.state.mcp_server_parent_auto_created = True
            request.state.mcp_server_can_update_existing_recheck = _recheck(name, username, auth_context)
            return can_create_mcp_server(username)
        if route.action in (READ, READ_SERVER):
            return _may_read(name, username)
        if route.action == UPDATE:
            return can_update_mcp_server(name, username)
        if route.action in (DELETE, DELETE_SERVER):
            return can_delete_mcp_server(name, username)
        return False

    return validator


def _recheck(name: str, username: str, auth_context: Any) -> Callable[[], bool]:
    def recheck() -> bool:
        from mlflow_oidc_auth.utils.permissions import can_update_mcp_server

        try:
            with _bridged(auth_context):
                return can_update_mcp_server(name, username)
        except Exception as e:
            logger.error("MCP server registry: permission recheck failed: %s", type(e).__name__)
            return False

    return recheck


# ---------------------------------------------------------------------------
# After MLflow's handler
# ---------------------------------------------------------------------------


def _allowed_actions(permission) -> list[str]:
    return [label for attribute, label in _ALLOWED_ACTIONS if getattr(permission, attribute, False)]


def _filter_search_body(username: str, body: bytes, list_key: str, name_key: str, stamp: bool) -> bytes:
    """Keep only the items on servers ``username`` may READ.

    Raises:
        ValueError: The body is not a list response under ``list_key``.
    """
    from mlflow_oidc_auth.utils.permissions import effective_mcp_server_permission, mcp_server_display_permission

    data = json.loads(body)
    items = data.get(list_key) if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("MCP registry response carries no list")
    cache: dict[str, Any] = {}
    visible = []
    for item in items:
        name = item.get(name_key) if isinstance(item, dict) else None
        if not isinstance(name, str) or not name:
            continue
        if name not in cache:
            try:
                cache[name] = effective_mcp_server_permission(name, username).permission if _may_read(name, username) else None
            except Exception as e:
                logger.error("MCP server registry: permission check failed: %s", type(e).__name__)
                cache[name] = None
        permission = cache[name]
        if permission is None:
            continue
        if stamp:
            item["allowed_actions"] = _allowed_actions(mcp_server_display_permission(name, username))
        visible.append(item)
    data[list_key] = visible
    return json.dumps(data).encode()


async def _buffer(response: Response) -> bytes:
    return b"".join([chunk async for chunk in response.body_iterator])


def _rebuilt(response: Response, body: bytes) -> Response:
    """``body`` as a response with ``response``'s status, headers (repeated ones included) and background."""
    rebuilt = Response(content=body, status_code=response.status_code, media_type="application/json", background=response.background)
    rebuilt.raw_headers.extend((k, v) for k, v in response.raw_headers if k.lower() not in (b"content-length", b"content-type"))
    return rebuilt


def _grant_creator_manage(name: str, username: str) -> None:
    """Give ``username`` MANAGE on ``name`` in the request's grant workspace, raising a lower grant."""
    from mlflow.exceptions import MlflowException
    from mlflow.protos.databricks_pb2 import RESOURCE_ALREADY_EXISTS, ErrorCode

    from mlflow_oidc_auth.permissions import MANAGE
    from mlflow_oidc_auth.store import store

    try:
        store.create_mcp_server_permission(name, username, MANAGE.name)
    except MlflowException as e:
        if e.error_code != ErrorCode.Name(RESOURCE_ALREADY_EXISTS):
            raise
        store.update_mcp_server_permission(name, username, MANAGE.name)


def _grant_parent_creator(name: str, username: str, auth_context: Any) -> None:
    """Grant MANAGE on a server MLflow created for this caller's version request. Never raises."""
    try:
        from mlflow.server.handlers import _get_tracking_store

        server = _get_tracking_store().get_mcp_server(name)
        # MLflow records the caller as the creator of a server it creates for a version; a server
        # someone else created first is theirs, not this caller's.
        if getattr(server, "created_by", None) == username:
            with _bridged(auth_context):
                _grant_creator_manage(name, username)
    except Exception as e:
        logger.error("MCP server registry: could not grant the creator MANAGE: %s", type(e).__name__)


def _created_in_grant_workspace(data: dict) -> bool:
    """Whether the server MLflow reports is in the workspace the grant would be written in."""
    from mlflow_oidc_auth.utils.grant_workspace import current_grant_workspace

    workspace = data.get("workspace")
    if workspace is None or not config.MLFLOW_ENABLE_WORKSPACES:
        return True
    return workspace == current_grant_workspace()


async def finalize_mcp_response(path: str, username: str, request: Request, response: Response, auth_context: Any, is_admin: bool = False) -> Response:
    """Post-process a registry response.

    For an admin only the delete cascade runs: an admin sees everything and is never granted
    anything, but the grants on a server an admin deletes must go with it. For everyone else:

    * search responses are narrowed to readable servers (and stamped with ``allowed_actions``); a
      body that cannot be filtered is an error, never the unfiltered list;
    * a single server is stamped with ``allowed_actions``;
    * a successful create (or a version create that created its server) grants the creator
      ``MANAGE`` in the request's workspace — only once MLflow returned success;
    * a successful server delete removes the server's grants in the request's workspace.

    Non-2xx responses are returned unchanged.
    """
    route = resolve_mcp_route(path, request.method)
    if route is not None and route.action == CREATE_VERSION and not is_admin and getattr(request.state, "mcp_server_parent_auto_created", False):
        # MLflow creates the server before the version, so a version that then fails still leaves
        # the server behind: its creator manages it either way, or nobody but an admin could.
        _grant_parent_creator(route.name, username, auth_context)
    if route is None or not 200 <= response.status_code < 300:
        return response
    if is_admin and route.action != DELETE_SERVER:
        return response

    if route.action in (SEARCH, SEARCH_ENDPOINTS):
        body = await _buffer(response)
        try:
            with _bridged(auth_context):
                if route.action == SEARCH:
                    filtered = _filter_search_body(username, body, "mcp_servers", "name", stamp=True)
                else:
                    filtered = _filter_search_body(username, body, "mcp_access_endpoints", "server_name", stamp=False)
        except Exception as e:
            logger.error("Failed to filter MCP server registry response: %s", type(e).__name__)
            return JSONResponse(status_code=500, content={"detail": "Failed to filter response"})
        return _rebuilt(response, filtered)

    if route.action == READ_SERVER:
        body = await _buffer(response)
        try:
            from mlflow_oidc_auth.utils.permissions import mcp_server_display_permission

            data = json.loads(body)
            with _bridged(auth_context):
                data["allowed_actions"] = _allowed_actions(mcp_server_display_permission(route.name, username))
            return _rebuilt(response, json.dumps(data).encode())
        except Exception as e:
            # Already authorized: an unstamped body exposes nothing the caller may not read.
            logger.warning("Could not stamp allowed_actions on an MCP server: %s", type(e).__name__)
            return _rebuilt(response, body)

    if route.action == CREATE:
        body = await _buffer(response)
        try:
            data = json.loads(body)
            name = data.get("name") if isinstance(data, dict) else None
            if not isinstance(name, str) or not _STORABLE_NAME.fullmatch(name):
                raise ValueError("create response names no MCP server")
            with _bridged(auth_context):
                if not _created_in_grant_workspace(data):
                    raise ValueError("MCP server created outside the request's grant workspace")
                _grant_creator_manage(name, username)
        except Exception as e:
            # The server exists; failing the response would make the client retry into a conflict.
            # With no MANAGE grant it is admin-only for changes until an admin grants one.
            logger.error("MCP server registry: could not grant the creator MANAGE: %s", type(e).__name__)
        return _rebuilt(response, body)

    if route.action == DELETE_SERVER:
        try:
            from mlflow_oidc_auth.store import store

            with _bridged(auth_context):
                store.wipe_mcp_server_permissions(route.name)
        except Exception as e:
            logger.warning("Failed to cascade-delete permissions for an MCP server: %s", type(e).__name__)
        return response

    return response
