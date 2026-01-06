from typing import NamedTuple, Literal
from pydantic import BaseModel, Field

from mlflow_oidc_auth.permissions import Permission


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


class UserPermission(BaseModel):
    """
    User permission information.

    Parameters:
    -----------
    name : str
        The username of the user with access to the resource.
    permission : str
        The permission level the user has for this resource.
    kind : str
        The type of user account ('user' or 'service-account').
    """

    name: str = Field(..., description="Username of the user with access")
    permission: str = Field(..., description="Permission level for the resource")
    kind: Literal["user", "service-account"] = Field(..., description="Type of user account")
