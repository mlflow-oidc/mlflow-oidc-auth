from typing import Dict, Optional

from pydantic import BaseModel, Field


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
