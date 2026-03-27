"""Workspace regex permission management routes.

CRUD endpoints for user-regex and group-regex workspace permissions.
Per D-01: separate router file from workspace_permissions.py.
Per D-02: mounted at /api/3.0/mlflow/permissions/workspaces/regex.
Per D-09: full cache.clear() on any regex CUD operation.
All endpoints require admin permission.
"""

from typing import List

from fastapi import APIRouter, Depends, Path, Query

from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models.workspace import (
    WorkspaceGroupRegexPermissionRequest,
    WorkspaceGroupRegexPermissionResponse,
    WorkspaceRegexPermissionRequest,
    WorkspaceRegexPermissionResponse,
)
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils.workspace_cache import flush_workspace_cache

from ._prefix import WORKSPACE_REGEX_PERMISSIONS_ROUTER_PREFIX

logger = get_logger()

workspace_regex_permissions_router = APIRouter(
    prefix=WORKSPACE_REGEX_PERMISSIONS_ROUTER_PREFIX,
    tags=["workspace regex permissions"],
    responses={
        403: {"description": "Forbidden - Admin privileges required"},
        404: {"description": "Resource not found"},
    },
)

# Endpoint path constants
USER_REGEX = "/user"
USER_REGEX_BY_ID = "/user/{permission_id}"
GROUP_REGEX = "/group"
GROUP_REGEX_BY_ID = "/group/{permission_id}"


@workspace_regex_permissions_router.post(
    USER_REGEX,
    response_model=WorkspaceRegexPermissionResponse,
    status_code=201,
    summary="Create user regex workspace permission",
)
async def create_user_regex_permission(
    body: WorkspaceRegexPermissionRequest,
    _: str = Depends(check_admin_permission),
) -> WorkspaceRegexPermissionResponse:
    """Create a user regex workspace permission. Requires admin privileges."""
    _validate_permission(body.permission)
    perm = store.create_workspace_regex_permission(body.regex, body.priority, body.permission, body.username)
    flush_workspace_cache()
    return WorkspaceRegexPermissionResponse(
        id=perm.id,
        regex=perm.regex,
        priority=perm.priority,
        permission=perm.permission,
        username=body.username,
    )


@workspace_regex_permissions_router.get(
    USER_REGEX,
    response_model=List[WorkspaceRegexPermissionResponse],
    summary="List all user regex workspace permissions",
)
async def list_user_regex_permissions(
    _: str = Depends(check_admin_permission),
) -> List[WorkspaceRegexPermissionResponse]:
    """List all user regex workspace permissions. Requires admin privileges."""
    perms = store.list_all_workspace_regex_permissions()
    return [
        WorkspaceRegexPermissionResponse(
            id=p.id,
            regex=p.regex,
            priority=p.priority,
            permission=p.permission,
            username=str(p.user_id),
        )
        for p in perms
    ]


@workspace_regex_permissions_router.patch(
    USER_REGEX_BY_ID,
    response_model=WorkspaceRegexPermissionResponse,
    summary="Update user regex workspace permission",
)
async def update_user_regex_permission(
    body: WorkspaceRegexPermissionRequest,
    permission_id: int = Path(..., description="The permission ID"),
    _: str = Depends(check_admin_permission),
) -> WorkspaceRegexPermissionResponse:
    """Update a user regex workspace permission. Requires admin privileges."""
    _validate_permission(body.permission)
    perm = store.update_workspace_regex_permission(body.regex, body.priority, body.permission, body.username, permission_id)
    flush_workspace_cache()
    return WorkspaceRegexPermissionResponse(
        id=perm.id,
        regex=perm.regex,
        priority=perm.priority,
        permission=perm.permission,
        username=body.username,
    )


@workspace_regex_permissions_router.delete(
    USER_REGEX_BY_ID,
    status_code=204,
    summary="Delete user regex workspace permission",
)
async def delete_user_regex_permission(
    permission_id: int = Path(..., description="The permission ID"),
    username: str = Query(..., description="The username"),
    _: str = Depends(check_admin_permission),
) -> None:
    """Delete a user regex workspace permission. Requires admin privileges."""
    store.delete_workspace_regex_permission(username, permission_id)
    flush_workspace_cache()


@workspace_regex_permissions_router.post(
    GROUP_REGEX,
    response_model=WorkspaceGroupRegexPermissionResponse,
    status_code=201,
    summary="Create group regex workspace permission",
)
async def create_group_regex_permission(
    body: WorkspaceGroupRegexPermissionRequest,
    _: str = Depends(check_admin_permission),
) -> WorkspaceGroupRegexPermissionResponse:
    """Create a group regex workspace permission. Requires admin privileges."""
    _validate_permission(body.permission)
    perm = store.create_workspace_group_regex_permission(body.group_name, body.regex, body.priority, body.permission)
    flush_workspace_cache()
    return WorkspaceGroupRegexPermissionResponse(
        id=perm.id,
        regex=perm.regex,
        priority=perm.priority,
        permission=perm.permission,
        group_name=body.group_name,
    )


@workspace_regex_permissions_router.get(
    GROUP_REGEX,
    response_model=List[WorkspaceGroupRegexPermissionResponse],
    summary="List all group regex workspace permissions",
)
async def list_group_regex_permissions(
    _: str = Depends(check_admin_permission),
) -> List[WorkspaceGroupRegexPermissionResponse]:
    """List all group regex workspace permissions. Requires admin privileges."""
    perms = store.list_all_workspace_group_regex_permissions()
    return [
        WorkspaceGroupRegexPermissionResponse(
            id=p.id,
            regex=p.regex,
            priority=p.priority,
            permission=p.permission,
            group_name=str(p.group_id),
        )
        for p in perms
    ]


@workspace_regex_permissions_router.patch(
    GROUP_REGEX_BY_ID,
    response_model=WorkspaceGroupRegexPermissionResponse,
    summary="Update group regex workspace permission",
)
async def update_group_regex_permission(
    body: WorkspaceGroupRegexPermissionRequest,
    permission_id: int = Path(..., description="The permission ID"),
    _: str = Depends(check_admin_permission),
) -> WorkspaceGroupRegexPermissionResponse:
    """Update a group regex workspace permission. Requires admin privileges."""
    _validate_permission(body.permission)
    perm = store.update_workspace_group_regex_permission(permission_id, body.group_name, body.regex, body.priority, body.permission)
    flush_workspace_cache()
    return WorkspaceGroupRegexPermissionResponse(
        id=perm.id,
        regex=perm.regex,
        priority=perm.priority,
        permission=perm.permission,
        group_name=body.group_name,
    )


@workspace_regex_permissions_router.delete(
    GROUP_REGEX_BY_ID,
    status_code=204,
    summary="Delete group regex workspace permission",
)
async def delete_group_regex_permission(
    permission_id: int = Path(..., description="The permission ID"),
    group_name: str = Query(..., description="The group name"),
    _: str = Depends(check_admin_permission),
) -> None:
    """Delete a group regex workspace permission. Requires admin privileges."""
    store.delete_workspace_group_regex_permission(group_name, permission_id)
    flush_workspace_cache()
