"""Authorization for MLflow's skill registry (``mlflow.server.skill_registry_api``, MLflow 3.18+).

MLflow serves the registry from FastAPI under ``/api/3.0/mlflow/skills`` and
``/ajax-api/3.0/mlflow/skills`` (each behind ``--static-prefix`` when one is set), so it never
reaches the Flask hooks: ``fastapi_permission_middleware`` runs the validator built here before
MLflow's handler and :func:`finalize_skill_response` after it.

MLflow keeps skills unique per ``(workspace, organization, name)``. A grant names a skill by its
key, ``<name>`` or ``@<organization>/<name>`` (``utils/skill_key.py``); an organization name grants
nothing by itself. Permissions mirror MLflow's own auth plugin (``mlflow/server/auth``):

=============================================  ================================================
Route                                          Requires
=============================================  ================================================
``POST   /skills``                             create rights (:func:`can_create_skill`); the
                                               creator is granted ``MANAGE`` once MLflow succeeds
``GET    /skills``                             authentication; MLflow is handed the identities the
                                               caller may read *before* it paginates
``GET    /skills/<skill>[/...]``               ``READ`` on the skill
``POST|PATCH /skills/<skill>[/...]``           ``EDIT`` on the skill (tags, aliases, description,
                                               version status)
``DELETE /skills/<skill>/tags/<key>``          ``EDIT`` on the skill
``POST   /skills/<skill>/versions``            ``EDIT`` on the skill; on a skill that does not
``POST   /skills/bulk-register``               exist yet (MLflow creates it) create rights, and
                                               the creator is granted ``MANAGE``
``DELETE /skills/<skill>[/...]`` (the rest)    ``MANAGE`` on the skill; deleting the skill also
``PATCH  .../versions/<v>`` to ``deleted``     deletes its grants in the request's workspace
=============================================  ================================================

``<skill>`` is ``<name>`` or ``@<organization>/<name>``.

The permission on a skill is the caller's user grant, then group grants, then their permission on
the request's workspace, or ``DEFAULT_MLFLOW_PERMISSION`` with workspaces disabled (see
``effective_skill_permission``). Admins never reach the validator: the middleware lets them
through first.

Requests are resolved against MLflow's own router (same routes, same order, the first full match),
so the skill judged here is the skill MLflow's handler will act on. A request that resolves to no
registry route, to a route this module does not know, or to an identity MLflow could never have
stored, is denied.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Match

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.middleware.registry_support import bridged_auth_context, buffer_body, can_create_in_request_workspace, rebuilt_response
from mlflow_oidc_auth.utils.skill_key import format_skill_key, parse_skill_key, validate_skill_identity

logger = get_logger()

#: The bare mount points; MLflow also mounts both behind ``--static-prefix`` (see :func:`skill_route_prefixes`).
SKILL_PREFIXES = ("/api/3.0/mlflow/skills", "/ajax-api/3.0/mlflow/skills")

# What a registry route does.
SEARCH = "search"
CREATE = "create"
REGISTER = "register"
BULK_REGISTER = "bulk_register"
READ = "read"
UPDATE = "update"
UPDATE_VERSION = "update_version"
MANAGE = "manage"
DELETE_SKILL = "delete_skill"

# MLflow's handlers (``mlflow.server.skill_registry_api``) by function name. A handler missing
# here — one a later MLflow adds — resolves to no operation and is denied until it is mapped.
_ENDPOINT_OPERATIONS = {
    "search_skills": SEARCH,
    "create_skill": CREATE,
    "bulk_register_skills": BULK_REGISTER,
    "create_skill_version": REGISTER,
    "create_organization_skill_version": REGISTER,
    "get_skill": READ,
    "get_organization_skill": READ,
    "search_skill_versions": READ,
    "search_organization_skill_versions": READ,
    "get_skill_version": READ,
    "get_organization_skill_version": READ,
    "get_skill_version_by_alias": READ,
    "get_organization_skill_version_by_alias": READ,
    "update_skill": UPDATE,
    "update_organization_skill": UPDATE,
    "update_skill_version": UPDATE_VERSION,
    "update_organization_skill_version": UPDATE_VERSION,
    "set_skill_tag": UPDATE,
    "set_organization_skill_tag": UPDATE,
    "delete_skill_tag": UPDATE,
    "delete_organization_skill_tag": UPDATE,
    "set_skill_version_tag": UPDATE,
    "set_organization_skill_version_tag": UPDATE,
    "set_skill_alias": UPDATE,
    "set_organization_skill_alias": UPDATE,
    "delete_skill": DELETE_SKILL,
    "delete_organization_skill": DELETE_SKILL,
    "delete_skill_version": MANAGE,
    "delete_organization_skill_version": MANAGE,
    "delete_skill_version_tag": MANAGE,
    "delete_organization_skill_version_tag": MANAGE,
    "delete_skill_alias": MANAGE,
    "delete_organization_skill_alias": MANAGE,
}

# The statuses a version may be moved to with EDIT. Anything else a PATCH names — ``deleted``, or
# a status a later MLflow adds — needs MANAGE.
_EDIT_STATUSES = frozenset(("draft", "active", "deprecated"))

# A key no grant can be stored under (the permission API validates keys), so resolving it yields
# what the caller holds on a skill with no grant of its own.
_NO_GRANT_KEY = "*"

# MLflow's cap on one bulk registration (``_MAX_BULK_REGISTER_SKILLS``); a larger batch is refused
# here rather than authorized skill by skill only for MLflow to reject it.
_MAX_BULK_TARGETS = 500


@dataclass(frozen=True)
class SkillRoute:
    """A resolved registry request: what it does and, for per-skill routes, which skill."""

    operation: str
    organization: str = ""
    name: Optional[str] = None

    @property
    def key(self) -> Optional[str]:
        """The grant key of the skill the route names, or None for a route that names none."""
        return None if self.name is None else format_skill_key(self.organization, self.name)


def skill_route_prefixes() -> tuple[str, ...]:
    """Every prefix the registry may be served under: the bare paths and the static-prefixed ones.

    MLflow mounts the registry at ``get_skill_registry_api_route_prefixes()``, which puts its static
    prefix in front of both paths. On an MLflow without the registry the static prefix is applied
    here the same way, so the match never depends on the installed version.
    """
    prefixes = list(SKILL_PREFIXES)
    try:
        from mlflow.server.skill_registry_api import get_skill_registry_api_route_prefixes

        prefixes.extend(get_skill_registry_api_route_prefixes())
    except ImportError:
        try:
            from mlflow.server.handlers import _add_static_prefix

            prefixes.extend(_add_static_prefix(p) for p in SKILL_PREFIXES)
        except Exception:
            logger.debug("Could not apply MLflow's static prefix to the skill registry paths")
    # Longest first, so a static-prefixed mount is never mistaken for a bare one.
    return tuple(sorted(set(prefixes), key=len, reverse=True))


def is_skill_registry_path(path: str) -> bool:
    """Whether ``path`` is on the skill registry, with or without MLflow's static prefix.

    Deliberately wide: anything starting with a registry prefix is routed to the registry validator,
    which denies whatever it cannot resolve to one of MLflow's routes.
    """
    return path.startswith(skill_route_prefixes())


def _registry_routes() -> tuple:
    """MLflow's skill registry routes in registration order; empty on an MLflow without the registry."""
    try:
        from mlflow.server.skill_registry_api import skill_registry_router
    except ImportError:
        return ()
    return tuple(skill_registry_router.routes)


def resolve_skill_route(path: str, method: str) -> Optional[SkillRoute]:
    """The registry route MLflow will serve ``method path`` with, or None if it serves none.

    Matched against MLflow's own router, so the first route whose path and method match is the one
    its dispatcher picks. Resolves to None as well: a route whose handler this module does not map,
    and a per-skill route whose organization or name MLflow's validators reject.

    Parameters:
        path: The routed request path, static prefix included.
        method: The HTTP method.

    Returns:
        The resolved route, or None.
    """
    for prefix in skill_route_prefixes():
        if path == prefix or path.startswith(prefix + "/"):
            suffix = path[len(prefix) :]
            break
    else:
        return None
    scope = {"type": "http", "path": suffix, "method": method.upper(), "root_path": ""}
    for route in _registry_routes():
        match, child_scope = route.matches(scope)
        if match is not Match.FULL:
            continue
        operation = _ENDPOINT_OPERATIONS.get(getattr(getattr(route, "endpoint", None), "__name__", ""))
        if operation is None:
            logger.warning("Skill registry: denying a route with no authorization rule")
            return None
        params = child_scope.get("path_params", {})
        name = params.get("name")
        if name is None:
            return SkillRoute(operation)
        organization = params.get("organization", "")
        try:
            validate_skill_identity(organization, name)
        except ValueError:
            return None
        return SkillRoute(operation, organization, name)
    return None


def can_create_skill(username: str) -> bool:
    """Whether ``username`` may create a skill in the request's workspace.

    With workspaces enabled: ``MANAGE`` on the workspace MLflow serves the request from, subject to
    ``OIDC_WORKSPACE_REQUIRE_CREATION_CONTEXT`` and ``OIDC_WORKSPACE_DENY_DEFAULT_CREATION`` — the
    same threshold as creating experiments, models, gateway resources and MCP servers.

    With workspaces disabled: any authenticated user, as for registered models and prompts — unless
    ``RESTRICT_RESOURCE_CREATION`` is set. That flag admits creations through pattern grants, which
    skills do not have, so with it set only administrators create skills.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return not config.RESTRICT_RESOURCE_CREATION
    return can_create_in_request_workspace(username)


def _can_create_named(key: str, username: str) -> bool:
    """Create rights, unless a grant already stored under ``key`` keeps ``username`` from changing it.

    A grant can outlive its skill (or be written ahead of it). One that does not let the caller
    edit — ``READ``, or ``NO_PERMISSIONS`` to shut them out — must not be overridden by creating
    the skill and collecting the creator's ``MANAGE``.
    """
    from mlflow_oidc_auth.utils.permissions import effective_skill_permission

    result = effective_skill_permission(key, username)
    if result.kind in ("user", "group") and not result.permission.can_update:
        return False
    return can_create_skill(username)


def _skill_exists(organization: str, name: str) -> bool:
    """Whether the request's workspace holds the skill.

    Raises:
        Exception: Any lookup failure other than "does not exist" — the caller denies.
    """
    from mlflow.exceptions import MlflowException
    from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode
    from mlflow.server.handlers import _get_tracking_store

    try:
        _get_tracking_store().get_skill(name=name, organization=organization)
        return True
    except MlflowException as e:
        if e.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
            return False
        raise


def skill_search_scope(username: str) -> tuple[Optional[list[tuple[str, str]]], list[tuple[str, str]]]:
    """The identities MLflow's search may return to ``username``: ``(include, exclude)``.

    MLflow applies both before it paginates, so neither a page nor its token tells anything about a
    skill the caller may not read. ``include`` is None when the caller reads every skill without a
    grant of its own (their workspace permission, or the global default with workspaces disabled),
    and ``exclude`` then lists the skills a grant shuts them out of. Otherwise ``include`` lists the
    skills a grant lets them read and nothing else is returned.

    Parameters:
        username: The caller.

    Returns:
        ``(include, exclude)`` as ``(organization, name)`` pairs, as ``search_skills`` takes them.
    """
    from mlflow_oidc_auth.store import store
    from mlflow_oidc_auth.utils.permissions import SKILL, effective_skill_permission

    baseline_read = effective_skill_permission(_NO_GRANT_KEY, username).permission.can_read
    keys = {grant.name for grant in store.list_user_grants(SKILL, username)} | {grant.name for grant in store.list_user_groups_grants(SKILL, username)}
    exceptions: set[tuple[str, str]] = set()
    for key in keys:
        try:
            identity = parse_skill_key(key)
        except ValueError:
            # No skill MLflow can store answers to this key, so there is nothing to include or exclude.
            continue
        if effective_skill_permission(key, username).permission.can_read != baseline_read:
            exceptions.add(identity)
    ordered = sorted(exceptions)
    return (None, ordered) if baseline_read else (ordered, [])


async def _json_object(request: Request) -> Optional[dict[str, Any]]:
    """The request's JSON object body, or None when it is not one."""
    try:
        body = await request.json()
    except Exception:
        return None
    return body if isinstance(body, dict) else None


async def _registration_targets(route: SkillRoute, request: Request) -> Optional[list[tuple[str, str]]]:
    """The skills a registration writes to, or None when the request cannot be authorized.

    A single registration names its skill in the path. A bulk one names an organization and a list
    of skill names in its JSON body, which MLflow's handler reads the same way.
    """
    if route.operation == REGISTER:
        return [(route.organization, route.name)] if route.name is not None else None
    body = await _json_object(request)
    if body is None:
        return None
    skills = body.get("skills")
    organization = body.get("organization", "")
    if not isinstance(skills, list) or not skills or len(skills) > _MAX_BULK_TARGETS:
        return None
    targets = []
    for skill in skills:
        name = skill.get("name") if isinstance(skill, dict) else None
        try:
            validate_skill_identity(organization, name)
        except ValueError:
            return None
        targets.append((organization, name))
    return targets


def get_skill_registry_validator(path: str) -> Callable[[str, Request], Awaitable[bool]]:
    """Return the validator for a skill registry request (see the module docstring)."""
    from mlflow_oidc_auth.utils.permissions import can_update_skill, effective_skill_permission

    async def validator(username: str, request: Request) -> bool:
        route = resolve_skill_route(path, request.method)
        if route is None:
            return False
        if route.operation == SEARCH:
            # MLflow's handler narrows its query to this scope before paginating.
            request.state.skill_identity_scope = skill_search_scope(username)
            return True
        if route.operation == CREATE:
            body = await _json_object(request)
            if body is None:
                return False
            organization, name = body.get("organization", ""), body.get("name")
            try:
                validate_skill_identity(organization, name)
            except ValueError:
                return False
            return _can_create_named(format_skill_key(organization, name), username)
        if route.operation in (REGISTER, BULK_REGISTER):
            targets = await _registration_targets(route, request)
            if targets is None:
                return False
            expected: dict[str, bool] = {}
            for organization, name in targets:
                key = format_skill_key(organization, name)
                # MLflow creates a skill that does not exist yet, so that registration is a creation.
                exists = _skill_exists(organization, name)
                if not (can_update_skill(key, username) if exists else _can_create_named(key, username)):
                    return False
                expected[name] = exists
            # MLflow's handler refuses the registration if a skill appeared or vanished since:
            # what was authorized here is then no longer what it would do.
            request.state.skill_expected_parent_exists = expected if route.operation == BULK_REGISTER else expected[route.name]
            return True
        if route.key is None:
            return False
        permission = effective_skill_permission(route.key, username).permission
        if route.operation == READ:
            return permission.can_read
        if route.operation == UPDATE:
            return permission.can_update
        if route.operation == UPDATE_VERSION:
            body = await _json_object(request)
            # A body that cannot be read here is judged as the most this route can do, never as
            # "no status change": what MLflow's handler makes of it is not this check's to assume.
            if body is None:
                return permission.can_manage
            status = body.get("status")
            if status is not None and not (isinstance(status, str) and status in _EDIT_STATUSES):
                return permission.can_manage
            return permission.can_update
        if route.operation in (MANAGE, DELETE_SKILL):
            return permission.can_manage
        return False

    return validator


# ---------------------------------------------------------------------------
# After MLflow's handler
# ---------------------------------------------------------------------------


def _filter_search_body(username: str, body: bytes) -> bytes:
    """Keep only the skills ``username`` may READ.

    MLflow already narrowed its query to :func:`skill_search_scope`; this re-checks every item, so
    a registry that ignored the scope still returns nothing the caller may not read.

    Raises:
        ValueError: The body is not a skill list response.
    """
    from mlflow_oidc_auth.utils.permissions import can_read_skill

    data = json.loads(body)
    items = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("skill registry response carries no list")
    visible = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            organization, name = item.get("organization") or "", item.get("name")
            validate_skill_identity(organization, name)
            if can_read_skill(format_skill_key(organization, name), username):
                visible.append(item)
        except Exception as e:
            logger.error("Skill registry: permission check failed: %s", type(e).__name__)
    data["skills"] = visible
    return json.dumps(data).encode()


def _grant_creator_manage(key: str, username: str) -> None:
    """Make ``username`` the one holder of a grant on the skill they just created: MANAGE.

    Any grant already stored under ``key`` in the request's grant workspace predates the skill — a
    leftover of a deleted skill of that name whose cascade failed, or one written ahead of it — and
    would hand someone else's permission to the new skill. They are deleted first.
    """
    from mlflow.exceptions import MlflowException
    from mlflow.protos.databricks_pb2 import RESOURCE_ALREADY_EXISTS, ErrorCode

    from mlflow_oidc_auth.permissions import MANAGE as MANAGE_PERMISSION
    from mlflow_oidc_auth.store import store

    store.wipe_skill_permissions(key)
    try:
        store.create_skill_permission(key, username, MANAGE_PERMISSION.name)
    except MlflowException as e:
        if e.error_code != ErrorCode.Name(RESOURCE_ALREADY_EXISTS):
            raise
        store.update_skill_permission(key, username, MANAGE_PERMISSION.name)


def _grant_created_skills(request: Request, username: str, auth_context: Any) -> None:
    """Grant the caller MANAGE on the skills MLflow's handler reports it created. Never raises.

    The handler lists them in ``request.state.skill_created_parents``. Each is looked up again: only
    a skill MLflow recorded this caller as the creator of, in the workspace the grant is written in,
    is granted — a skill someone else created in between is theirs.
    """
    from mlflow_oidc_auth.utils.grant_workspace import current_grant_workspace

    for created in getattr(request.state, "skill_created_parents", None) or ():
        try:
            organization, name = created
            validate_skill_identity(organization, name)
            from mlflow.server.handlers import _get_tracking_store

            with bridged_auth_context(auth_context):
                skill = _get_tracking_store().get_skill(name=name, organization=organization)
                if getattr(skill, "created_by", None) != username:
                    continue
                workspace = getattr(skill, "workspace", None)
                if config.MLFLOW_ENABLE_WORKSPACES and workspace is not None and workspace != current_grant_workspace():
                    raise ValueError("skill created outside the request's grant workspace")
                _grant_creator_manage(format_skill_key(organization, name), username)
        except Exception as e:
            # The skill exists; failing the response would make the client retry into a conflict.
            # Without a MANAGE grant it is governed by workspace permissions until someone grants one.
            logger.error("Skill registry: could not grant the creator MANAGE: %s", type(e).__name__)


async def finalize_skill_response(path: str, username: str, request: Request, response: Response, auth_context: Any, is_admin: bool = False) -> Response:
    """Post-process a registry response.

    For an admin only the delete cascade runs: an admin sees everything and is never granted
    anything, but the grants on a skill an admin deletes must go with it. For everyone else:

    * a search response is re-checked item by item; a body that cannot be filtered is an error,
      never the unfiltered list;
    * a successful create, or a registration that created its skill, grants the creator ``MANAGE``
      in the request's workspace — only once MLflow returned success;
    * a successful skill delete removes the skill's grants in the request's workspace.

    Non-2xx responses are returned unchanged.
    """
    route = resolve_skill_route(path, request.method)
    if route is None or not 200 <= response.status_code < 300:
        return response
    if is_admin and route.operation != DELETE_SKILL:
        return response

    if route.operation == SEARCH:
        body = await buffer_body(response)
        try:
            with bridged_auth_context(auth_context):
                filtered = _filter_search_body(username, body)
        except Exception as e:
            logger.error("Failed to filter skill registry response: %s", type(e).__name__)
            return JSONResponse(status_code=500, content={"detail": "Failed to filter response"})
        return rebuilt_response(response, filtered)

    if route.operation in (CREATE, REGISTER, BULK_REGISTER):
        _grant_created_skills(request, username, auth_context)
        return response

    if route.operation == DELETE_SKILL and route.key is not None:
        try:
            from mlflow_oidc_auth.store import store

            with bridged_auth_context(auth_context):
                store.wipe_skill_permissions(route.key)
        except Exception as e:
            # Stale grants are wiped again if a skill is created under this key, but until then
            # they are visible in the permission API: make the failure loud.
            logger.error("Failed to cascade-delete permissions for a skill: %s", type(e).__name__)
        return response

    return response


__all__ = [
    "SkillRoute",
    "can_create_skill",
    "finalize_skill_response",
    "get_skill_registry_validator",
    "is_skill_registry_path",
    "resolve_skill_route",
    "skill_route_prefixes",
    "skill_search_scope",
]
