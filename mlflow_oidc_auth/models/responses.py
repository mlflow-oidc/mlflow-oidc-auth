"""Shared API response models.

These models are used by routers to provide consistent, typed responses instead
of ad-hoc JSONResponse payloads.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Simple message-only response."""

    message: str = Field(..., description="Human-readable message")


class StatusOnlyResponse(BaseModel):
    """Response that indicates success/failure without extra payload."""

    status: Literal["success"] = Field("success", description="Operation status")


class StatusMessageResponse(BaseModel):
    """Response with a status plus a human-readable message."""

    status: Literal["success"] = Field("success", description="Operation status")
    message: str = Field(..., description="Human-readable message")


class NamedPermissionSummary(BaseModel):
    """Permission summary for a named resource (e.g. prompt, model)."""

    name: str = Field(..., description="Resource name")
    permission: str = Field(..., description="Permission name")
    kind: str = Field(..., description="Source kind of the effective permission")


class ExperimentPermissionRecord(BaseModel):
    """Serialized experiment permission record."""

    experiment_id: str = Field(..., description="Experiment ID")
    permission: str = Field(..., description="Permission name")
    user_id: Optional[int] = Field(None, description="User ID")
    group_id: Optional[int] = Field(None, description="Group ID (if permission granted via group)")


class ExperimentPermissionResponse(BaseModel):
    """Wrapper response for a single experiment permission."""

    experiment_permission: ExperimentPermissionRecord


class RegisteredModelPermissionRecord(BaseModel):
    """Serialized registered model / prompt permission record."""

    name: str = Field(..., description="Registered model or prompt name")
    user_id: Optional[int] = Field(None, description="User ID")
    permission: str = Field(..., description="Permission name")
    group_id: Optional[int] = Field(None, description="Group ID (if permission granted via group)")
    prompt: bool = Field(False, description="True if this permission is for a prompt")


class PromptPermissionResponse(BaseModel):
    """Wrapper response for a single prompt permission."""

    prompt_permission: RegisteredModelPermissionRecord


class RegisteredModelPermissionResponse(BaseModel):
    """Wrapper response for a single registered model permission."""

    registered_model_permission: RegisteredModelPermissionRecord


class RegisteredModelRegexPermissionRecord(BaseModel):
    """Serialized prompt/registered-model regex permission record."""

    id: int = Field(..., description="Pattern ID")
    regex: str = Field(..., description="Regex pattern")
    priority: int = Field(..., description="Evaluation priority")
    user_id: int = Field(..., description="User ID")
    permission: str = Field(..., description="Permission name")
    prompt: bool = Field(False, description="True if this pattern applies to prompts")


class PromptRegexPermissionResponse(BaseModel):
    """Wrapper response for a single prompt regex permission record."""

    prompt_permission: RegisteredModelRegexPermissionRecord


class RegisteredModelRegexPermissionResponse(BaseModel):
    """Wrapper response for a single registered model regex permission record."""

    registered_model_permission: RegisteredModelRegexPermissionRecord


class ScorerPermissionRecord(BaseModel):
    """Serialized scorer permission record."""

    experiment_id: str = Field(..., description="Experiment ID")
    scorer_name: str = Field(..., description="Scorer name")
    user_id: int = Field(..., description="User ID")
    permission: str = Field(..., description="Permission name")


class ScorerPermissionResponse(BaseModel):
    """Wrapper response for a single scorer permission."""

    scorer_permission: ScorerPermissionRecord


class ScorerRegexPermissionRecord(BaseModel):
    """Serialized scorer regex permission record."""

    id: int = Field(..., description="Pattern ID")
    regex: str = Field(..., description="Regex pattern")
    priority: int = Field(..., description="Evaluation priority")
    user_id: int = Field(..., description="User ID")
    permission: str = Field(..., description="Permission name")


class ScorerRegexPermissionResponse(BaseModel):
    """Wrapper response for a single scorer regex permission record."""

    pattern: ScorerRegexPermissionRecord


class GatewayPermissionRecord(BaseModel):
    """Serialized gateway permission record."""

    gateway_name: str = Field(..., description="Gateway name")
    user_id: Optional[int] = Field(None, description="User ID")
    permission: str = Field(..., description="Permission name")
    group_id: Optional[int] = Field(None, description="Group ID (if permission granted via group)")


class GatewayPermissionResponse(BaseModel):
    """Wrapper response for a single gateway permission."""

    gateway_permission: GatewayPermissionRecord


class GatewayRegexPermissionRecord(BaseModel):
    """Serialized gateway regex permission record."""

    id: int = Field(..., description="Pattern ID")
    regex: str = Field(..., description="Regex pattern")
    priority: int = Field(..., description="Evaluation priority")
    user_id: int = Field(..., description="User ID")
    permission: str = Field(..., description="Permission name")


class GatewayRegexPermissionResponse(BaseModel):
    """Wrapper response for a single gateway regex permission record."""

    gateway_permission: GatewayRegexPermissionRecord


class RegisteredModelRegexPermissionListResponse(BaseModel):
    """List wrapper for prompt/model regex permissions.

    Not currently used by routers, but available for future response normalization.
    """

    patterns: List[RegisteredModelRegexPermissionRecord]


class GroupRecord(BaseModel):
    """Serialized group record for user profile responses."""

    id: int = Field(..., description="Group ID")
    group_name: str = Field(..., description="Group name")


class CurrentUserProfile(BaseModel):
    """Lightweight current-user profile.

    This model intentionally excludes permission collections to keep the payload
    small and avoid heavy DB loads on common UI calls.
    """

    display_name: str = Field(..., description="Display name")
    groups: List[GroupRecord] = Field(default_factory=list, description="Groups the user belongs to")
    id: int = Field(..., description="User ID")
    is_admin: bool = Field(..., description="Whether the user is an administrator")
    is_service_account: bool = Field(..., description="Whether the user is a service account")
    password_expiration: Optional[str] = Field(None, description="Password expiration ISO timestamp")
    username: str = Field(..., description="Username")
