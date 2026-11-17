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
                                               (a re-creator's own grant is kept)
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

import asyncio
import functools
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


@functools.cache
def skill_route_prefixes() -> tuple[str, ...]:
    """Every prefix the registry is served under: the bare paths and the static-prefixed ones.

    MLflow mounts the registry at ``get_skill_registry_api_route_prefixes()``, which puts its static
    prefix in front of both paths. Empty on an MLflow without the registry: nothing is mounted
    there, so those paths stay with Flask (a 404), exactly as before this plugin knew of skills.

    Computed once per process: the static prefix is fixed at startup, and this runs on every
    request the FastAPI permission middleware sees.
    """
    try:
        from mlflow.server.skill_registry_api import get_skill_registry_api_route_prefixes
    except ImportError:
        return ()
    prefixes = set(SKILL_PREFIXES) | set(get_skill_registry_api_route_prefixes())
    # Longest first, so a static-prefixed mount is never mistaken for a bare one.
    return tuple(sorted(prefixes, key=len, reverse=True))


def _strip_prefix(path: str) -> Optional[str]:
    """``path`` below the registry prefix it is on (``""`` for the prefix itself), or None when off it."""
    for prefix in skill_route_prefixes():
        if path == prefix or path.startswith(prefix + "/"):
            return path[len(prefix) :]
    return None


def is_skill_registry_path(path: str) -> bool:
    """Whether ``path`` is on the skill registry, with or without MLflow's static prefix.

    A registry prefix, or anything below it on a segment boundary (``/skillsfoo`` is not on it), as
    MLflow's own ``is_skill_registry_api_path`` decides. Everything on it goes to the registry
    validator, which denies whatever it cannot resolve to one of MLflow's routes.
    """
    return _strip_prefix(path) is not None


@functools.cache
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
    suffix = _strip_prefix(path)
    if suffix is None:
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


def _can_create_named(key: str, username: str, permission_of: Optional[Callable[[str], Any]] = None) -> bool:
    """Create rights, unless a grant already stored under ``key`` keeps ``username`` from changing it.

    A grant can outlive its skill, when the delete cascade failed (the permission API refuses to
    write one ahead of it). One that does not let the caller edit — ``READ``, or
    ``NO_PERMISSIONS`` to shut them out — must not be overridden by creating the skill and
    collecting the creator's ``MANAGE``.

    Parameters:
        key: The skill key.
        username: The caller.
        permission_of: A resolver from :func:`~mlflow_oidc_auth.utils.permissions.skill_permission_resolver`
            to reuse across a batch; omitted, the single-skill check.
    """
    from mlflow_oidc_auth.utils.permissions import effective_skill_permission

    result = permission_of(key) if permission_of is not None else effective_skill_permission(key, username)
    if result.kind in ("user", "group") and not result.permission.can_update:
        return False
    return can_create_skill(username)


def _existing_skill_names(organization: str, names: set[str]) -> set[str]:
    """Which of ``names`` in ``organization`` the request's workspace holds, in one registry query.

    Raises:
        Exception: Any lookup failure — the caller denies.
    """
    from mlflow.server.handlers import _get_tracking_store

    found = _get_tracking_store().search_skills(
        max_results=len(names),
        include_skill_identities=[(organization, name) for name in sorted(names)],
    )
    return {skill.name for skill in found if (getattr(skill, "organization", "") or "") == organization} & names


def _authorize_registration(targets: list[tuple[str, str]], username: str) -> Optional[dict[str, bool]]:
    """Authorize registering a version of each target: ``{name: exists}``, or None to deny.

    A skill that exists needs ``EDIT``; one that does not is created by MLflow, so it needs create
    rights (:func:`_can_create_named`). Existence is read in one query and grants from one bulk
    context, so a batch costs a fixed number of statements.
    """
    from mlflow_oidc_auth.utils.permissions import skill_permission_resolver

    organizations = {organization for organization, _ in targets}
    if len(organizations) != 1:
        return None
    (organization,) = organizations
    names = {name for _, name in targets}
    existing = _existing_skill_names(organization, names)
    permission_of = skill_permission_resolver(username)
    expected: dict[str, bool] = {}
    for name in sorted(names):
        key = format_skill_key(organization, name)
        exists = name in existing
        if not (permission_of(key).permission.can_update if exists else _can_create_named(key, username, permission_of)):
            return None
        expected[name] = exists
    return expected


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
    from mlflow_oidc_auth.utils.permissions import SKILL, skill_permission_resolver

    permission_of = skill_permission_resolver(username)
    baseline_read = permission_of(_NO_GRANT_KEY).permission.can_read
    keys = {grant.name for grant in store.list_user_grants(SKILL, username)} | {grant.name for grant in store.list_user_groups_grants(SKILL, username)}
    exceptions: set[tuple[str, str]] = set()
    for key in keys:
        try:
            identity = parse_skill_key(key)
        except ValueError:
            # No skill MLflow can store answers to this key, so there is nothing to include or exclude.
            continue
        if permission_of(key).permission.can_read != baseline_read:
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
    from mlflow_oidc_auth.utils.permissions import effective_skill_permission

    async def validator(username: str, request: Request) -> bool:
        route = resolve_skill_route(path, request.method)
        if route is None:
            return False
        if route.operation == SEARCH:
            # MLflow's handler narrows its query to this scope before paginating, and
            # finalize_skill_response holds the response to the same scope.
            request.state.skill_identity_scope = await asyncio.to_thread(skill_search_scope, username)
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
            # Store and grant reads are synchronous; a bulk batch holds up to _MAX_BULK_TARGETS
            # skills, so they run off the event loop (the auth and workspace context go with them).
            expected = await asyncio.to_thread(_authorize_registration, targets, username)
            if expected is None:
                return False
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


async def prepare_admin_skill_request(path: str, request: Request, auth_context: Any) -> Optional[Response]:
    """Before an admin's registration: tell MLflow which targets exist.

    Admins skip the validator, which is what hands MLflow ``skill_expected_parent_exists``; without
    it MLflow does not report the skills a registration created, and :func:`finalize_skill_response`
    could not clear the grants left under their keys. MLflow refuses the registration if a target
    appeared or vanished since, as for everyone else.

    A registration body this cannot read is refused here (``400``, in MLflow's error format) rather
    than handed to MLflow without the expectation: were MLflow to accept it, the skill it created
    would keep the grants left under its key.

    Returns:
        None to go on, or the response refusing the request.

    Raises:
        Exception: The registry lookup failed. The caller refuses the request rather than let a
            registration create a skill whose leftover grants would then go uncleared.
    """
    route = resolve_skill_route(path, request.method)
    if route is None or route.operation not in (REGISTER, BULK_REGISTER):
        return
    targets = await _registration_targets(route, request)
    if not targets:
        return JSONResponse(status_code=400, content={"error_code": "INVALID_PARAMETER_VALUE", "message": "Invalid skill registration request"})
    organization = targets[0][0]
    names = {name for _, name in targets}

    def existing() -> set[str]:
        with bridged_auth_context(auth_context):
            return _existing_skill_names(organization, names)

    found = await asyncio.to_thread(existing)
    expected = {name: name in found for name in names}
    request.state.skill_expected_parent_exists = expected if route.operation == BULK_REGISTER else expected[route.name]
    return None


# ---------------------------------------------------------------------------
# After MLflow's handler
# ---------------------------------------------------------------------------


def _filter_search_body(scope: Any, body: bytes, permission_of: Callable[[str], Any]) -> bytes:
    """Keep only the skills the caller may READ: inside the validator's scope, and readable by key.

    MLflow already narrowed its query to that scope (:func:`skill_search_scope`). Every item is held
    to it again, and resolved by its own key as well, the way ``GET /skills/<skill>`` resolves it:
    a registry that ignored the scope returns nothing unreadable, and a list never shows a skill
    its detail route refuses — say a skill whose name differs only in case from a denied one, where
    the grant database compares names without case and the registry with it. The resolver reads the
    caller's grants once (see :func:`~mlflow_oidc_auth.utils.permissions.skill_permission_resolver`).

    Parameters:
        scope: ``request.state.skill_identity_scope``: ``(include, exclude)``.
        body: MLflow's response body.
        permission_of: The caller's resolver, from a key to their permission on that skill.

    Raises:
        ValueError: The body is not a skill list response, or there is no scope to hold it to.
    """
    if not (isinstance(scope, tuple) and len(scope) == 2):
        raise ValueError("no skill search scope for this request")
    include, exclude = scope
    allowed = None if include is None else set(include)
    denied = set(exclude or ())
    data = json.loads(body)
    items = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("skill registry response carries no list")
    visible = []
    for item in items:
        if not isinstance(item, dict):
            continue
        organization, name = item.get("organization") or "", item.get("name")
        try:
            validate_skill_identity(organization, name)
        except ValueError:
            continue
        identity = (organization, name)
        in_scope = (identity in allowed) if allowed is not None else (identity not in denied)
        if in_scope and permission_of(format_skill_key(organization, name)).permission.can_read:
            visible.append(item)
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


def _grant_created_skills(request: Request, username: str, auth_context: Any, grant: bool = True) -> None:
    """Grant the caller MANAGE on the skills MLflow's handler reports it created. Never raises.

    The handler lists them in ``request.state.skill_created_parents``. Each is looked up again: only
    a skill MLflow recorded this caller as the creator of, in the workspace the grant is written in,
    is granted — a skill someone else created in between is theirs. With ``grant=False`` (an admin,
    who is never granted anything) the leftover grants under its key are still removed, so a new
    skill never inherits the grants of an earlier one of the same name, whoever creates it.
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
                key = format_skill_key(organization, name)
                if grant:
                    _grant_creator_manage(key, username)
                else:
                    from mlflow_oidc_auth.store import store

                    store.wipe_skill_permissions(key)
        except Exception as e:
            # The skill exists; failing the response would make the client retry into a conflict.
            # Without a MANAGE grant it is governed by workspace permissions until someone grants one.
            logger.error("Skill registry: could not grant the creator MANAGE: %s", type(e).__name__)


def _recreated_skill_creator(organization: str, name: str) -> Optional[str]:
    """The creator of a skill stored under the key again, ``""`` when there is none or it is unknown.

    A failed lookup counts as "none": the grants are then wiped, never kept on a guess.
    """
    from mlflow.server.handlers import _get_tracking_store

    try:
        skill = _get_tracking_store().get_skill(name=name, organization=organization)
    except Exception:
        return ""
    return getattr(skill, "created_by", None) or ""


def _cascade_delete(route: SkillRoute, auth_context: Any) -> None:
    """Delete the grants on the skill ``route`` just deleted, in the request's grant workspace.

    MLflow committed the delete before this runs, so a skill may already be stored under the key
    again. Its creator's own grant — the ``MANAGE`` :func:`_grant_created_skills` gave them — is
    kept; every other grant is a leftover of the deleted skill and goes, even if the new creator's
    own cleanup failed.
    """
    from mlflow.exceptions import MlflowException

    from mlflow_oidc_auth.store import store

    with bridged_auth_context(auth_context):
        creator = _recreated_skill_creator(route.organization, route.name)
        kept = None
        if creator:
            try:
                kept = store.get_skill_permission(route.key, creator).permission
            except MlflowException:
                kept = None
        store.wipe_skill_permissions(route.key)
        if kept is not None:
            store.create_skill_permission(route.key, creator, kept)


async def finalize_skill_response(path: str, username: str, request: Request, response: Response, auth_context: Any, is_admin: bool = False) -> Response:
    """Post-process a registry response.

    An admin sees everything and is never granted anything, but the leftover grants under the key
    of a skill an admin creates are removed, and the grants on a skill an admin deletes go with it.
    For everyone else:

    * a search response is held item by item to the scope the validator computed; a body that
      cannot be filtered is an error, never the unfiltered list;
    * a successful create, or a registration that created its skill, replaces any grants left under
      its key with the creator's ``MANAGE`` in the request's workspace — only once MLflow returned
      success;
    * a successful skill delete removes the skill's grants in the request's workspace, all but the
      creator's own if a skill of that name was created again in between.

    Non-2xx responses are returned unchanged.
    """
    route = resolve_skill_route(path, request.method)
    if route is None or not 200 <= response.status_code < 300:
        return response
    if is_admin and route.operation in (CREATE, REGISTER, BULK_REGISTER):
        await asyncio.to_thread(_grant_created_skills, request, username, auth_context, False)
        return response
    if is_admin and route.operation != DELETE_SKILL:
        return response

    if route.operation == SEARCH:
        body = await buffer_body(response)
        scope = getattr(request.state, "skill_identity_scope", None)

        def filtered_body() -> bytes:
            from mlflow_oidc_auth.utils.permissions import skill_permission_resolver

            with bridged_auth_context(auth_context):
                return _filter_search_body(scope, body, skill_permission_resolver(username))

        try:
            filtered = await asyncio.to_thread(filtered_body)
        except Exception as e:
            logger.error("Failed to filter skill registry response: %s", type(e).__name__)
            return JSONResponse(status_code=500, content={"detail": "Failed to filter response"})
        return rebuilt_response(response, filtered)

    if route.operation in (CREATE, REGISTER, BULK_REGISTER):
        await asyncio.to_thread(_grant_created_skills, request, username, auth_context)
        return response

    if route.operation == DELETE_SKILL and route.key is not None:
        try:
            await asyncio.to_thread(_cascade_delete, route, auth_context)
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
    "prepare_admin_skill_request",
    "resolve_skill_route",
    "skill_route_prefixes",
    "skill_search_scope",
]
