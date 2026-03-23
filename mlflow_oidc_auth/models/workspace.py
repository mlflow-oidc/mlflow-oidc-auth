"""Pydantic request/response models for workspace permission CRUD.

These models support the workspace permissions router endpoints
for managing user and group workspace-level permissions.
"""

from pydantic import BaseModel, Field


class WorkspaceUserPermissionRequest(BaseModel):
    """Request model for creating/updating a user workspace permission."""

    username: str = Field(..., description="Username to grant workspace permission to")
    permission: str = Field(
        ..., description="Permission level (READ, USE, EDIT, MANAGE)"
    )


class WorkspaceGroupPermissionRequest(BaseModel):
    """Request model for creating/updating a group workspace permission."""

    group_name: str = Field(
        ..., description="Group name to grant workspace permission to"
    )
    permission: str = Field(
        ..., description="Permission level (READ, USE, EDIT, MANAGE)"
    )


class WorkspaceUserPermissionResponse(BaseModel):
    """Response model for a user workspace permission."""

    workspace: str = Field(..., description="Workspace name")
    username: str = Field(..., description="Username")
    permission: str = Field(..., description="Permission level")


class WorkspaceGroupPermissionResponse(BaseModel):
    """Response model for a group workspace permission."""

    workspace: str = Field(..., description="Workspace name")
    group_name: str = Field(..., description="Group name")
    permission: str = Field(..., description="Permission level")
