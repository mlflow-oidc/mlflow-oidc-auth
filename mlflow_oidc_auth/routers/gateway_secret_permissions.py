from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import JSONResponse

from mlflow_oidc_auth.dependencies import check_gateway_secret_manage_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models.group import GroupPermissionEntry
from mlflow_oidc_auth.models.permission import UserPermission
from mlflow_oidc_auth.routers._prefix import GATEWAY_PERMISSIONS_ROUTER_PREFIX
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import fetch_all_gateway_secrets, get_is_admin, get_username
from mlflow_oidc_auth.utils.batch_permissions import filter_manageable_gateway_secrets

logger = get_logger()

gateway_secret_permissions_router = APIRouter(
    prefix=f"{GATEWAY_PERMISSIONS_ROUTER_PREFIX}/secrets",
    tags=["gateway secret permissions"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)


LIST_SECRETS = ""

GATEWAY_SECRET_USER_PERMISSIONS = "/{name:path}/users"
GATEWAY_SECRET_GROUP_PERMISSIONS = "/{name:path}/groups"


@gateway_secret_permissions_router.get(
    GATEWAY_SECRET_USER_PERMISSIONS,
    response_model=List[UserPermission],
    summary="List users with permissions for a gateway secret",
    description="Retrieves a list of users who have permissions for the specified gateway secret.",
)
async def get_gateway_secret_users(
    name: str = Path(..., description="The gateway secret name to get permissions for"),
    _: None = Depends(check_gateway_secret_manage_permission),
) -> List[UserPermission]:
    list_users = store.list_users(all=True)

    users: List[UserPermission] = []
    for user in list_users:
        user_secrets = {}
        if hasattr(user, "gateway_secret_permissions") and user.gateway_secret_permissions:
            user_secrets = {g.secret_id: g.permission for g in user.gateway_secret_permissions}

        if name in user_secrets:
            users.append(
                UserPermission(
                    name=user.username,
                    permission=user_secrets[name],
                    kind="service-account" if user.is_service_account else "user",
                )
            )
    return users


@gateway_secret_permissions_router.get(
    GATEWAY_SECRET_GROUP_PERMISSIONS,
    response_model=List[GroupPermissionEntry],
    summary="List groups with permissions for a gateway secret",
    description="Retrieves a list of groups who have permissions for the specified gateway secret.",
)
async def get_gateway_secret_groups(
    name: str = Path(..., description="The gateway secret name to get permissions for"),
    _: None = Depends(check_gateway_secret_manage_permission),
) -> List[GroupPermissionEntry]:
    """List all groups with permissions for a specific gateway secret."""
    try:
        groups = store.gateway_secret_group_repo.list_groups_for_secret(name)
        return [GroupPermissionEntry(name=group_name, permission=permission) for group_name, permission in groups]
    except Exception as e:
        logger.error(f"Error retrieving gateway secret group permissions: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve gateway secret group permissions")


@gateway_secret_permissions_router.get(
    LIST_SECRETS,
    response_model=List[Dict[str, Any]],
    summary="List all gateway secrets",
    description="Retrieves a list of all gateway secrets from MLflow.",
)
async def list_gateway_secrets(username: str = Depends(get_username), is_admin: bool = Depends(get_is_admin)) -> JSONResponse:
    """
    List gateway secrets accessible to the authenticated user.

    This endpoint returns gateway secrets from MLflow's AI Gateway based on user permissions:
    - Administrators can see all gateway secrets
    - Regular users only see gateway secrets they can manage

    Parameters:
    -----------
    username : str
        The authenticated username (injected by dependency).
    is_admin : bool
        Whether the user has admin privileges (injected by dependency).

    Returns:
    --------
    JSONResponse
        A JSON response containing the list of accessible gateway secrets.

    Raises:
    -------
    HTTPException
        If there is an error retrieving the secrets.
    """
    try:
        # Fetch all gateway secrets from MLflow's tracking store
        all_secrets = fetch_all_gateway_secrets()

        if is_admin:
            # Admins can see all secrets
            secrets = all_secrets
        else:
            # Regular users only see secrets they can manage
            secrets = filter_manageable_gateway_secrets(username, all_secrets)

        # Format the response to match the expected frontend schema
        return JSONResponse(
            content=[
                {
                    "key": secret.get("secret_name") or secret.get("name") or secret.get("key", ""),
                }
                for secret in secrets
            ]
        )
    except Exception as e:
        logger.error(f"Error listing gateway secrets: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve gateway secrets")
