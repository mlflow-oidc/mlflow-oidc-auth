from typing import List, Literal, Optional

from pydantic import BaseModel, Field, RootModel


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
    kind: Literal["group"] = Field("group", description="Indicates this is a group experiment permission")


class GroupRegexPermission(BaseModel):
    """
    Regex-based permission information for a group.

    Parameters:
    -----------
    id : str
        Unique identifier for the regex pattern.
    regex : str
        Regular expression pattern to match resources.
    priority : int
        Priority of this rule (lower numbers = higher priority).
    permission : str
        The permission level to grant.
    """

    id: str = Field(..., description="Unique identifier for the regex pattern")
    regex: str = Field(..., description="Regex pattern to match resources")
    priority: int = Field(..., description="Priority of the permission rule")
    permission: str = Field(..., description="Permission level for matching resources")
    kind: Literal["group"] = Field("group", description="Indicates this is a group regex permission")


class GroupPermissionEntry(BaseModel):
    """Permission information for a group on a specific resource.

    This is used for endpoints like:
    - /mlflow/permissions/experiments/{experiment_id}/groups
    - /mlflow/permissions/registered-models/{name}/groups
    - /mlflow/permissions/prompts/{prompt_name}/groups
    - /mlflow/permissions/scorers/{experiment_id}/{scorer_name}/groups
    """

    name: str = Field(..., description="Group name")
    permission: str = Field(..., description="Permission level for the group")
    kind: Literal["group"] = Field("group", description="Indicates this is a group permission entry")


class GroupListResponse(RootModel[List[str]]):
    """Wrapper response for group listings while keeping a flat payload."""

    root: List[str]


class GroupExperimentPermissionItem(BaseModel):
    """Serialized experiment permission entry for a group."""

    id: str = Field(..., description="Experiment ID")
    name: str = Field(..., description="Experiment name")
    permission: str = Field(..., description="Permission level granted to the group")
    kind: Literal["group"] = Field("group", description="Indicates this is a group experiment permission")


class GroupNamedPermissionItem(BaseModel):
    """Serialized named resource permission entry for a group."""

    name: str = Field(..., description="Resource name")
    permission: str = Field(..., description="Permission level granted to the group")
    kind: Literal["group"] = Field("group", description="Indicates this is a group named permission")


class GroupExperimentRegexPermissionItem(BaseModel):
    """Serialized experiment regex permission entry for a group."""

    id: int = Field(..., description="Pattern identifier")
    regex: str = Field(..., description="Regex pattern")
    priority: int = Field(..., description="Evaluation priority")
    group_id: Optional[int] = Field(None, description="Identifier of the group that owns the pattern")
    permission: str = Field(..., description="Permission granted when the regex matches")
    kind: Literal["group"] = Field("group", description="Indicates this is a group experiment regex permission")


class GroupRegisteredModelRegexPermissionItem(BaseModel):
    """Serialized registered model regex permission entry for a group."""

    id: int = Field(..., description="Pattern identifier")
    regex: str = Field(..., description="Regex pattern")
    priority: int = Field(..., description="Evaluation priority")
    group_id: Optional[int] = Field(None, description="Identifier of the group that owns the pattern")
    permission: str = Field(..., description="Permission granted when the regex matches")
    prompt: bool = Field(..., description="Whether the pattern targets prompts instead of registered models")
    kind: Literal["group"] = Field("group", description="Indicates this is a group registered model regex permission")


class GroupPromptRegexPermissionItem(GroupRegisteredModelRegexPermissionItem):
    """Serialized prompt regex permission entry for a group."""


class GroupScorerPermissionItem(BaseModel):
    """Serialized scorer permission entry for a group."""

    experiment_id: str = Field(..., description="Experiment identifier of the scorer")
    scorer_name: str = Field(..., description="Scorer name")
    group_id: Optional[int] = Field(None, description="Identifier of the group that owns the permission")
    permission: str = Field(..., description="Permission granted to the group for the scorer")
    kind: Literal["group"] = Field("group", description="Indicates this is a group scorer permission")


class GroupScorerRegexPermissionItem(BaseModel):
    """Serialized scorer regex permission entry for a group."""

    id: int = Field(..., description="Pattern identifier")
    regex: str = Field(..., description="Regex pattern")
    priority: int = Field(..., description="Evaluation priority")
    group_id: Optional[int] = Field(None, description="Identifier of the group that owns the pattern")
    permission: str = Field(..., description="Permission granted when the regex matches")
    kind: Literal["group"] = Field("group", description="Indicates this is a group scorer regex permission")


class GroupGatewayRegexPermissionItem(BaseModel):
    """Serialized gateway regex permission entry for a group."""

    id: int = Field(..., description="Pattern identifier")
    regex: str = Field(..., description="Regex pattern")
    priority: int = Field(..., description="Evaluation priority")
    group_id: Optional[int] = Field(None, description="Identifier of the group that owns the pattern")
    permission: str = Field(..., description="Permission granted when the regex matches")
    kind: Literal["group"] = Field("group", description="Indicates this is a group gateway regex permission")
