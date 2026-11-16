"""Permission API for MLflow's skill registry (MLflow 3.18+).

MLflow keeps skills unique per ``(workspace, organization, name)``, so every grant here is read and
written in the request's workspace (``X-MLFLOW-WORKSPACE``, else the default workspace) — the same
workspace MLflow serves the registry from. A skill is named by its key (``utils/skill_key.py``):
``<name>``, or ``@<organization>/<name>``. A key no skill could have is refused with 400.

Three routers, all gated with dependencies from ``dependencies.py``:

* ``/api/2.0/mlflow/permissions/skills`` — the skills the caller may manage, and the users
  and groups holding a grant on one skill;
* ``/api/2.0/mlflow/permissions/users/{username}/skills[/{name}]`` — a user's grants;
* ``/api/2.0/mlflow/permissions/groups/{group_name}/skills[/{name}]`` — a group's grants.

Changing a grant needs MANAGE on the skill (or admin), as for registered models and experiments:
the creator of a skill holds MANAGE and may share it.
"""

from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from fastapi.responses import JSONResponse

from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.dependencies import check_skill_manage_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import GatewayPermission, NamedPermissionSummary, StatusMessageResponse, UserPermission
from mlflow_oidc_auth.models.responses import SkillListItem
from mlflow_oidc_auth.models.group import GroupNamedPermissionItem, GroupPermissionEntry
from mlflow_oidc_auth.permissions import NO_PERMISSIONS
from mlflow_oidc_auth.routers._errors import mlflow_error_status
from mlflow_oidc_auth.routers._group_route import GroupNameRoute
from mlflow_oidc_auth.routers._prefix import GROUP_PERMISSIONS_ROUTER_PREFIX, SKILL_PERMISSIONS_ROUTER_PREFIX, USER_PERMISSIONS_ROUTER_PREFIX
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import get_is_admin, get_username
from mlflow_oidc_auth.utils.data_fetching import fetch_all_skills
from mlflow_oidc_auth.utils.pagination import NO_PAGE, PageQuery, paginate_with_headers
from mlflow_oidc_auth.utils.permissions import can_manage_skill, effective_skill_permission

logger = get_logger()

_RESPONSES = {
    403: {"description": "Forbidden - Insufficient permissions"},
    404: {"description": "Resource not found"},
}

skill_permissions_router = APIRouter(prefix=SKILL_PERMISSIONS_ROUTER_PREFIX, tags=["skill permissions"], responses=_RESPONSES)
user_skill_permissions_router = APIRouter(prefix=USER_PERMISSIONS_ROUTER_PREFIX, tags=["user skill permissions"], responses=_RESPONSES)
group_skill_permissions_router = APIRouter(
    prefix=GROUP_PERMISSIONS_ROUTER_PREFIX, tags=["group skill permissions"], responses=_RESPONSES, route_class=GroupNameRoute
)

LIST_SKILLS = ""
SKILL_USER_PERMISSIONS = "/{name:path}/users"
SKILL_GROUP_PERMISSIONS = "/{name:path}/groups"
USER_SKILL_PERMISSIONS = "/{username}/skills"
USER_SKILL_PERMISSION_DETAIL = "/{username}/skills/{name:path}"
GROUP_SKILL_PERMISSIONS = "/{group_name}/skills"
GROUP_SKILL_PERMISSION_DETAIL = "/{group_name}/skills/{name:path}"


_ERROR_DETAIL = {409: "Permission already exists", 404: "Not found", 400: "Invalid permission"}


def _http_error(e: Exception, action: str) -> HTTPException:
    """Map a store error to an HTTP error without echoing internals."""
    status = mlflow_error_status(e)
    if status is not None:
        return HTTPException(status_code=status, detail=_ERROR_DETAIL[status])
    logger.error("Skill permission API: failed to %s: %s", action, type(e).__name__)
    return HTTPException(status_code=500, detail=f"Failed to {action}")


# ----------------------------------------------------------------------------------------
# Per skill
# ----------------------------------------------------------------------------------------


@skill_permissions_router.get(
    LIST_SKILLS,
    response_model=List[SkillListItem],
    summary="List skills the caller may manage",
    description="Skills of the request's workspace: all of them for an admin, otherwise those the caller can MANAGE.",
)
async def list_skills(username: str = Depends(get_username), is_admin: bool = Depends(get_is_admin), page: PageQuery = NO_PAGE) -> JSONResponse:
    try:
        skills = fetch_all_skills()
        if not is_admin:
            skills = [s for s in skills if can_manage_skill(s["name"], username)]
    except Exception as e:
        raise _http_error(e, "retrieve skills")
    # Paginate strictly after the permission filter: the total never counts a hidden skill.
    skills, headers = paginate_with_headers(skills, key=lambda s: s.get("name", ""), params=page)
    return JSONResponse(headers=headers, content=skills)


@skill_permissions_router.get(
    SKILL_USER_PERMISSIONS,
    response_model=List[UserPermission],
    summary="List users with a grant on a skill",
)
async def get_skill_users(
    name: str = Path(..., description="Skill key: <name> or @<organization>/<name>"),
    _: str = Depends(check_skill_manage_permission),
) -> List[UserPermission]:
    try:
        rows = store.list_skill_users(name)
    except Exception as e:
        raise _http_error(e, "retrieve skill user permissions")
    return [UserPermission(name=u, permission=p, kind="service-account" if is_sa else "user") for u, p, is_sa in rows]


@skill_permissions_router.get(
    SKILL_GROUP_PERMISSIONS,
    response_model=List[GroupPermissionEntry],
    summary="List groups with a grant on a skill",
)
async def get_skill_groups(
    name: str = Path(..., description="Skill key: <name> or @<organization>/<name>"),
    _: str = Depends(check_skill_manage_permission),
) -> List[GroupPermissionEntry]:
    try:
        rows = store.list_skill_groups(name)
    except Exception as e:
        raise _http_error(e, "retrieve skill group permissions")
    return [GroupPermissionEntry(name=g, permission=p) for g, p in rows]


# ----------------------------------------------------------------------------------------
# Per user
# ----------------------------------------------------------------------------------------


@user_skill_permissions_router.get(
    USER_SKILL_PERMISSIONS,
    response_model=List[NamedPermissionSummary],
    summary="List a user's skill permissions",
    description="Effective permissions of a user on the skills of the request's workspace.",
)
async def get_user_skill_permissions(
    username: str = Path(..., description="The user"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[NamedPermissionSummary]:
    """Admins see every skill; the user themselves those they can reach; others only skills they MANAGE."""
    try:
        results: List[NamedPermissionSummary] = []
        for skill in fetch_all_skills():
            name = skill.get("name")
            if not name:
                continue
            if not is_admin and current_username != username and not can_manage_skill(name, current_username):
                continue
            result = effective_skill_permission(name, username)
            if not is_admin and current_username == username and result.permission.name == NO_PERMISSIONS.name:
                continue
            results.append(NamedPermissionSummary(name=name, permission=result.permission.name, kind=result.kind))
        return results
    except Exception as e:
        raise _http_error(e, "retrieve skill permissions")


@user_skill_permissions_router.post(
    USER_SKILL_PERMISSION_DETAIL,
    status_code=201,
    response_model=NamedPermissionSummary,
    summary="Grant a user a permission on a skill",
)
async def create_user_skill_permission(
    username: str = Path(..., description="The user to grant"),
    name: str = Path(..., description="Skill key: <name> or @<organization>/<name>"),
    permission_data: GatewayPermission = Body(...),
    actor: str = Depends(check_skill_manage_permission),
) -> NamedPermissionSummary:
    try:
        perm = store.create_skill_permission(name, username, permission_data.permission)
    except Exception as e:
        raise _http_error(e, "create skill permission")
    emit_audit_event(
        "permission.create",
        actor=actor,
        resource_type="skill_permission",
        resource_id=name,
        detail={"username": username, "permission": permission_data.permission},
    )
    return NamedPermissionSummary(name=perm.name, permission=perm.permission, kind="user")


@user_skill_permissions_router.get(
    USER_SKILL_PERMISSION_DETAIL,
    response_model=NamedPermissionSummary,
    summary="Get a user's grant on a skill",
)
async def get_user_skill_permission(
    username: str = Path(..., description="The user"),
    name: str = Path(..., description="Skill key: <name> or @<organization>/<name>"),
    _: str = Depends(check_skill_manage_permission),
) -> NamedPermissionSummary:
    try:
        perm = store.get_skill_permission(name, username)
    except Exception as e:
        raise _http_error(e, "retrieve skill permission")
    return NamedPermissionSummary(name=perm.name, permission=perm.permission, kind="user")


@user_skill_permissions_router.patch(
    USER_SKILL_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Change a user's grant on a skill",
)
async def update_user_skill_permission(
    username: str = Path(..., description="The user"),
    name: str = Path(..., description="Skill key: <name> or @<organization>/<name>"),
    permission_data: GatewayPermission = Body(...),
    actor: str = Depends(check_skill_manage_permission),
) -> StatusMessageResponse:
    try:
        store.update_skill_permission(name, username, permission_data.permission)
    except Exception as e:
        raise _http_error(e, "update skill permission")
    emit_audit_event(
        "permission.update",
        actor=actor,
        resource_type="skill_permission",
        resource_id=name,
        detail={"username": username, "permission": permission_data.permission},
    )
    return StatusMessageResponse(message=f"Skill permission updated for {username} on {name}")


@user_skill_permissions_router.delete(
    USER_SKILL_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Revoke a user's grant on a skill",
)
async def delete_user_skill_permission(
    username: str = Path(..., description="The user"),
    name: str = Path(..., description="Skill key: <name> or @<organization>/<name>"),
    actor: str = Depends(check_skill_manage_permission),
) -> StatusMessageResponse:
    try:
        store.delete_skill_permission(name, username)
    except Exception as e:
        raise _http_error(e, "delete skill permission")
    emit_audit_event("permission.delete", actor=actor, resource_type="skill_permission", resource_id=name, detail={"username": username})
    return StatusMessageResponse(message=f"Skill permission deleted for {username} on {name}")


# ----------------------------------------------------------------------------------------
# Per group
# ----------------------------------------------------------------------------------------


@group_skill_permissions_router.get(
    GROUP_SKILL_PERMISSIONS,
    response_model=List[GroupNamedPermissionItem],
    summary="List a group's skill grants",
    description="The group's grants in the request's workspace: all of them for an admin, otherwise those on skills the caller can MANAGE.",
)
async def get_group_skill_permissions(
    group_name: str = Path(..., description="The group"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[GroupNamedPermissionItem]:
    try:
        perms = store.list_group_skill_permissions(group_name)
        return [GroupNamedPermissionItem(name=p.name, permission=p.permission) for p in perms if is_admin or can_manage_skill(p.name, current_username)]
    except Exception as e:
        raise _http_error(e, "retrieve group skill permissions")


@group_skill_permissions_router.post(
    GROUP_SKILL_PERMISSION_DETAIL,
    status_code=201,
    response_model=GroupNamedPermissionItem,
    summary="Grant a group a permission on a skill",
)
async def create_group_skill_permission(
    group_name: str = Path(..., description="The group to grant"),
    name: str = Path(..., description="Skill key: <name> or @<organization>/<name>"),
    permission_data: GatewayPermission = Body(...),
    actor: str = Depends(check_skill_manage_permission),
) -> GroupNamedPermissionItem:
    try:
        perm = store.create_group_skill_permission(group_name, name, permission_data.permission)
    except Exception as e:
        raise _http_error(e, "create group skill permission")
    emit_audit_event(
        "permission.create",
        actor=actor,
        resource_type="group_skill_permission",
        resource_id=name,
        detail={"group_name": group_name, "permission": permission_data.permission},
    )
    return GroupNamedPermissionItem(name=perm.name, permission=perm.permission)


@group_skill_permissions_router.get(
    GROUP_SKILL_PERMISSION_DETAIL,
    response_model=GroupNamedPermissionItem,
    summary="Get a group's grant on a skill",
)
async def get_group_skill_permission(
    group_name: str = Path(..., description="The group"),
    name: str = Path(..., description="Skill key: <name> or @<organization>/<name>"),
    _: str = Depends(check_skill_manage_permission),
) -> GroupNamedPermissionItem:
    try:
        perm = store.get_group_skill_permission(group_name, name)
    except Exception as e:
        raise _http_error(e, "retrieve group skill permission")
    return GroupNamedPermissionItem(name=perm.name, permission=perm.permission)


@group_skill_permissions_router.patch(
    GROUP_SKILL_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Change a group's grant on a skill",
)
async def update_group_skill_permission(
    group_name: str = Path(..., description="The group"),
    name: str = Path(..., description="Skill key: <name> or @<organization>/<name>"),
    permission_data: GatewayPermission = Body(...),
    actor: str = Depends(check_skill_manage_permission),
) -> StatusMessageResponse:
    try:
        store.update_group_skill_permission(group_name, name, permission_data.permission)
    except Exception as e:
        raise _http_error(e, "update group skill permission")
    emit_audit_event(
        "permission.update",
        actor=actor,
        resource_type="group_skill_permission",
        resource_id=name,
        detail={"group_name": group_name, "permission": permission_data.permission},
    )
    return StatusMessageResponse(message=f"Skill permission updated for group {group_name} on {name}")


@group_skill_permissions_router.delete(
    GROUP_SKILL_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Revoke a group's grant on a skill",
)
async def delete_group_skill_permission(
    group_name: str = Path(..., description="The group"),
    name: str = Path(..., description="Skill key: <name> or @<organization>/<name>"),
    actor: str = Depends(check_skill_manage_permission),
) -> StatusMessageResponse:
    try:
        store.delete_group_skill_permission(group_name, name)
    except Exception as e:
        raise _http_error(e, "delete group skill permission")
    emit_audit_event("permission.delete", actor=actor, resource_type="group_skill_permission", resource_id=name, detail={"group_name": group_name})
    return StatusMessageResponse(message=f"Skill permission deleted for group {group_name} on {name}")
