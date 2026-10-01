"""Permission API for MLflow's MCP server registry.

MLflow keeps MCP servers unique per ``(workspace, name)``, so every grant here is read and written
in the request's workspace (``X-MLFLOW-WORKSPACE``, else the default workspace) — the same
workspace MLflow serves the registry from.

Three routers, all gated with dependencies from ``dependencies.py``:

* ``/api/2.0/mlflow/permissions/mcp-servers`` — the servers the caller may manage, and the users
  and groups holding a grant on one server;
* ``/api/2.0/mlflow/permissions/users/{username}/mcp-servers[/{name}]`` — a user's grants;
* ``/api/2.0/mlflow/permissions/groups/{group_name}/mcp-servers[/{name}]`` — a group's grants.

Changing a grant needs MANAGE on the server (or admin), as for registered models and experiments:
the creator of a server holds MANAGE and may share it.
"""

from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from fastapi.responses import JSONResponse
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST, ErrorCode

from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.dependencies import check_mcp_server_manage_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import GatewayPermission, NamedPermissionSummary, StatusMessageResponse, UserPermission
from mlflow_oidc_auth.models.group import GroupNamedPermissionItem, GroupPermissionEntry
from mlflow_oidc_auth.permissions import NO_PERMISSIONS
from mlflow_oidc_auth.routers._prefix import GROUP_PERMISSIONS_ROUTER_PREFIX, MCP_SERVER_PERMISSIONS_ROUTER_PREFIX, USER_PERMISSIONS_ROUTER_PREFIX
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import get_is_admin, get_username
from mlflow_oidc_auth.utils.data_fetching import fetch_all_mcp_servers
from mlflow_oidc_auth.utils.pagination import NO_PAGE, PageQuery, paginate_with_headers
from mlflow_oidc_auth.utils.permissions import can_manage_mcp_server, effective_mcp_server_permission

logger = get_logger()

_RESPONSES = {
    403: {"description": "Forbidden - Insufficient permissions"},
    404: {"description": "Resource not found"},
}

mcp_server_permissions_router = APIRouter(prefix=MCP_SERVER_PERMISSIONS_ROUTER_PREFIX, tags=["mcp server permissions"], responses=_RESPONSES)
user_mcp_server_permissions_router = APIRouter(prefix=USER_PERMISSIONS_ROUTER_PREFIX, tags=["user mcp server permissions"], responses=_RESPONSES)
group_mcp_server_permissions_router = APIRouter(prefix=GROUP_PERMISSIONS_ROUTER_PREFIX, tags=["group mcp server permissions"], responses=_RESPONSES)

LIST_MCP_SERVERS = ""
MCP_SERVER_USER_PERMISSIONS = "/{name:path}/users"
MCP_SERVER_GROUP_PERMISSIONS = "/{name:path}/groups"
USER_MCP_SERVER_PERMISSIONS = "/{username}/mcp-servers"
USER_MCP_SERVER_PERMISSION_DETAIL = "/{username}/mcp-servers/{name:path}"
GROUP_MCP_SERVER_PERMISSIONS = "/{group_name:path}/mcp-servers"
GROUP_MCP_SERVER_PERMISSION_DETAIL = "/{group_name:path}/mcp-servers/{name:path}"


def _http_error(e: Exception, action: str) -> HTTPException:
    """Map a store error to an HTTP error without echoing internals."""
    if isinstance(e, MlflowException):
        if e.error_code == ErrorCode.Name(RESOURCE_ALREADY_EXISTS):
            return HTTPException(status_code=409, detail="Permission already exists")
        if e.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
            return HTTPException(status_code=404, detail="Not found")
        if e.error_code == ErrorCode.Name(INVALID_PARAMETER_VALUE):
            return HTTPException(status_code=400, detail="Invalid permission")
    logger.error("MCP server permission API: failed to %s: %s", action, type(e).__name__)
    return HTTPException(status_code=500, detail=f"Failed to {action}")


# ----------------------------------------------------------------------------------------
# Per server
# ----------------------------------------------------------------------------------------


@mcp_server_permissions_router.get(
    LIST_MCP_SERVERS,
    summary="List MCP servers the caller may manage",
    description="MCP servers of the request's workspace: all of them for an admin, otherwise those the caller can MANAGE.",
)
async def list_mcp_servers(username: str = Depends(get_username), is_admin: bool = Depends(get_is_admin), page: PageQuery = NO_PAGE) -> JSONResponse:
    try:
        servers = fetch_all_mcp_servers()
        if not is_admin:
            servers = [s for s in servers if can_manage_mcp_server(s["name"], username)]
    except Exception as e:
        raise _http_error(e, "retrieve MCP servers")
    # Paginate strictly after the permission filter: the total never counts a hidden server.
    servers, headers = paginate_with_headers(servers, key=lambda s: s.get("name", ""), params=page)
    return JSONResponse(headers=headers, content=servers)


@mcp_server_permissions_router.get(
    MCP_SERVER_USER_PERMISSIONS,
    response_model=List[UserPermission],
    summary="List users with a grant on an MCP server",
)
async def get_mcp_server_users(
    name: str = Path(..., description="MCP server name"),
    _: str = Depends(check_mcp_server_manage_permission),
) -> List[UserPermission]:
    try:
        rows = store.list_mcp_server_users(name)
    except Exception as e:
        raise _http_error(e, "retrieve MCP server user permissions")
    return [UserPermission(name=u, permission=p, kind="service-account" if is_sa else "user") for u, p, is_sa in rows]


@mcp_server_permissions_router.get(
    MCP_SERVER_GROUP_PERMISSIONS,
    response_model=List[GroupPermissionEntry],
    summary="List groups with a grant on an MCP server",
)
async def get_mcp_server_groups(
    name: str = Path(..., description="MCP server name"),
    _: str = Depends(check_mcp_server_manage_permission),
) -> List[GroupPermissionEntry]:
    try:
        rows = store.list_mcp_server_groups(name)
    except Exception as e:
        raise _http_error(e, "retrieve MCP server group permissions")
    return [GroupPermissionEntry(name=g, permission=p) for g, p in rows]


# ----------------------------------------------------------------------------------------
# Per user
# ----------------------------------------------------------------------------------------


@user_mcp_server_permissions_router.get(
    USER_MCP_SERVER_PERMISSIONS,
    response_model=List[NamedPermissionSummary],
    summary="List a user's MCP server permissions",
    description="Effective permissions of a user on the MCP servers of the request's workspace.",
)
async def get_user_mcp_server_permissions(
    username: str = Path(..., description="The user"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[NamedPermissionSummary]:
    """Admins see every server; the user themselves those they can reach; others only servers they MANAGE."""
    try:
        results: List[NamedPermissionSummary] = []
        for server in fetch_all_mcp_servers():
            name = server.get("name")
            if not name:
                continue
            if not is_admin and current_username != username and not can_manage_mcp_server(name, current_username):
                continue
            result = effective_mcp_server_permission(name, username)
            if not is_admin and current_username == username and result.permission.name == NO_PERMISSIONS.name:
                continue
            results.append(NamedPermissionSummary(name=name, permission=result.permission.name, kind=result.kind))
        return results
    except Exception as e:
        raise _http_error(e, "retrieve MCP server permissions")


@user_mcp_server_permissions_router.post(
    USER_MCP_SERVER_PERMISSION_DETAIL,
    status_code=201,
    response_model=NamedPermissionSummary,
    summary="Grant a user a permission on an MCP server",
)
async def create_user_mcp_server_permission(
    username: str = Path(..., description="The user to grant"),
    name: str = Path(..., description="MCP server name"),
    permission_data: GatewayPermission = Body(...),
    actor: str = Depends(check_mcp_server_manage_permission),
) -> NamedPermissionSummary:
    try:
        perm = store.create_mcp_server_permission(name, username, permission_data.permission)
    except Exception as e:
        raise _http_error(e, "create MCP server permission")
    emit_audit_event(
        "permission.create",
        actor=actor,
        resource_type="mcp_server_permission",
        resource_id=name,
        detail={"username": username, "permission": permission_data.permission},
    )
    return NamedPermissionSummary(name=perm.name, permission=perm.permission, kind="user")


@user_mcp_server_permissions_router.get(
    USER_MCP_SERVER_PERMISSION_DETAIL,
    response_model=NamedPermissionSummary,
    summary="Get a user's grant on an MCP server",
)
async def get_user_mcp_server_permission(
    username: str = Path(..., description="The user"),
    name: str = Path(..., description="MCP server name"),
    _: str = Depends(check_mcp_server_manage_permission),
) -> NamedPermissionSummary:
    try:
        perm = store.get_mcp_server_permission(name, username)
    except Exception as e:
        raise _http_error(e, "retrieve MCP server permission")
    return NamedPermissionSummary(name=perm.name, permission=perm.permission, kind="user")


@user_mcp_server_permissions_router.patch(
    USER_MCP_SERVER_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Change a user's grant on an MCP server",
)
async def update_user_mcp_server_permission(
    username: str = Path(..., description="The user"),
    name: str = Path(..., description="MCP server name"),
    permission_data: GatewayPermission = Body(...),
    actor: str = Depends(check_mcp_server_manage_permission),
) -> StatusMessageResponse:
    try:
        store.update_mcp_server_permission(name, username, permission_data.permission)
    except Exception as e:
        raise _http_error(e, "update MCP server permission")
    emit_audit_event(
        "permission.update",
        actor=actor,
        resource_type="mcp_server_permission",
        resource_id=name,
        detail={"username": username, "permission": permission_data.permission},
    )
    return StatusMessageResponse(message=f"MCP server permission updated for {username} on {name}")


@user_mcp_server_permissions_router.delete(
    USER_MCP_SERVER_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Revoke a user's grant on an MCP server",
)
async def delete_user_mcp_server_permission(
    username: str = Path(..., description="The user"),
    name: str = Path(..., description="MCP server name"),
    actor: str = Depends(check_mcp_server_manage_permission),
) -> StatusMessageResponse:
    try:
        store.delete_mcp_server_permission(name, username)
    except Exception as e:
        raise _http_error(e, "delete MCP server permission")
    emit_audit_event("permission.delete", actor=actor, resource_type="mcp_server_permission", resource_id=name, detail={"username": username})
    return StatusMessageResponse(message=f"MCP server permission deleted for {username} on {name}")


# ----------------------------------------------------------------------------------------
# Per group
# ----------------------------------------------------------------------------------------


@group_mcp_server_permissions_router.get(
    GROUP_MCP_SERVER_PERMISSIONS,
    response_model=List[GroupNamedPermissionItem],
    summary="List a group's MCP server grants",
    description="The group's grants in the request's workspace: all of them for an admin, otherwise those on servers the caller can MANAGE.",
)
async def get_group_mcp_server_permissions(
    group_name: str = Path(..., description="The group"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[GroupNamedPermissionItem]:
    try:
        perms = store.list_group_mcp_server_permissions(group_name)
        return [GroupNamedPermissionItem(name=p.name, permission=p.permission) for p in perms if is_admin or can_manage_mcp_server(p.name, current_username)]
    except Exception as e:
        raise _http_error(e, "retrieve group MCP server permissions")


@group_mcp_server_permissions_router.post(
    GROUP_MCP_SERVER_PERMISSION_DETAIL,
    status_code=201,
    response_model=GroupNamedPermissionItem,
    summary="Grant a group a permission on an MCP server",
)
async def create_group_mcp_server_permission(
    group_name: str = Path(..., description="The group to grant"),
    name: str = Path(..., description="MCP server name"),
    permission_data: GatewayPermission = Body(...),
    actor: str = Depends(check_mcp_server_manage_permission),
) -> GroupNamedPermissionItem:
    try:
        perm = store.create_group_mcp_server_permission(group_name, name, permission_data.permission)
    except Exception as e:
        raise _http_error(e, "create group MCP server permission")
    emit_audit_event(
        "permission.create",
        actor=actor,
        resource_type="group_mcp_server_permission",
        resource_id=name,
        detail={"group_name": group_name, "permission": permission_data.permission},
    )
    return GroupNamedPermissionItem(name=perm.name, permission=perm.permission)


@group_mcp_server_permissions_router.get(
    GROUP_MCP_SERVER_PERMISSION_DETAIL,
    response_model=GroupNamedPermissionItem,
    summary="Get a group's grant on an MCP server",
)
async def get_group_mcp_server_permission(
    group_name: str = Path(..., description="The group"),
    name: str = Path(..., description="MCP server name"),
    _: str = Depends(check_mcp_server_manage_permission),
) -> GroupNamedPermissionItem:
    try:
        perm = store.get_group_mcp_server_permission(group_name, name)
    except Exception as e:
        raise _http_error(e, "retrieve group MCP server permission")
    return GroupNamedPermissionItem(name=perm.name, permission=perm.permission)


@group_mcp_server_permissions_router.patch(
    GROUP_MCP_SERVER_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Change a group's grant on an MCP server",
)
async def update_group_mcp_server_permission(
    group_name: str = Path(..., description="The group"),
    name: str = Path(..., description="MCP server name"),
    permission_data: GatewayPermission = Body(...),
    actor: str = Depends(check_mcp_server_manage_permission),
) -> StatusMessageResponse:
    try:
        store.update_group_mcp_server_permission(group_name, name, permission_data.permission)
    except Exception as e:
        raise _http_error(e, "update group MCP server permission")
    emit_audit_event(
        "permission.update",
        actor=actor,
        resource_type="group_mcp_server_permission",
        resource_id=name,
        detail={"group_name": group_name, "permission": permission_data.permission},
    )
    return StatusMessageResponse(message=f"MCP server permission updated for group {group_name} on {name}")


@group_mcp_server_permissions_router.delete(
    GROUP_MCP_SERVER_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Revoke a group's grant on an MCP server",
)
async def delete_group_mcp_server_permission(
    group_name: str = Path(..., description="The group"),
    name: str = Path(..., description="MCP server name"),
    actor: str = Depends(check_mcp_server_manage_permission),
) -> StatusMessageResponse:
    try:
        store.delete_group_mcp_server_permission(group_name, name)
    except Exception as e:
        raise _http_error(e, "delete group MCP server permission")
    emit_audit_event("permission.delete", actor=actor, resource_type="group_mcp_server_permission", resource_id=name, detail={"group_name": group_name})
    return StatusMessageResponse(message=f"MCP server permission deleted for group {group_name} on {name}")
