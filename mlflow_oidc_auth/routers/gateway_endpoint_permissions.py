from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import JSONResponse

from mlflow_oidc_auth.dependencies import check_gateway_endpoint_manage_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models.group import GroupPermissionEntry
from mlflow_oidc_auth.models.permission import UserPermission
from mlflow_oidc_auth.routers._prefix import GATEWAY_PERMISSIONS_ROUTER_PREFIX
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import fetch_all_gateway_endpoints, get_is_admin, get_username
from mlflow_oidc_auth.utils.batch_permissions import filter_manageable_gateway_endpoints

logger = get_logger()

gateway_endpoint_permissions_router = APIRouter(
    prefix=f"{GATEWAY_PERMISSIONS_ROUTER_PREFIX}/endpoints",
    tags=["gateway endpoint permissions"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)


LIST_ENDPOINTS = ""

GATEWAY_ENDPOINT_USER_PERMISSIONS = "/{name}/users"
GATEWAY_ENDPOINT_GROUP_PERMISSIONS = "/{name}/groups"


@gateway_endpoint_permissions_router.get(
    GATEWAY_ENDPOINT_USER_PERMISSIONS,
    response_model=List[UserPermission],
    summary="List users with permissions for a gateway endpoint",
    description="Retrieves a list of users who have permissions for the specified gateway endpoint.",
)
async def get_gateway_endpoint_users(
    name: str = Path(..., description="The gateway endpoint name to get permissions for"),
    _: None = Depends(check_gateway_endpoint_manage_permission),
) -> List[UserPermission]:
    list_users = store.list_users(all=True)

    users: List[UserPermission] = []
    for user in list_users:
        user_gateways = {}
        if hasattr(user, "gateway_endpoint_permissions") and user.gateway_endpoint_permissions:
            # Permission objects use `endpoint_id`
            user_gateways = {g.endpoint_id: g.permission for g in user.gateway_endpoint_permissions}

        if name in user_gateways:
            users.append(
                UserPermission(
                    name=user.username,
                    permission=user_gateways[name],
                    kind="service-account" if user.is_service_account else "user",
                )
            )
    return users


@gateway_endpoint_permissions_router.get(
    GATEWAY_ENDPOINT_GROUP_PERMISSIONS,
    response_model=List[GroupPermissionEntry],
    summary="List groups with permissions for a gateway endpoint",
    description="Retrieves a list of groups who have permissions for the specified gateway endpoint.",
)
async def get_gateway_endpoint_groups(
    name: str = Path(..., description="The gateway endpoint name to get permissions for"),
    _: None = Depends(check_gateway_endpoint_manage_permission),
) -> List[GroupPermissionEntry]:
    """List all groups with permissions for a specific gateway endpoint."""
    try:
        groups = store.gateway_endpoint_group_repo.list_groups_for_endpoint(name)
        return [GroupPermissionEntry(name=group_name, permission=permission) for group_name, permission in groups]
    except Exception as e:
        logger.error(f"Error retrieving gateway endpoint group permissions: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve gateway endpoint group permissions")


@gateway_endpoint_permissions_router.get(
    LIST_ENDPOINTS,
    response_model=List[Dict[str, Any]],
    summary="List all gateway endpoints",
    description="Retrieves a list of all gateway endpoints from MLflow.",
)
async def list_gateway_endpoints(username: str = Depends(get_username), is_admin: bool = Depends(get_is_admin)) -> JSONResponse:
    """
    List gateway endpoints accessible to the authenticated user.

    This endpoint returns gateway endpoints from MLflow's AI Gateway based on user permissions:
    - Administrators can see all gateway endpoints
    - Regular users only see gateway endpoints they can manage

    The response includes endpoint metadata like name and type from MLflow's gateway store.

    Parameters:
    -----------
    username : str
        The authenticated username (injected by dependency).
    is_admin : bool
        Whether the user has admin privileges (injected by dependency).

    Returns:
    --------
    JSONResponse
        A JSON response containing the list of accessible gateway endpoints.

    Raises:
    -------
    HTTPException
        If there is an error retrieving the endpoints.
    """
    try:
        # Fetch all gateway endpoints from MLflow's tracking store
        all_endpoints = fetch_all_gateway_endpoints()

        if is_admin:
            # Admins can see all endpoints
            endpoints = all_endpoints
        else:
            # Regular users only see endpoints they can manage
            endpoints = filter_manageable_gateway_endpoints(username, all_endpoints)

        # Format the response to match the expected frontend schema
        return JSONResponse(
            content=[
                {
                    "name": endpoint.get("name", ""),
                    "type": endpoint.get("endpoint_type", ""),
                    "description": endpoint.get("description", ""),
                    "route_type": endpoint.get("route_type", ""),
                    "auth_type": endpoint.get("auth_type", ""),
                }
                for endpoint in endpoints
            ]
        )
    except Exception as e:
        logger.error(f"Error listing gateway endpoints: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve gateway endpoints")
