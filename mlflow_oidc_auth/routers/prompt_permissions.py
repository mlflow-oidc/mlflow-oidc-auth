from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse

from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import fetch_all_prompts, get_is_admin, get_username
from mlflow_oidc_auth.utils.permissions import can_manage_registered_model

from ._prefix import PROMPT_PERMISSIONS_ROUTER_PREFIX

logger = get_logger()

prompt_permissions_router = APIRouter(
    prefix=PROMPT_PERMISSIONS_ROUTER_PREFIX,
    tags=["permissions"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)


LIST_PROMPTS = ""
PROMPT_USER_PERMISSIONS = "/{prompt_name}/users"


@prompt_permissions_router.get(
    PROMPT_USER_PERMISSIONS,
    summary="List users with permissions for a prompt",
    description="Retrieves a list of users who have permissions for the specified prompt.",
)
async def get_prompt_users(
    prompt_name: str = Path(..., description="The prompt name to get permissions for"), admin_username: str = Depends(check_admin_permission)
) -> JSONResponse:
    """
    List all users with permissions for a specific prompt.

    This endpoint returns all users who have explicitly assigned permissions
    for the specified prompt. The requesting user must be an admin or
    have management permissions for the prompt.

    Parameters:
    -----------
    prompt_name : str
        The name of the prompt to get user permissions for.
    admin_username : str
        The authenticated username (injected by dependency).

    Returns:
    --------
    JSONResponse
        A JSON response containing users with their permission levels for the prompt.

    Raises:
    -------
    HTTPException
        If there is an error retrieving the user permissions.
    """
    # Get all users
    list_users = store.list_users(all=True)

    # Filter users who are associated with the given prompt
    # Note: In this system, prompts are treated as registered models with special handling
    users = []
    for user in list_users:
        # Check if the user is associated with the prompt
        # Prompts are stored as registered models in the system
        user_models = {}
        if hasattr(user, "registered_model_permissions") and user.registered_model_permissions:
            user_models = {model.name: model.permission for model in user.registered_model_permissions}

        if prompt_name in user_models:
            users.append(
                {
                    "username": user.username,
                    "permission": user_models[prompt_name],
                    "kind": "user" if not user.is_service_account else "service-account",
                }
            )

    return JSONResponse(content=users)


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
    if is_admin:
        # Admin can see all prompts
        prompts = fetch_all_prompts()
    else:
        # Regular user can only see prompts they can manage
        all_prompts = fetch_all_prompts()
        prompts = []

        for prompt in all_prompts:
            # Prompts are handled as registered models in this system
            if can_manage_registered_model(prompt.name, username):
                prompts.append(prompt)

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
