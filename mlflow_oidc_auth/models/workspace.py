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


class WorkspaceRegexPermissionRequest(BaseModel):
    """Request model for creating/updating a user regex workspace permission."""

    regex: str = Field(..., description="Regex pattern to match workspace names")
    priority: int = Field(
        ..., description="Priority (lower number = higher priority, per D-07)"
    )
    permission: str = Field(
        ..., description="Permission level (READ, USE, EDIT, MANAGE)"
    )
    username: str = Field(
        ..., description="Username to grant regex workspace permission to"
    )


class WorkspaceGroupRegexPermissionRequest(BaseModel):
    """Request model for creating/updating a group regex workspace permission."""

    regex: str = Field(..., description="Regex pattern to match workspace names")
    priority: int = Field(
        ..., description="Priority (lower number = higher priority, per D-07)"
    )
    permission: str = Field(
        ..., description="Permission level (READ, USE, EDIT, MANAGE)"
    )
    group_name: str = Field(
        ..., description="Group name to grant regex workspace permission to"
    )


class WorkspaceRegexPermissionResponse(BaseModel):
    """Response model for a user regex workspace permission."""

    id: int = Field(..., description="Permission ID")
    regex: str = Field(..., description="Regex pattern")
    priority: int = Field(..., description="Priority")
    permission: str = Field(..., description="Permission level")
    username: str = Field(..., description="Username")


class WorkspaceGroupRegexPermissionResponse(BaseModel):
    """Response model for a group regex workspace permission."""

    id: int = Field(..., description="Permission ID")
    regex: str = Field(..., description="Regex pattern")
    priority: int = Field(..., description="Priority")
    permission: str = Field(..., description="Permission level")
    group_name: str = Field(..., description="Group name")
