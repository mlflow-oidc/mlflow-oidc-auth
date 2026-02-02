from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import JSONResponse

from mlflow_oidc_auth.dependencies import check_gateway_endpoint_manage_permission
from mlflow_oidc_auth.models.group import GroupPermissionEntry
from mlflow_oidc_auth.models.permission import UserPermission
from mlflow_oidc_auth.routers._prefix import GATEWAY_PERMISSIONS_ROUTER_PREFIX
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import get_is_admin, get_username

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


gateway_endpoint_permissions_router.get(
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


gateway_endpoint_permissions_router.get(
    GATEWAY_ENDPOINT_GROUP_PERMISSIONS,
    response_model=List[GroupPermissionEntry],
    summary="List groups with permissions for a gateway endpoint",
    description="Retrieves a list of groups who have permissions for the specified gateway endpoint.",
)


async def get_gateway_endpoint_groups(
    name: str = Path(..., description="The gateway endpoint name to get permissions for"),
    _: None = Depends(check_gateway_endpoint_manage_permission),
) -> List[GroupPermissionEntry]:
    list_groups = store.list_groups(all=True)

    groups: List[GroupPermissionEntry] = []
    for group in list_groups:
        group_gateways = {}
        if hasattr(group, "gateway_endpoint_permissions") and group.gateway_endpoint_permissions:
            group_gateways = {g.endpoint_id: g.permission for g in group.gateway_endpoint_permissions}

        if name in group_gateways:
            groups.append(
                GroupPermissionEntry(
                    name=group.group_name,
                    permission=group_gateways[name],
                )
            )
    return groups


gateway_endpoint_permissions_router.get(
    LIST_ENDPOINTS,
    response_model=List[str],
    summary="List all gateway endpoints with permissions",
    description="Retrieves a list of all gateway endpoints that have permissions assigned.",
)


async def list_gateway_endpoints_with_permissions(username: str = Depends(get_username), is_admin: bool = Depends(get_is_admin)) -> JSONResponse:
    """
    List gateway endpoints accessible to the authenticated user.

    This endpoint returns gateway endpoints based on user permissions:
    - Administrators can see all gateway endpoints
    - Regular users only see gateway endpoints they can manage

    For admins we aggregate all known endpoint IDs from stored user/group permissions.
    For regular users we return only endpoints the user has explicit permissions for.
    """
    # Admin path: collect all endpoint IDs from stored users/groups
    if is_admin:
        all_users = store.list_users(all=True)
        endpoint_names = set()
        for user in all_users:
            if hasattr(user, "gateway_endpoint_permissions") and user.gateway_endpoint_permissions:
                endpoint_names.update({p.endpoint_id for p in user.gateway_endpoint_permissions})
        return JSONResponse(content=sorted(list(endpoint_names)))

    # Non-admin path: return only endpoints the user can manage.
    # Build a set of known endpoints from stored user and group permissions, then filter
    # by effective manage permission using the existing permission resolver.
    all_endpoints = set()
    # Gather endpoints from users
    all_users = store.list_users(all=True)
    for user in all_users:
        if hasattr(user, "gateway_endpoint_permissions") and user.gateway_endpoint_permissions:
            all_endpoints.update({p.endpoint_id for p in user.gateway_endpoint_permissions})
    # Gather endpoints from groups
    all_groups = store.list_groups(all=True)
    for group in all_groups:
        if hasattr(group, "gateway_endpoint_permissions") and group.gateway_endpoint_permissions:
            all_endpoints.update({p.endpoint_id for p in group.gateway_endpoint_permissions})

    from mlflow_oidc_auth.utils.permissions import can_manage_gateway

    manageable = []
    for endpoint in sorted(all_endpoints):
        try:
            if can_manage_gateway(endpoint, username):
                manageable.append(endpoint)
        except Exception:
            # Treat errors (missing resource etc.) as not manageable
            continue

    return JSONResponse(content=manageable)
