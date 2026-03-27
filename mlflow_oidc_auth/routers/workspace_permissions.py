"""Workspace permission management routes.

CRUD endpoints for workspace-user and workspace-group permissions.
Per D-01: mounted at /api/3.0/mlflow/permissions/workspaces.
Per D-03: CUD endpoints require admin or workspace MANAGE; list endpoints require workspace READ.
Per D-04: MANAGE users can grant up to and including MANAGE.
Per D-13/D-14: User permission CUD invalidates workspace cache in router layer.
"""

from typing import List

from fastapi import APIRouter, Depends, Path

from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.dependencies import (
    check_workspace_manage_permission,
    check_workspace_read_permission,
)
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models.workspace import (
    WorkspaceGroupPermissionRequest,
    WorkspaceGroupPermissionResponse,
    WorkspaceUserPermissionRequest,
    WorkspaceUserPermissionResponse,
)
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils.workspace_cache import invalidate_workspace_permission

from ._prefix import WORKSPACE_PERMISSIONS_ROUTER_PREFIX

logger = get_logger()

workspace_permissions_router = APIRouter(
    prefix=WORKSPACE_PERMISSIONS_ROUTER_PREFIX,
    tags=["workspace permissions"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)

# Endpoint path constants
WORKSPACE_USERS = "/{workspace}/users"
WORKSPACE_GROUPS = "/{workspace}/groups"
WORKSPACE_USER = "/{workspace}/users/{username}"
WORKSPACE_GROUP = "/{workspace}/groups/{group_name}"


@workspace_permissions_router.get(
    WORKSPACE_USERS,
    response_model=List[WorkspaceUserPermissionResponse],
    summary="List users with permissions for a workspace",
)
async def list_workspace_users(
    workspace: str = Path(..., description="The workspace name"),
    _: str = Depends(check_workspace_read_permission),
) -> List[WorkspaceUserPermissionResponse]:
    """List all users with permissions in the specified workspace."""
    perms = store.list_workspace_permissions(workspace)
    return [
        WorkspaceUserPermissionResponse(
            workspace=p.workspace,
            username=p.username or str(p.user_id),
            permission=p.permission,
        )
        for p in perms
    ]


@workspace_permissions_router.get(
    WORKSPACE_GROUPS,
    response_model=List[WorkspaceGroupPermissionResponse],
    summary="List groups with permissions for a workspace",
)
async def list_workspace_groups(
    workspace: str = Path(..., description="The workspace name"),
    _: str = Depends(check_workspace_read_permission),
) -> List[WorkspaceGroupPermissionResponse]:
    """List all groups with permissions in the specified workspace."""
    perms = store.list_workspace_group_permissions(workspace)
    return [
        WorkspaceGroupPermissionResponse(
            workspace=p.workspace,
            group_name=p.group_name or str(p.group_id),
            permission=p.permission,
        )
        for p in perms
    ]


@workspace_permissions_router.post(
    WORKSPACE_USERS,
    response_model=WorkspaceUserPermissionResponse,
    status_code=201,
    summary="Create user permission for a workspace",
)
async def create_workspace_user_permission(
    body: WorkspaceUserPermissionRequest,
    workspace: str = Path(..., description="The workspace name"),
    current_username: str = Depends(check_workspace_manage_permission),
) -> WorkspaceUserPermissionResponse:
    """Grant a user permission on a workspace. Per D-04, MANAGE users can grant up to MANAGE."""
    _validate_permission(body.permission)
    perm = store.create_workspace_permission(workspace, body.username, body.permission)
    invalidate_workspace_permission(body.username, workspace)
    emit_audit_event(
        "permission.create",
        current_username,
        resource_type="workspace_permission",
        resource_id=workspace,
        detail={"username": body.username, "permission": body.permission},
    )
    return WorkspaceUserPermissionResponse(
        workspace=perm.workspace,
        username=body.username,
        permission=perm.permission,
    )


@workspace_permissions_router.post(
    WORKSPACE_GROUPS,
    response_model=WorkspaceGroupPermissionResponse,
    status_code=201,
    summary="Create group permission for a workspace",
)
async def create_workspace_group_permission(
    body: WorkspaceGroupPermissionRequest,
    workspace: str = Path(..., description="The workspace name"),
    current_username: str = Depends(check_workspace_manage_permission),
) -> WorkspaceGroupPermissionResponse:
    """Grant a group permission on a workspace."""
    _validate_permission(body.permission)
    perm = store.create_workspace_group_permission(workspace, body.group_name, body.permission)
    # Group changes rely on TTL-based cache expiry per D-15
    emit_audit_event(
        "permission.create",
        current_username,
        resource_type="group_workspace_permission",
        resource_id=workspace,
        detail={"group_name": body.group_name, "permission": body.permission},
    )
    return WorkspaceGroupPermissionResponse(
        workspace=perm.workspace,
        group_name=body.group_name,
        permission=perm.permission,
    )


@workspace_permissions_router.patch(
    WORKSPACE_USER,
    response_model=WorkspaceUserPermissionResponse,
    summary="Update user permission for a workspace",
)
async def update_workspace_user_permission(
    body: WorkspaceUserPermissionRequest,
    workspace: str = Path(..., description="The workspace name"),
    username: str = Path(..., description="The username"),
    current_username: str = Depends(check_workspace_manage_permission),
) -> WorkspaceUserPermissionResponse:
    """Update a user's permission on a workspace."""
    _validate_permission(body.permission)
    perm = store.update_workspace_permission(workspace, username, body.permission)
    invalidate_workspace_permission(username, workspace)
    emit_audit_event(
        "permission.update",
        current_username,
        resource_type="workspace_permission",
        resource_id=workspace,
        detail={"username": username, "permission": body.permission},
    )
    return WorkspaceUserPermissionResponse(
        workspace=perm.workspace,
        username=username,
        permission=perm.permission,
    )


@workspace_permissions_router.patch(
    WORKSPACE_GROUP,
    response_model=WorkspaceGroupPermissionResponse,
    summary="Update group permission for a workspace",
)
async def update_workspace_group_permission(
    body: WorkspaceGroupPermissionRequest,
    workspace: str = Path(..., description="The workspace name"),
    group_name: str = Path(..., description="The group name"),
    current_username: str = Depends(check_workspace_manage_permission),
) -> WorkspaceGroupPermissionResponse:
    """Update a group's permission on a workspace."""
    _validate_permission(body.permission)
    perm = store.update_workspace_group_permission(workspace, group_name, body.permission)
    emit_audit_event(
        "permission.update",
        current_username,
        resource_type="group_workspace_permission",
        resource_id=workspace,
        detail={"group_name": group_name, "permission": body.permission},
    )
    return WorkspaceGroupPermissionResponse(
        workspace=perm.workspace,
        group_name=group_name,
        permission=perm.permission,
    )


@workspace_permissions_router.delete(
    WORKSPACE_USER,
    status_code=204,
    summary="Delete user permission for a workspace",
)
async def delete_workspace_user_permission(
    workspace: str = Path(..., description="The workspace name"),
    username: str = Path(..., description="The username"),
    current_username: str = Depends(check_workspace_manage_permission),
) -> None:
    """Remove a user's permission from a workspace."""
    store.delete_workspace_permission(workspace, username)
    invalidate_workspace_permission(username, workspace)
    emit_audit_event(
        "permission.delete",
        current_username,
        resource_type="workspace_permission",
        resource_id=workspace,
        detail={"username": username},
    )


@workspace_permissions_router.delete(
    WORKSPACE_GROUP,
    status_code=204,
    summary="Delete group permission for a workspace",
)
async def delete_workspace_group_permission(
    workspace: str = Path(..., description="The workspace name"),
    group_name: str = Path(..., description="The group name"),
    current_username: str = Depends(check_workspace_manage_permission),
) -> None:
    """Remove a group's permission from a workspace."""
    store.delete_workspace_group_permission(workspace, group_name)
    emit_audit_event(
        "permission.delete",
        current_username,
        resource_type="group_workspace_permission",
        resource_id=workspace,
        detail={"group_name": group_name},
    )
