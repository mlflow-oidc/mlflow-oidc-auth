"""Generated grant routes for the user and group permission routers (#459).

``routers/user_permissions.py`` and ``routers/group_permissions.py`` serve the same handful of
routes for every resource kind: get, create, update and delete one grant (and list them), for a
user or a group, as an exact grant or a regex pattern. Those routes differ only in data, so they
are produced here from a spec rather than written out ~140 times by hand.

A spec carries everything that differs between two routes:

* the path and the route name (the name is the OpenAPI operation id),
* the request and response models and the parameter texts (the OpenAPI contract),
* the authorization dependency ``auth`` and, for the routes that check inline, a ``guard``,
* the audit ``resource_type``,
* the store call, the response, the messages and how a failure is reported.

The generated routes must stay indistinguishable from the hand-written ones they replace: the
committed ``openapi.json`` is unchanged, and so are status codes, bodies, log lines and audit
events. That is why the text and error templates below look as irregular as they do.

Security: ``auth`` is the only thing between a caller and a grant change, and the factory never
supplies a default for an exact grant. ``tests/routers/test_permission_route_auth.py`` pins the gate
of every route against an explicit table.

Store calls are lambdas defined in the router modules, so they resolve ``store`` (and every helper
they use) in the router module at call time. Tests patch those module attributes.
"""

import inspect
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import StatusMessageResponse, StatusOnlyResponse
from mlflow_oidc_auth.utils import get_is_admin, get_username

logger = get_logger()

Args = SimpleNamespace
"""A route's bound arguments, by parameter name (``a.username``, ``a.permission_data``)."""

Auth = Tuple[Tuple[str, Callable[..., Any]], ...]
"""``(parameter name, dependency)`` pairs. The first one's value is the audit actor."""

ADMIN: Auth = (("admin_username", check_admin_permission),)
CALLER: Auth = (("current_username", get_username), ("is_admin", get_is_admin))
"""The caller and whether they are an admin, for a route that checks permission inline with a ``guard``."""

ALL_OPS = ("list", "create", "get", "update", "delete")

BAD_PATTERN_ID = "Invalid pattern ID format. Expected an integer."

_METHOD = {"list": "GET", "create": "POST", "get": "GET", "update": "PATCH", "delete": "DELETE"}
_VERB = {"list": "List", "create": "Create", "get": "Get", "update": "Update", "delete": "Delete"}
_GERUND = {"list": "listing", "create": "creating", "get": "getting", "update": "updating", "delete": "deleting"}
_PAST = {"create": "created", "update": "updated", "delete": "deleted"}
_DOES = {"list": "Retrieves", "get": "Retrieves", "update": "Updates", "delete": "Deletes"}
_PURPOSE = {"create": "set", "get": "get", "update": "update", "delete": "delete"}
_ID_TEXT = {"get": "The pattern ID to retrieve", "update": "The pattern ID to update", "delete": "The pattern ID to delete"}


def pattern_fields(a: Args) -> Dict[str, Any]:
    """The regex, priority and permission of a pattern request body, as store keyword arguments."""
    return {"regex": a.pattern_data.regex, "priority": a.pattern_data.priority, "permission": a.pattern_data.permission}


def regex_names(kind: str) -> Dict[str, str]:
    """Endpoint names of the older pattern routes, which say ``regex`` where newer ones say ``pattern``.

    Parameters:
        kind: Subject and kind, e.g. ``"user_prompt"``.

    Returns:
        The endpoint name of every op.
    """
    return {op: f"{'get' if op == 'list' else op}_{kind}_regex_permission{'s' if op == 'list' else ''}" for op in ALL_OPS}


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _snake(label: str) -> str:
    return label.replace(" ", "_")


@dataclass(frozen=True)
class Failure:
    """How a route reports an exception raised by its store call, audit or response.

    Parameters:
        log: Prefix of the error line logged as ``f"{log}: {error}"``.
        status: Status of the HTTPException any other exception becomes.
        detail: Detail of that HTTPException.
        bad_id: Report a ``ValueError`` (a pattern id that is not an integer) as a 400.
        mlflow: ``(error_code, status, detail)`` for an ``MlflowException``; a ``None`` detail
            echoes the exception. An ``MlflowException`` matching none of them is re-raised.
    """

    log: str
    status: int
    detail: str
    bad_id: bool = False
    mlflow: Tuple[Tuple[int, int, Optional[str]], ...] = ()

    def translate(self, error: Exception) -> Optional[HTTPException]:
        """Return the HTTPException to raise for ``error``, or ``None`` to re-raise it unchanged.

        Parameters:
            error: The exception the route raised.

        Returns:
            The HTTPException to raise instead, or ``None``.
        """
        if self.mlflow and isinstance(error, MlflowException):
            logger.error(f"{self.log}: {str(error)}")
            code = getattr(error, "error_code", None)
            for error_code, status, detail in self.mlflow:
                if code == error_code:
                    return HTTPException(status_code=status, detail=str(error) if detail is None else detail)
            return None
        if self.bad_id and isinstance(error, ValueError):
            return HTTPException(status_code=400, detail=BAD_PATTERN_ID)
        logger.error(f"{self.log}: {str(error)}")
        return HTTPException(status_code=self.status, detail=self.detail)


@dataclass(frozen=True)
class Route:
    """One generated route.

    Parameters:
        name: Endpoint name, which is also the OpenAPI operation id.
        op: ``list``, ``create``, ``get``, ``update`` or ``delete``; picks the HTTP method and the audit event.
        path: Path below the router prefix.
        summary: OpenAPI summary.
        description: OpenAPI description.
        tag: OpenAPI tag.
        params: Path parameters in signature order, as ``(name, type, description)``.
        auth: The authorization dependencies, see :data:`Auth`.
        call: The store call; its result is passed to ``respond``.
        respond: Builds the response from the arguments and the store result.
        response_model: OpenAPI response model.
        body: The request body as ``(name, model, description)``, if any.
        status_code: Success status, if not 200.
        exclude_none: ``response_model_exclude_none``.
        audit: ``(resource_type, resource_id, detail)`` of the audit event a write emits.
        failure: How exceptions are reported; ``None`` lets them propagate.
        guard: An inline authorization check that runs before anything else.
    """

    name: str
    op: str
    path: str
    summary: str
    description: str
    tag: str
    params: Tuple[Tuple[str, Any, str], ...]
    auth: Auth
    call: Callable[[Args], Any]
    respond: Callable[[Args, Any], Any]
    response_model: Any
    body: Optional[Tuple[str, Any, str]] = None
    status_code: Optional[int] = None
    exclude_none: bool = False
    audit: Optional[Tuple[str, Callable[[Args], Any], Callable[[Args], Dict[str, Any]]]] = None
    failure: Optional[Failure] = None
    guard: Optional[Callable[[Args], None]] = None


def _perform(route: Route, a: Args) -> Any:
    result = route.call(a)
    if route.audit is not None:
        resource_type, resource_id, detail = route.audit
        event = f"permission.{route.op}"
        emit_audit_event(event, actor=getattr(a, route.auth[0][0]), resource_type=resource_type, resource_id=resource_id(a), detail=detail(a))
    return route.respond(a, result)


def _execute(route: Route, a: Args) -> Any:
    if route.guard is not None:
        route.guard(a)
    if route.failure is None:
        return _perform(route, a)
    try:
        return _perform(route, a)
    except Exception as error:
        translated = route.failure.translate(error)
        if translated is None:
            raise
        raise translated


def add_route(router: APIRouter, route: Route) -> Callable[..., Any]:
    """Register ``route`` on ``router`` and return its endpoint.

    The endpoint gets an explicit signature, so FastAPI sees exactly the path parameters, body
    and dependencies a hand-written endpoint would declare, in the same order.

    Parameters:
        router: The router to add the route to.
        route: The route.

    Returns:
        The endpoint coroutine function.
    """
    kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
    parameters = [inspect.Parameter(name, kind, default=Path(..., description=text), annotation=type_) for name, type_, text in route.params]
    if route.body is not None:
        name, model, text = route.body
        parameters.append(inspect.Parameter(name, kind, default=Body(..., description=text), annotation=model))
    parameters += [inspect.Parameter(name, kind, default=Depends(dependency), annotation=Any) for name, dependency in route.auth]
    signature = inspect.Signature(parameters, return_annotation=route.response_model)

    async def endpoint(*args: Any, **kwargs: Any) -> Any:
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        return _execute(route, Args(**bound.arguments))

    endpoint.__signature__ = signature  # type: ignore[attr-defined]
    endpoint.__name__ = endpoint.__qualname__ = route.name
    endpoint.__doc__ = route.description
    router.add_api_route(
        route.path,
        endpoint,
        methods=[_METHOD[route.op]],
        response_model=route.response_model,
        status_code=route.status_code,
        tags=[route.tag],
        summary=route.summary,
        description=route.description,
        response_model_exclude_none=route.exclude_none,
    )
    return endpoint


@dataclass(frozen=True)
class Subject:
    """Who a grant is for: a user or a group."""

    param: str  # path parameter naming the grantee
    noun: str  # how parameter texts name it
    word: str  # "user" / "group"
    prefix: str  # "" / "group " in front of log lines, error details and audit resource types
    message: str  # how messages name it, as a format string over the route's arguments

    @property
    def who(self) -> str:
        return f"a {self.word}"


USER = Subject("username", "username", "user", "", "{username}")
GROUP = Subject("group_name", "group name", "group", "group ", "group {group_name}")


def _texts(text: Optional[Mapping[str, Mapping[str, str]]], op: str) -> Mapping[str, str]:
    return (text or {}).get(op, {})


def exact_routes(
    router: APIRouter,
    subject: Subject,
    label: str,
    tag: str,
    path: str,
    *,
    keys: Sequence[Tuple[str, str]],
    auth: Auth,
    call: Mapping[str, Callable[[Args], Any]],
    body: Any,
    ops: Sequence[str] = ("create", "get", "update", "delete"),
    list_path: Optional[str] = None,
    models: Optional[Mapping[str, Any]] = None,
    respond: Optional[Mapping[str, Callable[[Args, Any], Any]]] = None,
    on: Optional[str] = None,
    messages: Optional[Mapping[str, str]] = None,
    message_model: Any = StatusMessageResponse,
    created: Optional[int] = 201,
    guard: Optional[Callable[[Args], None]] = None,
    conflicts: bool = False,
    handled: bool = True,
    text: Optional[Mapping[str, Mapping[str, str]]] = None,
) -> None:
    """Add the routes managing exact grants of one resource kind for a user or a group.

    Parameters:
        router: The router to add the routes to.
        subject: :data:`USER` or :data:`GROUP`.
        label: The resource kind as the texts name it, e.g. ``"registered model"``.
        tag: OpenAPI tag.
        path: Path of one grant.
        keys: The resource's path parameters as ``(name, description)``; ``{purpose}`` in a
            description becomes set/get/update/delete. The last one is the audit resource id.
        auth: The authorization dependencies of every route. There is deliberately no default.
        call: The store call of each op.
        body: Request model of create and update.
        ops: The routes to add, in registration order.
        list_path: Path of the ``list`` route.
        models: Response model of an op, where not the message model.
        respond: Builds the response of an op, where not the message.
        on: Format string naming the resource in messages; defaults to the last key.
        messages: A message of an op, replacing the generated one.
        message_model: Model of the create, update and delete messages.
        created: Success status of create.
        guard: An inline authorization check run before every route's store call.
        conflicts: Map MlflowException error codes of create and update, as the prompt,
            registered-model and scorer routes do.
        handled: ``False`` lets exceptions propagate instead of becoming a 404/500.
        text: OpenAPI text overrides, by op and then by ``summary``, ``description``,
            ``subject``, ``body`` or a key name.
    """
    who, noun, snake = subject.who, f"{subject.prefix}{label} permission", _snake(label)
    resource_key = keys[-1][0]
    on = on or "{" + resource_key + "}"
    for op in ops:
        t = _texts(text, op)
        verb = "get" if op == "list" else op
        name = f"{verb}_{subject.word}_{snake}_permission" + ("s" if op == "list" else "")
        if op == "list":
            route_path, summary = list_path, f"List {label} permissions for {who}"
            description = f"Retrieves a list of {label} permissions for the specified {subject.word}."
            params = ((subject.param, str, t.get("subject", f"The {subject.noun} to get {label} permissions for")),)
        else:
            route_path, summary = path, f"{_VERB[op]} {label} permission for {who}"
            if op == "create":
                description = f"Creates a new permission for {who} to access a specific {label}."
                purpose_text = f"The {subject.noun} to grant {label} permission to"
            else:
                description = f"{_DOES[op]} the permission for {who} on a specific {label}."
                purpose_text = f"The {subject.noun} to {op} {label} permission for"
            params = ((subject.param, str, t.get("subject", purpose_text)),)
            params += tuple((key, str, t.get(key, key_text.format(purpose=_PURPOSE[op]))) for key, key_text in keys)
        audit = None
        if op in _PAST:
            extra = [key for key, _ in keys if key != resource_key]
            with_permission = op != "delete"

            def detail(a: Args, extra: List[str] = extra, with_permission: bool = with_permission) -> Dict[str, Any]:
                values = {subject.param: getattr(a, subject.param), **{key: getattr(a, key) for key in extra}}
                if with_permission:
                    values["permission"] = a.permission_data.permission
                return values

            audit = (f"{_snake(subject.prefix)}{snake}_permission", lambda a: getattr(a, resource_key), detail)
        failure = None
        if handled:
            mlflow: Tuple[Tuple[int, int, Optional[str]], ...] = ()
            if conflicts and op == "create":
                mlflow = ((RESOURCE_ALREADY_EXISTS, 409, f"{_cap(noun)} already exists"), (INVALID_PARAMETER_VALUE, 400, None))
            if conflicts and op == "update":
                mlflow = ((RESOURCE_DOES_NOT_EXIST, 404, f"{_cap(noun)} does not exist"), (INVALID_PARAMETER_VALUE, 400, None))
            if op == "get":
                failure = Failure(f"Error getting {noun}", 404, f"{_cap(noun)} not found")
            elif op == "list":
                failure = Failure(f"Error listing {noun}s", 500, f"Failed to retrieve {noun}s")
            else:
                failure = Failure(f"Error {_GERUND[op]} {noun}", 500, f"Failed to {op} {noun}", mlflow=mlflow)
        message = (messages or {}).get(op, f"{_cap(label)} permission {_PAST.get(op)} for {subject.message} on {on}")
        add_route(
            router,
            Route(
                name=name,
                op=op,
                path=route_path,
                summary=t.get("summary", summary),
                description=t.get("description", description),
                tag=tag,
                params=params,
                auth=auth,
                call=call[op],
                respond=(respond or {}).get(op, lambda a, _, message=message: message_model(message=message.format(**vars(a)))),
                response_model=(models or {}).get(op, message_model),
                body=(
                    ("permission_data", body, t.get("body", "The permission details" if op == "create" else "Updated permission details"))
                    if op in ("create", "update")
                    else None
                ),
                status_code=created if op == "create" else None,
                audit=audit,
                failure=failure,
                guard=guard if op != "list" else None,
            ),
        )


def regex_routes(
    router: APIRouter,
    subject: Subject,
    label: str,
    tag: str,
    path: str,
    detail_path: str,
    *,
    call: Mapping[str, Callable[[Args], Any]],
    body: Any,
    item: Callable[[Any], Any],
    item_model: Any,
    ops: Sequence[str] = ALL_OPS,
    id_type: type = int,
    names: Optional[Mapping[str, str]] = None,
    models: Optional[Mapping[str, Any]] = None,
    respond: Optional[Mapping[str, Callable[[Args, Any], Any]]] = None,
    quiet_delete: bool = False,
    specific: Sequence[str] = (),
    plural: str = "",
    lab: Optional[str] = None,
    group_failures: bool = False,
    conflicts: bool = False,
    text: Optional[Mapping[str, Mapping[str, str]]] = None,
) -> None:
    """Add the admin-only routes managing regex (pattern) grants of one kind for a user or a group.

    Parameters:
        router: The router to add the routes to.
        subject: :data:`USER` or :data:`GROUP`.
        label: The resource kind as the texts name it.
        tag: OpenAPI tag.
        path: Path of the list and create routes.
        detail_path: Path of one pattern, ending in ``{id}``.
        call: The store call of each op.
        body: Request model of create and update.
        item: Turns one stored pattern into ``item_model``; used by list and get.
        item_model: Response model of get (and of each element of list).
        ops: The routes to add, in registration order.
        id_type: ``str`` ids are converted by the store call, and a bad one is a 400.
        names: Endpoint name of an op, where not ``{verb}_{subject}_{kind}_pattern_permission``.
        models: Response model of an op, where not the default.
        respond: Builds the response of an op, where not the default.
        quiet_delete: delete answers an empty ``StatusOnlyResponse``.
        specific: Ops documented in the "specific ... regex pattern permission" wording.
        plural: The kind in the plural, for that wording of create.
        lab: How the parameter texts in the regex-based wording name the kind ("" omits it).
        group_failures: Report list and get failures as "Failed to get ..." 500s.
        conflicts: Map MlflowException error codes of create.
        text: OpenAPI text overrides, by op and then by ``summary``.
    """
    who, noun, snake = subject.who, f"{subject.prefix}{label} pattern permission", _snake(label)
    lab = f"{label} " if lab is None else lab
    for op in ops:
        t = _texts(text, op)
        name = (names or {}).get(op, f"{'get' if op == 'list' else op}_{subject.word}_{snake}_pattern_permission" + ("s" if op == "list" else ""))
        if op in specific:
            id_text, subject_text = "The pattern ID", f"The {subject.noun}"
            summary = {
                "list": f"Get {subject.word} {label} pattern permissions",
                "get": f"Get specific {label} pattern permission for {who}",
            }.get(op, f"{_VERB[op]} {label} pattern permission for {who}")
            description = {
                "list": f"Retrieves all {label} regex pattern permissions for a specific {subject.word}.",
                "create": f"Creates a new regex pattern permission for {who} to access {plural}.",
            }.get(op, f"{_DOES.get(op)} a specific {label} regex pattern permission for {who}.")
            if op in ("list", "create"):
                subject_text = f"The {subject.noun} to {'get' if op == 'list' else 'create'} {label} pattern permission{'s' if op == 'list' else ''} for"
            body_text = "The pattern permission details"
        else:
            id_text = _ID_TEXT.get(op)
            summary = f"{_VERB[op]} {label} pattern permission{'s' if op == 'list' else ''} for {who}"
            description = {
                "list": f"Retrieves a list of regex-based {label} permission patterns for the specified {subject.word}.",
                "create": f"Creates a new regex-based permission pattern for {label} access.",
            }.get(op, f"{_DOES.get(op)} a specific regex-based {label} permission pattern for the specified {subject.word}.")
            subject_text = f"The {subject.noun} to {_VERB[op].lower()} {lab}pattern permission{'s' if op == 'list' else ''} for"
            body_text = "The regex pattern permission details"
        params: Tuple[Tuple[str, Any, str], ...] = ((subject.param, str, subject_text),)
        if op in ("get", "update", "delete"):
            params += (("id", id_type, id_text),)
        body_param = None
        if op in ("create", "update"):
            body_param = ("pattern_data", body, body_text if op == "create" else "Updated pattern permission details")
        audit = None
        if op in _PAST:
            details = {
                "create": lambda a: {"regex": a.pattern_data.regex, "priority": a.pattern_data.priority, "permission": a.pattern_data.permission},
                "update": lambda a: {"id": a.id, "regex": a.pattern_data.regex, "priority": a.pattern_data.priority, "permission": a.pattern_data.permission},
                "delete": lambda a: {"id": a.id},
            }
            audit = (f"{_snake(subject.prefix)}{snake}_regex_permission", lambda a: getattr(a, subject.param), details[op])
        bad_id = id_type is str and op in ("get", "update", "delete")
        if op == "list" and group_failures:
            failure = Failure(f"Error getting {noun}s", 500, f"Failed to get {noun}s")
        elif op == "list":
            failure = Failure(f"Error listing {noun}s", 500, f"Failed to retrieve {noun}s")
        elif op == "get" and group_failures:
            failure = Failure(f"Error getting {noun}", 500, f"Failed to get {noun}", bad_id=bad_id)
        elif op == "get":
            failure = Failure(f"Error getting {noun}", 404, f"{_cap(noun)} not found", bad_id=bad_id)
        else:
            mlflow: Tuple[Tuple[int, int, Optional[str]], ...] = ()
            if conflicts and op == "create":
                mlflow = ((RESOURCE_ALREADY_EXISTS, 409, f"{_cap(noun)} already exists"), (INVALID_PARAMETER_VALUE, 400, None))
            failure = Failure(f"Error {_GERUND[op]} {noun}", 500, f"Failed to {op} {noun}", bad_id=bad_id, mlflow=mlflow)
        if op == "list":
            default_model, default_respond = List[item_model], lambda a, r: [item(p) for p in r]
        elif op == "get":
            default_model, default_respond = item_model, lambda a, r: item(r)
        elif op == "delete" and quiet_delete:
            default_model, default_respond = StatusOnlyResponse, lambda a, r: StatusOnlyResponse()
        else:
            message = f"{_cap(label)} pattern permission {_PAST[op]} for {subject.message}"
            default_model, default_respond = StatusMessageResponse, lambda a, r, message=message: StatusMessageResponse(message=message.format(**vars(a)))
        add_route(
            router,
            Route(
                name=name,
                op=op,
                path=path if op in ("list", "create") else detail_path,
                summary=t.get("summary", summary),
                description=t.get("description", description),
                tag=tag,
                params=params,
                auth=ADMIN,
                call=call[op],
                respond=(respond or {}).get(op, default_respond),
                response_model=(models or {}).get(op, default_model),
                body=body_param,
                status_code=201 if op == "create" else None,
                exclude_none=op == "delete" and quiet_delete,
                audit=audit,
                failure=failure,
            ),
        )
