"""Pydantic request/response models for workspace permission CRUD.

These models support the workspace permissions router endpoints
for managing user and group workspace-level permissions,
and the workspace CRUD router for workspace lifecycle management.
"""

import re

from pydantic import BaseModel, Field, field_validator

# MLflow workspace name validation (matches WorkspaceNameValidator in mlflow.server.handlers)
WORKSPACE_NAME_PATTERN = re.compile(r"^(?!.*--)[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
WORKSPACE_NAME_MIN_LENGTH = 2
WORKSPACE_NAME_MAX_LENGTH = 63
WORKSPACE_RESERVED_NAMES = {"workspaces", "api", "ajax-api", "static-files"}


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


# ──────────────────────────────────────────────────────────────────────────
# Workspace CRUD models (WSCRUD-07)
# ──────────────────────────────────────────────────────────────────────────


class WorkspaceCrudCreateRequest(BaseModel):
    """Request model for creating a workspace (WSCRUD-07)."""

    name: str = Field(
        ...,
        min_length=WORKSPACE_NAME_MIN_LENGTH,
        max_length=WORKSPACE_NAME_MAX_LENGTH,
        description="DNS-safe workspace name",
    )
    description: str = Field(
        "", max_length=500, description="Optional workspace description"
    )
    default_artifact_root: str | None = Field(
        None,
        max_length=1024,
        description="Optional artifact storage root URI (e.g. s3://team-a-artifacts)",
    )

    @field_validator("name")
    @classmethod
    def validate_workspace_name(cls, v: str) -> str:
        if not WORKSPACE_NAME_PATTERN.match(v):
            raise ValueError(
                "Workspace name must be DNS-safe: lowercase alphanumeric and hyphens, "
                "no leading/trailing hyphens, no consecutive hyphens"
            )
        if v in WORKSPACE_RESERVED_NAMES:
            raise ValueError(f"'{v}' is a reserved workspace name")
        return v


class WorkspaceCrudUpdateRequest(BaseModel):
    """Request model for updating a workspace (WSCRUD-07)."""

    description: str = Field(
        ..., max_length=500, description="Updated workspace description"
    )
    default_artifact_root: str | None = Field(
        None,
        max_length=1024,
        description="Optional artifact storage root URI (e.g. s3://team-a-artifacts)",
    )


class WorkspaceCrudResponse(BaseModel):
    """Response model for a workspace."""

    name: str = Field(..., description="Workspace name")
    description: str = Field("", description="Workspace description")
    default_artifact_root: str | None = Field(
        None, description="Artifact storage root URI"
    )
