"""
Pydantic models for request/response data validation.

This module defines data models used for validating API request and response data.
"""

from typing import Dict, Literal, NamedTuple, Optional

from pydantic import BaseModel, Field

from mlflow_oidc_auth.permissions import Permission


class ExperimentPermission(BaseModel):
    """
    Model for creating or updating an experiment permission.

    Parameters:
    -----------
    permission : str
        The permission level to grant (e.g., "READ", "WRITE", "MANAGE").
    """

    permission: str = Field(..., description="Permission level for the experiment")


class ExperimentRegexCreate(BaseModel):
    """
    Model for creating or updating a regex-based experiment permission.

    Parameters:
    -----------
    regex : str
        Regular expression pattern to match experiment names/IDs.
    priority : int
        Priority of this rule (lower numbers = higher priority).
    permission : str
        The permission level to grant.
    """

    regex: str = Field(..., description="Regex pattern to match experiments")
    priority: int = Field(..., description="Priority of the permission rule")
    permission: str = Field(..., description="Permission level for matching experiments")


# Add this to your existing models file
class ExperimentPermissionSummary(BaseModel):
    """
    Summary of an experiment with its associated permission for a user.

    Parameters:
    -----------
    name : str
        The name of the experiment.
    id : str
        The unique identifier of the experiment.
    permission : str
        The permission level the user has for this experiment.
    type : str
        The type of permission (direct, regex, etc.).
    """

    name: str = Field(..., description="The name of the experiment")
    id: str = Field(..., description="The experiment ID")
    permission: str = Field(..., description="The permission level")
    type: str = Field(..., description="The type of permission (direct, regex, etc.)")


class ExperimentSummary(BaseModel):
    """
    Summary information about an MLflow experiment.

    Parameters:
    -----------
    name : str
        The name of the experiment.
    id : str
        The unique identifier of the experiment.
    tags : Optional[Dict[str, str]]
        Key-value pairs of tags associated with the experiment.
    """

    name: str = Field(..., description="The name of the experiment")
    id: str = Field(..., description="The unique identifier of the experiment")
    tags: Optional[Dict[str, str]] = Field(None, description="Tags associated with the experiment")


class ExperimentUserPermission(BaseModel):
    """
    User permission information for an experiment.

    Parameters:
    -----------
    username : str
        The username of the user with access to the experiment.
    permission : str
        The permission level the user has for this experiment.
    kind : str
        The type of user account ('user' or 'service-account').
    """

    username: str = Field(..., description="Username of the user with access")
    permission: str = Field(..., description="Permission level for the experiment")
    kind: Literal["user", "service-account"] = Field(..., description="Type of user account")


class ExperimentRegexPermission(BaseModel):
    """
    Regex-based experiment permission information.

    Parameters:
    -----------
    pattern_id : str
        Unique identifier for the regex pattern.
    regex : str
        Regular expression pattern to match experiment names/IDs.
    priority : int
        Priority of this rule (lower numbers = higher priority).
    permission : str
        The permission level to grant.
    """

    pattern_id: str = Field(..., description="Unique identifier for the regex pattern")
    regex: str = Field(..., description="Regex pattern to match experiments")
    priority: int = Field(..., description="Priority of the permission rule")
    permission: str = Field(..., description="Permission level for matching experiments")


class PromptPermission(BaseModel):
    """
    Model for creating or updating a prompt permission.

    Parameters:
    -----------
    permission : str
        The permission level to grant (e.g., "READ", "WRITE", "MANAGE").
    """

    permission: str = Field(..., description="Permission level for the prompt")


class PromptRegexCreate(BaseModel):
    """
    Model for creating or updating a regex-based prompt permission.

    Parameters:
    -----------
    regex : str
        Regular expression pattern to match prompt names.
    priority : int
        Priority of this rule (lower numbers = higher priority).
    permission : str
        The permission level to grant.
    """

    regex: str = Field(..., description="Regex pattern to match prompts")
    priority: int = Field(..., description="Priority of the permission rule")
    permission: str = Field(..., description="Permission level for matching prompts")


class RegisteredModelPermission(BaseModel):
    """
    Model for creating or updating a registered model permission.

    Parameters:
    -----------
    permission : str
        The permission level to grant (e.g., "READ", "WRITE", "MANAGE").
    """

    permission: str = Field(..., description="Permission level for the registered model")


class RegisteredModelRegexCreate(BaseModel):
    """
    Model for creating or updating a regex-based registered model permission.

    Parameters:
    -----------
    regex : str
        Regular expression pattern to match model names.
    priority : int
        Priority of this rule (lower numbers = higher priority).
    permission : str
        The permission level to grant.
    """

    regex: str = Field(..., description="Regex pattern to match models")
    priority: int = Field(..., description="Priority of the permission rule")
    permission: str = Field(..., description="Permission level for matching models")


class GroupUser(BaseModel):
    """
    User information within a group.

    Parameters:
    -----------
    username : str
        The username of the user in the group.
    is_admin : bool
        Whether the user has admin privileges in the group.
    """

    username: str = Field(..., description="Username of the user in the group")
    is_admin: bool = Field(..., description="Whether the user has admin privileges")


class GroupExperimentPermission(BaseModel):
    """
    Experiment permission information for a group.

    Parameters:
    -----------
    experiment_id : str
        The ID of the experiment.
    experiment_name : str
        The name of the experiment.
    permission : str
        The permission level the group has for this experiment.
    """

    experiment_id: str = Field(..., description="The experiment ID")
    experiment_name: str = Field(..., description="The name of the experiment")
    permission: str = Field(..., description="Permission level for the experiment")


class GroupRegexPermission(BaseModel):
    """
    Regex-based permission information for a group.

    Parameters:
    -----------
    pattern_id : str
        Unique identifier for the regex pattern.
    regex : str
        Regular expression pattern to match resources.
    priority : int
        Priority of this rule (lower numbers = higher priority).
    permission : str
        The permission level to grant.
    """

    pattern_id: str = Field(..., description="Unique identifier for the regex pattern")
    regex: str = Field(..., description="Regex pattern to match resources")
    priority: int = Field(..., description="Priority of the permission rule")
    permission: str = Field(..., description="Permission level for matching resources")


class CreateAccessTokenRequest(BaseModel):
    """Request model for creating access tokens."""

    username: Optional[str] = None  # Optional, will use authenticated user if not provided
    expiration: Optional[str] = None  # ISO 8601 format string


class CreateUserRequest(BaseModel):
    """Request model for creating users."""

    username: str
    display_name: str
    is_admin: bool = False
    is_service_account: bool = False


class PermissionResult(NamedTuple):
    """
    Result object containing permission information and its source.

    This class encapsulates both the permission details and metadata about
    where the permission was determined from (e.g., user, group, regex, fallback).

    Attributes:
        permission (Permission): The Permission object containing access rights
        type (str): String indicating the source type (e.g., 'user', 'group', 'regex', 'fallback')
    """

    permission: Permission
    type: str
