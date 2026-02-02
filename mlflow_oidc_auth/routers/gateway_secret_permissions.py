from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import JSONResponse

from mlflow_oidc_auth.dependencies import check_gateway_secret_manage_permission
from mlflow_oidc_auth.models.group import GroupPermissionEntry
from mlflow_oidc_auth.models.permission import UserPermission
from mlflow_oidc_auth.routers._prefix import GATEWAY_PERMISSIONS_ROUTER_PREFIX
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import get_is_admin, get_username

gateway_secret_permissions_router = APIRouter(
    prefix=f"{GATEWAY_PERMISSIONS_ROUTER_PREFIX}/secrets",
    tags=["gateway secret permissions"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)


LIST_SECRETS = ""

GATEWAY_SECRET_USER_PERMISSIONS = "/{name}/users"
GATEWAY_SECRET_GROUP_PERMISSIONS = "/{name}/groups"


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
    list_groups = store.list_groups(all=True)

    groups: List[GroupPermissionEntry] = []
    for group in list_groups:
        group_secrets = {}
        if hasattr(group, "gateway_secret_permissions") and group.gateway_secret_permissions:
            group_secrets = {g.secret_id: g.permission for g in group.gateway_secret_permissions}

        if name in group_secrets:
            groups.append(
                GroupPermissionEntry(
                    name=group.group_name,
                    permission=group_secrets[name],
                )
            )
    return groups


@gateway_secret_permissions_router.get(
    LIST_SECRETS,
    response_model=List[str],
    summary="List all gateway secrets with permissions",
    description="Retrieves a list of all gateway secrets that have permissions assigned.",
)
async def list_gateway_secrets_with_permissions(username: str = Depends(get_username), is_admin: bool = Depends(get_is_admin)) -> JSONResponse:
    """
    List gateway secrets accessible to the authenticated user.

    Admins can see all known secrets (collected from stored user/group permissions).
    Regular users only see secrets they can manage.
    """
    # Admin path: collect all secret IDs from stored users/groups
    if is_admin:
        all_users = store.list_users(all=True)
        secret_names = set()
        for user in all_users:
            if hasattr(user, "gateway_secret_permissions") and user.gateway_secret_permissions:
                secret_names.update({p.secret_id for p in user.gateway_secret_permissions})
        return JSONResponse(content=sorted(list(secret_names)))

    # Non-admin path: gather known secrets and filter by manage capability
    all_secrets = set()
    all_users = store.list_users(all=True)
    for user in all_users:
        if hasattr(user, "gateway_secret_permissions") and user.gateway_secret_permissions:
            all_secrets.update({p.secret_id for p in user.gateway_secret_permissions})
    all_groups = store.list_groups(all=True)
    for group in all_groups:
        if hasattr(group, "gateway_secret_permissions") and group.gateway_secret_permissions:
            all_secrets.update({p.secret_id for p in group.gateway_secret_permissions})

    from mlflow_oidc_auth.utils.permissions import can_manage_gateway

    manageable = []
    for secret in sorted(all_secrets):
        try:
            if can_manage_gateway(secret, username):
                manageable.append(secret)
        except Exception:
            continue

    return JSONResponse(content=manageable)
