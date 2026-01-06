from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import JSONResponse

from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import GroupPermissionEntry
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import get_is_admin, get_username
from mlflow_oidc_auth.utils.data_fetching import fetch_all_registered_models
from mlflow_oidc_auth.utils.permissions import can_manage_registered_model

from ._prefix import REGISTERED_MODEL_PERMISSIONS_ROUTER_PREFIX

logger = get_logger()

registered_model_permissions_router = APIRouter(
    prefix=REGISTERED_MODEL_PERMISSIONS_ROUTER_PREFIX,
    tags=["registered model permissions"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)


LIST_MODELS = ""


REGISTERED_MODEL_USER_PERMISSIONS = "/{name}/users"
REGISTERED_MODEL_GROUP_PERMISSIONS = "/{name}/groups"


@registered_model_permissions_router.get(
    REGISTERED_MODEL_USER_PERMISSIONS,
    summary="List users with permissions for a registered model",
    description="Retrieves a list of users who have permissions for the specified registered model.",
)
async def get_registered_model_users(
    name: str = Path(..., description="The registered model name to get permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    List all users with permissions for a specific registered model.

    This endpoint returns all users who have explicitly assigned permissions
    for the specified registered model. The requesting user must be an admin.

    Parameters:
    -----------
    name : str
        The name of the registered model to get user permissions for.
    admin_username : str
        The authenticated admin username (injected by dependency).

    Returns:
    --------
    JSONResponse
        A JSON response containing users with their permission levels for the registered model.

    Raises:
    -------
    HTTPException
        If there is an error retrieving the user permissions.
    """
    list_users = store.list_users(all=True)

    # Filter users who are associated with the given registered model
    users = []
    for user in list_users:
        # Check if the user is associated with the registered model
        user_models = {}
        if hasattr(user, "registered_model_permissions") and user.registered_model_permissions:
            user_models = {model.name: model.permission for model in user.registered_model_permissions}

        if name in user_models:
            users.append(
                {
                    "username": user.username,
                    "permission": user_models[name],
                    "kind": "user" if not user.is_service_account else "service-account",
                }
            )
    return JSONResponse(content=users)


@registered_model_permissions_router.get(
    REGISTERED_MODEL_GROUP_PERMISSIONS,
    response_model=List[GroupPermissionEntry],
    summary="List groups with permissions for a registered model",
    description="Retrieves a list of groups that have permissions for the specified registered model.",
)
async def get_registered_model_groups(
    name: str = Path(..., description="The registered model name to get group permissions for"),
    _: str = Depends(check_admin_permission),
) -> List[GroupPermissionEntry]:
    """List groups with explicit permissions for a registered model."""

    try:
        groups = store.registered_model_group_repo.list_groups_for_model(str(name))
        return [GroupPermissionEntry(name=name, permission=permission) for name, permission in groups]
    except Exception as e:
        logger.error(f"Error retrieving registered model group permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve registered model group permissions")


@registered_model_permissions_router.get(
    LIST_MODELS, summary="List accessible registered models", description="Retrieves a list of registered models that the user has access to."
)
async def list_models(username: str = Depends(get_username), is_admin: bool = Depends(get_is_admin)) -> JSONResponse:
    """
    List registered models accessible to the authenticated user.

    This endpoint returns registered models based on user permissions:
    - Administrators can see all models
    - Regular users only see models they can manage

    Parameters:
    -----------
    username : str
        The authenticated username (injected by dependency).
    is_admin : bool
        Whether the user has admin privileges (injected by dependency).

    Returns:
    --------
    JSONResponse
        A JSON response containing the list of accessible registered models.

    Raises:
    -------
    HTTPException
        If there is an error retrieving the registered models.
    """
    if is_admin:
        # Admin can see all registered models
        registered_models = fetch_all_registered_models()
    else:
        # Regular user can only see models they can manage
        all_models = fetch_all_registered_models()
        registered_models = []

        for model in all_models:
            if can_manage_registered_model(model.name, username):
                registered_models.append(model)

    return JSONResponse(
        content=[
            {
                "name": model.name,
                "tags": model.tags,
                "description": model.description,
                "aliases": model.aliases,
            }
            for model in registered_models
        ]
    )
