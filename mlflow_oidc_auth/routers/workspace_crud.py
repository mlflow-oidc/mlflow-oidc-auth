"""Workspace CRUD management routes.

FastAPI endpoints that proxy to MLflow's native workspace store with
enhanced validation, permission checks, and structured error handling.
Per WSCRUD-07: validates names client-side. Per WSCRUD-08: feature-flag gated.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from mlflow.server.handlers import _get_workspace_store
from mlflow.store.workspace import Workspace
from mlflow.store.workspace.abstract_store import WorkspaceDeletionMode

from mlflow_oidc_auth.dependencies import (
    check_admin_permission,
    check_workspace_manage_permission,
    check_workspace_read_permission,
)
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models.workspace import (
    WorkspaceCrudCreateRequest,
    WorkspaceCrudResponse,
    WorkspaceCrudUpdateRequest,
)
from mlflow_oidc_auth.utils import get_is_admin, get_username
from mlflow_oidc_auth.utils.workspace_cache import (
    get_workspace_permission_cached,
)

from ._prefix import WORKSPACE_CRUD_ROUTER_PREFIX

logger = get_logger()

workspace_crud_router = APIRouter(
    prefix=WORKSPACE_CRUD_ROUTER_PREFIX,
    tags=["workspace crud"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Workspace not found"},
    },
)


@workspace_crud_router.post(
    "",
    response_model=WorkspaceCrudResponse,
    status_code=201,
    summary="Create a workspace (admin only)",
)
async def create_workspace(
    body: WorkspaceCrudCreateRequest,
    username: str = Depends(check_admin_permission),
) -> WorkspaceCrudResponse:
    """Create a new workspace. Admin-only (WSCRUD-01). Auto-grants MANAGE to creator via after_request hook."""
    try:
        ws_store = _get_workspace_store()
        workspace = ws_store.create_workspace(
            Workspace(
                name=body.name,
                description=body.description,
                default_artifact_root=body.default_artifact_root,
            ),
        )
        logger.info("Workspace created by admin")
        return WorkspaceCrudResponse(
            name=workspace.name,
            description=workspace.description or "",
            default_artifact_root=workspace.default_artifact_root,
        )
    except Exception as e:
        error_msg = str(e)
        if "already exists" in error_msg.lower() or "UNIQUE constraint" in error_msg:
            raise HTTPException(
                status_code=409,
                detail=f"Workspace '{body.name}' already exists",
            )
        logger.error("Failed to create workspace: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create workspace: {error_msg}",
        )


@workspace_crud_router.get(
    "",
    response_model=List[WorkspaceCrudResponse],
    summary="List workspaces (filtered by permissions)",
)
async def list_workspaces(
    request: Request,
) -> List[WorkspaceCrudResponse]:
    """List workspaces. Admins see all; non-admins see only permitted workspaces (WSCRUD-02)."""
    username = await get_username(request=request)
    is_admin = await get_is_admin(request=request)

    ws_store = _get_workspace_store()
    all_workspaces = ws_store.list_workspaces()

    if is_admin:
        return [
            WorkspaceCrudResponse(
                name=ws.name,
                description=ws.description or "",
                default_artifact_root=ws.default_artifact_root,
            )
            for ws in all_workspaces
        ]

    # Filter by user permissions — only include workspaces where the user has at least READ access.
    # A non-None permission with can_read=False (e.g. NO_PERMISSIONS) should still be excluded.
    return [
        WorkspaceCrudResponse(
            name=ws.name,
            description=ws.description or "",
            default_artifact_root=ws.default_artifact_root,
        )
        for ws in all_workspaces
        if (perm := get_workspace_permission_cached(username, ws.name)) is not None and perm.can_read
    ]


@workspace_crud_router.get(
    "/{workspace}",
    response_model=WorkspaceCrudResponse,
    summary="Get workspace details",
)
async def get_workspace(
    workspace: str = Path(..., description="The workspace name"),
    _: str = Depends(check_workspace_read_permission),
) -> WorkspaceCrudResponse:
    """Get workspace details by name. Requires at least READ permission (WSCRUD-03)."""
    try:
        ws_store = _get_workspace_store()
        ws = ws_store.get_workspace(workspace)
        return WorkspaceCrudResponse(
            name=ws.name,
            description=ws.description or "",
            default_artifact_root=ws.default_artifact_root,
        )
    except Exception as e:
        if "not found" in str(e).lower() or "does not exist" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail=f"Workspace '{workspace}' not found",
            )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get workspace: {e}",
        )


@workspace_crud_router.patch(
    "/{workspace}",
    response_model=WorkspaceCrudResponse,
    summary="Update workspace (MANAGE permission required)",
)
async def update_workspace(
    body: WorkspaceCrudUpdateRequest,
    workspace: str = Path(..., description="The workspace name"),
    _: str = Depends(check_workspace_manage_permission),
) -> WorkspaceCrudResponse:
    """Update a workspace description. Requires MANAGE permission (WSCRUD-04)."""
    try:
        ws_store = _get_workspace_store()
        ws = ws_store.update_workspace(
            Workspace(
                name=workspace,
                description=body.description,
                default_artifact_root=body.default_artifact_root,
            ),
        )
        logger.info("Workspace updated")
        return WorkspaceCrudResponse(
            name=ws.name,
            description=ws.description or "",
            default_artifact_root=ws.default_artifact_root,
        )
    except Exception as e:
        if "not found" in str(e).lower() or "does not exist" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail=f"Workspace '{workspace}' not found",
            )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update workspace: {e}",
        )


@workspace_crud_router.delete(
    "/{workspace}",
    status_code=204,
    summary="Delete workspace (MANAGE permission required, RESTRICT mode)",
)
async def delete_workspace(
    workspace: str = Path(..., description="The workspace name"),
    _: str = Depends(check_workspace_manage_permission),
) -> None:
    """Delete a workspace in RESTRICT mode. Requires MANAGE permission (WSCRUD-05).
    The 'default' workspace cannot be deleted."""
    if workspace == "default":
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the default workspace",
        )
    try:
        ws_store = _get_workspace_store()
        ws_store.delete_workspace(workspace, mode=WorkspaceDeletionMode.RESTRICT)
        logger.info("Workspace deleted (RESTRICT mode)")
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
            raise HTTPException(
                status_code=404,
                detail=f"Workspace '{workspace}' not found",
            )
        if "has resources" in error_msg.lower() or "restrict" in error_msg.lower() or "not empty" in error_msg.lower():
            raise HTTPException(
                status_code=409,
                detail=f"Workspace '{workspace}' is not empty. Remove all resources before deleting.",
            )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete workspace: {error_msg}",
        )
