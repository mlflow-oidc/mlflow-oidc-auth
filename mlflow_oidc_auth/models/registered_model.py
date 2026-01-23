from pydantic import BaseModel, Field


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
