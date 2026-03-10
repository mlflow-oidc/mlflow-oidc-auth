from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import JSONResponse

from mlflow_oidc_auth.dependencies import check_prompt_manage_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import UserPermission, GroupPermissionEntry
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import fetch_all_prompts, get_is_admin, get_username
from mlflow_oidc_auth.utils.batch_permissions import filter_manageable_prompts

from ._prefix import PROMPT_PERMISSIONS_ROUTER_PREFIX

logger = get_logger()

prompt_permissions_router = APIRouter(
    prefix=PROMPT_PERMISSIONS_ROUTER_PREFIX,
    tags=["prompt permissions"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)


LIST_PROMPTS = ""
PROMPT_USER_PERMISSIONS = "/{prompt_name:path}/users"
PROMPT_GROUP_PERMISSIONS = "/{prompt_name:path}/groups"


@prompt_permissions_router.get(
    PROMPT_USER_PERMISSIONS,
    response_model=List[UserPermission],
    summary="List users with permissions for a prompt",
    description="Retrieves a list of users who have permissions for the specified prompt.",
)
async def get_prompt_users(
    prompt_name: str = Path(..., description="The prompt name to get permissions for"), _: None = Depends(check_prompt_manage_permission)
) -> List[UserPermission]:
    """
    List all users with permissions for a specific prompt.

    This endpoint returns all users who have explicitly assigned permissions
    for the specified prompt. The requesting user must be an admin or
    have management permissions for the prompt.

    Parameters:
    -----------
    prompt_name : str
        The name of the prompt to get user permissions for.
    _ : None
        Dependency that ensures the requester is an admin or can manage the prompt.

    Returns:
    --------
    List[UserPermission]
        A list of users with their permission levels for the prompt.

    Raises:
    -------
    HTTPException
        If there is an error retrieving the user permissions.
    """
    # Get all users
    list_users = store.list_users(all=True)

    # Filter users who are associated with the given prompt
    # Note: In this system, prompts are treated as registered models with special handling
    users: List[UserPermission] = []
    for user in list_users:
        # Check if the user is associated with the prompt
        # Prompts are stored as registered models in the system
        user_models = {}
        if hasattr(user, "registered_model_permissions") and user.registered_model_permissions:
            user_models = {model.name: model.permission for model in user.registered_model_permissions}

        if prompt_name in user_models:
            users.append(
                UserPermission(
                    name=user.username,
                    permission=user_models[prompt_name],
                    kind="service-account" if user.is_service_account else "user",
                )
            )

    return users


@prompt_permissions_router.get(
    PROMPT_GROUP_PERMISSIONS,
    response_model=List[GroupPermissionEntry],
    summary="List groups with permissions for a prompt",
    description="Retrieves a list of groups that have permissions for the specified prompt.",
)
async def get_prompt_groups(
    prompt_name: str = Path(..., description="The prompt name to get group permissions for"),
    _: None = Depends(check_prompt_manage_permission),
) -> List[GroupPermissionEntry]:
    """List groups with explicit permissions for a prompt."""

    try:
        groups = store.prompt_group_repo.list_groups_for_prompt(str(prompt_name))
        return [GroupPermissionEntry(name=name, permission=permission) for name, permission in groups]
    except Exception as e:
        logger.error(f"Error retrieving prompt group permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve prompt group permissions")


@prompt_permissions_router.get(LIST_PROMPTS, summary="List accessible prompts", description="Retrieves a list of prompts that the user has access to.")
async def list_prompts(username: str = Depends(get_username), is_admin: bool = Depends(get_is_admin)) -> JSONResponse:
    """
    List prompts accessible to the authenticated user.

    This endpoint returns prompts based on user permissions:
    - Administrators can see all prompts
    - Regular users only see prompts they can manage

    Parameters:
    -----------
    username : str
        The authenticated username (injected by dependency).
    is_admin : bool
        Whether the user has admin privileges (injected by dependency).

    Returns:
    --------
    JSONResponse
        A JSON response containing the list of accessible prompts.

    Raises:
    -------
    HTTPException
        If there is an error retrieving the prompts.
    """
    # Fetch all prompts and filter based on permissions (batch resolution for efficiency)
    all_prompts = fetch_all_prompts()

    if is_admin:
        # Admin can see all prompts
        prompts = all_prompts
    else:
        # Regular user can only see prompts they can manage
        prompts = filter_manageable_prompts(username, all_prompts)

    return JSONResponse(
        content=[
            {
                "name": model.name,
                "tags": model.tags,
                "description": model.description,
                "aliases": model.aliases,
            }
            for model in prompts
        ]
    )
