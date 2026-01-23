"""Pydantic models for scorer permission APIs."""

from typing import Optional

from pydantic import BaseModel, Field


class ScorerPermission(BaseModel):
    """Model for creating or updating a scorer permission."""

    permission: str = Field(..., description="Permission level for the scorer")


class ScorerRegexCreate(BaseModel):
    """Model for creating or updating a regex-based scorer permission."""

    regex: str = Field(..., description="Regex pattern to match scorer names")
    priority: int = Field(..., description="Priority of the permission rule")
    permission: str = Field(..., description="Permission level for matching scorers")


class ScorerPermissionRequest(BaseModel):
    """Request payload for scorer permission CRUD endpoints.

    MLflow v3 scorer permission routes expect these fields.
    """

    experiment_id: str = Field(..., description="Experiment ID owning the scorer")
    scorer_name: str = Field(..., description="Scorer name")
    username: str = Field(..., description="Target username")
    permission: str = Field(..., description="Permission name (e.g. READ/UPDATE/DELETE/MANAGE)")


class ScorerSummary(BaseModel):
    """Lightweight representation of a scorer entry for listing endpoints."""

    experiment_id: str = Field(..., description="Experiment identifier that owns the scorer")
    name: str = Field(..., description="Scorer name")
    version: int = Field(..., description="Scorer version number")
    creation_time: int = Field(..., description="Creation timestamp in milliseconds since epoch")
    scorer_id: Optional[str] = Field(None, description="Unique scorer identifier if present")
