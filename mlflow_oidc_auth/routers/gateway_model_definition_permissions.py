from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import JSONResponse

from mlflow_oidc_auth.dependencies import check_gateway_model_definition_manage_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models.group import GroupPermissionEntry
from mlflow_oidc_auth.models.permission import UserPermission
from mlflow_oidc_auth.routers._prefix import GATEWAY_PERMISSIONS_ROUTER_PREFIX
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import fetch_all_gateway_model_definitions, get_is_admin, get_username
from mlflow_oidc_auth.utils.batch_permissions import filter_manageable_gateway_model_definitions

logger = get_logger()

gateway_model_definition_permissions_router = APIRouter(
    prefix=f"{GATEWAY_PERMISSIONS_ROUTER_PREFIX}/model-definitions",
    tags=["gateway model definition permissions"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)


LIST_MODEL_DEFINITIONS = ""

GATEWAY_MODEL_DEFINITION_USER_PERMISSIONS = "/{name}/users"
GATEWAY_MODEL_DEFINITION_GROUP_PERMISSIONS = "/{name}/groups"


@gateway_model_definition_permissions_router.get(
    GATEWAY_MODEL_DEFINITION_USER_PERMISSIONS,
    response_model=List[UserPermission],
    summary="List users with permissions for a gateway model definition",
    description="Retrieves a list of users who have permissions for the specified gateway model definition.",
)
async def get_gateway_model_definition_users(
    name: str = Path(..., description="The gateway model definition name to get permissions for"),
    _: None = Depends(check_gateway_model_definition_manage_permission),
) -> List[UserPermission]:
    list_users = store.list_users(all=True)

    users: List[UserPermission] = []
    for user in list_users:
        user_defs = {}
        if hasattr(user, "gateway_model_definition_permissions") and user.gateway_model_definition_permissions:
            user_defs = {g.model_definition_id: g.permission for g in user.gateway_model_definition_permissions}

        if name in user_defs:
            users.append(
                UserPermission(
                    name=user.username,
                    permission=user_defs[name],
                    kind="service-account" if user.is_service_account else "user",
                )
            )
    return users


@gateway_model_definition_permissions_router.get(
    GATEWAY_MODEL_DEFINITION_GROUP_PERMISSIONS,
    response_model=List[GroupPermissionEntry],
    summary="List groups with permissions for a gateway model definition",
    description="Retrieves a list of groups who have permissions for the specified gateway model definition.",
)
async def get_gateway_model_definition_groups(
    name: str = Path(..., description="The gateway model definition name to get permissions for"),
    _: None = Depends(check_gateway_model_definition_manage_permission),
) -> List[GroupPermissionEntry]:
    """List all groups with permissions for a specific gateway model definition."""
    try:
        groups = store.gateway_model_definition_group_repo.list_groups_for_model_definition(name)
        return [GroupPermissionEntry(name=group_name, permission=permission) for group_name, permission in groups]
    except Exception as e:
        logger.error(f"Error retrieving gateway model definition group permissions: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve gateway model definition group permissions")


@gateway_model_definition_permissions_router.get(
    LIST_MODEL_DEFINITIONS,
    response_model=List[Dict[str, Any]],
    summary="List all gateway model definitions",
    description="Retrieves a list of all gateway model definitions from MLflow.",
)
async def list_gateway_model_definitions(username: str = Depends(get_username), is_admin: bool = Depends(get_is_admin)) -> JSONResponse:
    """
    List gateway model definitions accessible to the authenticated user.

    This endpoint returns gateway model definitions from MLflow's AI Gateway based on user permissions:
    - Administrators can see all gateway model definitions
    - Regular users only see gateway model definitions they can manage

    Parameters:
    -----------
    username : str
        The authenticated username (injected by dependency).
    is_admin : bool
        Whether the user has admin privileges (injected by dependency).

    Returns:
    --------
    JSONResponse
        A JSON response containing the list of accessible gateway model definitions.

    Raises:
    -------
    HTTPException
        If there is an error retrieving the model definitions.
    """
    try:
        # Fetch all gateway model definitions from MLflow's tracking store
        all_models = fetch_all_gateway_model_definitions()

        if is_admin:
            # Admins can see all model definitions
            models = all_models
        else:
            # Regular users only see model definitions they can manage
            models = filter_manageable_gateway_model_definitions(username, all_models)

        # Format the response to match the expected frontend schema
        return JSONResponse(
            content=[
                {
                    "name": model.get("name", ""),
                    "source": model.get("source") or model.get("provider", ""),
                }
                for model in models
            ]
        )
    except Exception as e:
        logger.error(f"Error listing gateway model definitions: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve gateway model definitions")
