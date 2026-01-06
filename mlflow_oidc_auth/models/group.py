from pydantic import BaseModel, Field


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


class GroupPermissionEntry(BaseModel):
    """Permission information for a group on a specific resource.

    This is used for endpoints like:
    - /mlflow/permissions/experiments/{experiment_id}/groups
    - /mlflow/permissions/registered-models/{name}/groups
    - /mlflow/permissions/prompts/{prompt_name}/groups
    - /mlflow/permissions/scorers/{experiment_id}/{scorer_name}/groups
    """

    group_name: str = Field(..., description="Group name")
    permission: str = Field(..., description="Permission level for the group")
