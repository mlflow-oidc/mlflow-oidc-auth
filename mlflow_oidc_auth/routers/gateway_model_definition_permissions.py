from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import JSONResponse

from mlflow_oidc_auth.dependencies import check_gateway_model_definition_manage_permission
from mlflow_oidc_auth.models.group import GroupPermissionEntry
from mlflow_oidc_auth.models.permission import UserPermission
from mlflow_oidc_auth.routers._prefix import GATEWAY_PERMISSIONS_ROUTER_PREFIX
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import get_is_admin, get_username

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
    list_groups = store.list_groups(all=True)

    groups: List[GroupPermissionEntry] = []
    for group in list_groups:
        group_defs = {}
        if hasattr(group, "gateway_model_definition_permissions") and group.gateway_model_definition_permissions:
            group_defs = {g.model_definition_id: g.permission for g in group.gateway_model_definition_permissions}

        if name in group_defs:
            groups.append(
                GroupPermissionEntry(
                    name=group.group_name,
                    permission=group_defs[name],
                )
            )
    return groups


@gateway_model_definition_permissions_router.get(
    LIST_MODEL_DEFINITIONS,
    response_model=List[str],
    summary="List all gateway model definitions with permissions",
    description="Retrieves a list of all gateway model definitions that have permissions assigned.",
)
async def list_gateway_model_definitions_with_permissions(username: str = Depends(get_username), is_admin: bool = Depends(get_is_admin)) -> JSONResponse:
    """
    List gateway model definitions accessible to the authenticated user.

    Admins can see all known model definitions (collected from stored user/group permissions).
    Regular users only see model definitions they can manage.
    """
    # Admin path: collect all model-def IDs from stored users/groups
    if is_admin:
        all_users = store.list_users(all=True)
        def_names = set()
        for user in all_users:
            if hasattr(user, "gateway_model_definition_permissions") and user.gateway_model_definition_permissions:
                def_names.update({p.model_definition_id for p in user.gateway_model_definition_permissions})
        return JSONResponse(content=sorted(list(def_names)))

    # Non-admin path: gather known definitions and filter by manage capability
    all_defs = set()
    all_users = store.list_users(all=True)
    for user in all_users:
        if hasattr(user, "gateway_model_definition_permissions") and user.gateway_model_definition_permissions:
            all_defs.update({p.model_definition_id for p in user.gateway_model_definition_permissions})
    all_groups = store.list_groups(all=True)
    for group in all_groups:
        if hasattr(group, "gateway_model_definition_permissions") and group.gateway_model_definition_permissions:
            all_defs.update({p.model_definition_id for p in group.gateway_model_definition_permissions})

    from mlflow_oidc_auth.utils.permissions import can_manage_gateway_model_definition

    manageable = []
    for md in sorted(all_defs):
        try:
            if can_manage_gateway_model_definition(md, username):
                manageable.append(md)
        except Exception:
            continue

    return JSONResponse(content=manageable)
