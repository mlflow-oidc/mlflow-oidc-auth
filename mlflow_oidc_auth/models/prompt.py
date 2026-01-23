from pydantic import BaseModel, Field


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
