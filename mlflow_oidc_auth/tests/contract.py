"""Enforce the OpenAPI contract on the responses the test suite receives (#458).

The plugin's handlers mostly build their own ``JSONResponse``, which FastAPI returns as is: the
``response_model`` a route declares documents the body but is never checked against it. This module
closes that gap in the test suite. ``check_response`` takes a response and the app that produced
it, resolves the route that served it, and — when that route declares a model for the status —
validates the body against it:

- strictly — a string is not accepted for an integer, nor an integer for a string;
- with no undocumented fields — a key the model does not declare fails, at any depth. A new field
  added to a body without the contract (a hash, a full session id) fails the build rather than
  reaching the UI unannounced;
- with every field the serialization schema requires present, so a field the contract promises
  is always sent cannot quietly go missing.

Route resolution walks middleware wrappers and ``Mount``s and honours ``root_path``. A JSON
response on a plugin prefix (``/api/``, ``/ajax-api/``, ``/oidc/``, ``/scim/``) that resolves to no
route at all fails, rather than being skipped, unless it is a router-level 404/405 or is listed in
``UNMATCHED_ALLOWED``. A response served by something other than a FastAPI route (MLflow's Flask
app) is MLflow's, not the plugin's, and is left alone.

What is covered, exactly: every response a test receives through ``TestClient`` (the autouse
fixture in ``tests/conftest.py``), and the handlers a test awaits directly where the test wraps
them with ``checked()``. A handler awaited directly without ``checked()`` is not checked.

When a body and its model disagree, fix the model — unless the body is the bug (it leaks
something).
"""

from __future__ import annotations

import functools
import json
from typing import Any, Dict, List, Optional, Tuple

from fastapi.routing import APIRoute
from pydantic import TypeAdapter, ValidationError
from starlette.routing import Match, Mount

#: Property names no response may carry, compared case-insensitively at any depth. Shared by the
#: OpenAPI scan (test_openapi_contract.py) and the SCIM runtime check.
CREDENTIAL_PROPERTIES = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "token_hash",
        "secret",
        "client_secret",
        "session_id",
        "access_token",
        "refresh_token",
        "id_token",
        "encrypted_tokens",
    }
)

#: Path prefixes the plugin serves. A JSON response here must come from a route the checker can
#: resolve; one that resolves to nothing fails.
PLUGIN_PREFIXES = ("/api/", "/ajax-api/", "/oidc/", "/scim/")

#: ``(method, path)`` pairs on a plugin prefix that may answer without any route matching —
#: intentional exceptions to the rule above, each with the reason.
UNMATCHED_ALLOWED: Dict[Tuple[str, str], str] = {
    ("GET", "/api/2.0/mlflow/not-a-route"): (
        "test_fastapi_permission_middleware: deny-by-default — the auth middleware answers 401 for a path no route serves"
    ),
    ("GET", "/scim/v2x/Users"): ("test_scim_auth: a sibling of the SCIM prefix stays protected — the auth middleware answers 401 before any routing"),
}


class ContractViolation(AssertionError):
    """A response body that does not match the model its route declares, or no route at all."""


#: model -> (adapter, serialization JSON schema); both are costly to build and never change.
_ADAPTERS: Dict[Any, Tuple[TypeAdapter, Dict[str, Any]]] = {}


def _adapter(model: Any) -> Tuple[TypeAdapter, Dict[str, Any]]:
    cached = _ADAPTERS.get(model)
    if cached is None:
        adapter = TypeAdapter(model)
        cached = _ADAPTERS[model] = (adapter, adapter.json_schema(mode="serialization"))
    return cached


def _resolve(app: Any, scope: Dict[str, Any], depth: int = 0) -> Tuple[str, Optional[APIRoute]]:
    """Which route ``app`` dispatches ``scope`` to.

    Returns:
        ``("api", route)`` for a FastAPI route, ``("other", None)`` for anything else that matched
        (a WSGI mount, a plain Starlette route), ``("none", None)`` when nothing matched.
    """
    # Middleware and other ASGI wrappers keep the next app on ``.app``.
    while getattr(app, "routes", None) is None and getattr(app, "app", None) is not None and depth < 32:
        app, depth = app.app, depth + 1
    routes = getattr(app, "routes", None)
    if routes is None:
        return "other", None
    for route in routes:
        match, child_scope = route.matches(scope)
        if match != Match.FULL:
            continue
        if isinstance(route, APIRoute):
            return "api", route
        if isinstance(route, Mount):
            return _resolve(route.app, {**scope, **child_scope}, depth + 1)
        return "other", None
    return "none", None


def _declared_model(route: APIRoute, status_code: int) -> Any:
    """The model ``route`` documents for ``status_code``, or None when it documents none."""
    declared = route.responses.get(status_code) or route.responses.get(str(status_code))
    if isinstance(declared, dict) and declared.get("model") is not None:
        return declared["model"]
    success = route.status_code or 200
    if 200 <= status_code < 300 and status_code in (success, 200, 201):
        return route.response_model
    return None


_KINDS = {
    "null": lambda v: v is None,
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}


def _deref(schema: Dict[str, Any], defs: Dict[str, Any]) -> Dict[str, Any]:
    while "$ref" in schema:
        schema = defs[schema["$ref"].rsplit("/", 1)[-1]]
    return schema


def _same_kind(schema: Dict[str, Any], value: Any) -> bool:
    """Whether ``schema`` describes values of ``value``'s JSON kind (object, array, null, ...)."""
    kind = schema.get("type")
    if kind is None:
        if "properties" in schema or "additionalProperties" in schema:
            return isinstance(value, dict)
        return True
    kinds = kind if isinstance(kind, list) else [kind]
    return any(_KINDS.get(k, lambda v: True)(value) for k in kinds)


def _field_problems(schema: Dict[str, Any], value: Any, defs: Dict[str, Any], where: str) -> List[str]:
    """Undeclared and missing keys of ``value`` against ``schema``, at any depth."""
    schema = _deref(schema, defs)
    for key in ("anyOf", "oneOf"):
        if key in schema:
            candidates = [branch for branch in schema[key] if _same_kind(_deref(branch, defs), value)]
            branches = [_field_problems(branch, value, defs, where) for branch in candidates]
            # The value is fine if a branch of its kind accounts for it. A value of no branch's
            # kind is the strict validation's to reject.
            return min(branches, key=len) if branches and all(branches) else []
    if "allOf" in schema:
        return [problem for branch in schema["allOf"] for problem in _field_problems(branch, value, defs, where)]
    if isinstance(value, dict):
        properties = schema.get("properties")
        problems: List[str] = []
        if properties is not None:
            problems += [f"{where}.{key} (undeclared)" for key in value if key not in properties]
            # The serialization schema lists what every body carries; a missing one is a gap too.
            problems += [f"{where}.{key} (missing)" for key in schema.get("required", []) if key not in value]
            for key, item in value.items():
                if key in properties:
                    problems += _field_problems(properties[key], item, defs, f"{where}.{key}")
        extra = schema.get("additionalProperties")
        if isinstance(extra, dict):
            for key, item in value.items():
                if properties is None or key not in properties:
                    problems += _field_problems(extra, item, defs, f"{where}.{key}")
        return problems
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        return [problem for index, item in enumerate(value) for problem in _field_problems(schema["items"], item, defs, f"{where}[{index}]")]
    return []


def check_body(model: Any, body: bytes, label: str = "body") -> None:
    """Validate a JSON ``body`` against ``model``: strict types, no undeclared or missing fields.

    Raises:
        ContractViolation: When the body does not match.
    """
    adapter, schema = _adapter(model)
    try:
        adapter.validate_json(body, strict=True)
    except ValidationError as exc:
        raise ContractViolation(f"{label} does not match {model!r}:\n{exc}") from None
    problems = _field_problems(schema, json.loads(body), schema.get("$defs", {}), "$")
    if problems:
        raise ContractViolation(f"{label} does not match the fields {model!r} declares: {problems}")


def check_response(app: Any, response: Any, root_path: str = "") -> None:
    """Validate ``response`` against the model its route declares for its status.

    Raises:
        ContractViolation: When the body does not match, or when a JSON response on a plugin
            prefix resolves to no route (and is not a router-level 404/405 or allow-listed).
    """
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type or not response.content:
        return
    request = response.request
    method, path = request.method, request.url.path
    scope = {"type": "http", "path": path, "root_path": root_path, "method": method, "path_params": {}}
    kind, route = _resolve(app, scope)
    label = f"{method} {path} -> {response.status_code}"
    if kind == "none":
        route_path = path[len(root_path) :] if root_path and path.startswith(root_path) else path
        if route_path.startswith(PLUGIN_PREFIXES) and response.status_code not in (404, 405) and (method, route_path) not in UNMATCHED_ALLOWED:
            raise ContractViolation(f"{label}: no route resolves this plugin path, so its body cannot be checked")
        return
    if route is None:
        return
    model = _declared_model(route, response.status_code)
    if model is not None:
        check_body(model, response.content, label)


def _route_of(endpoint: Any) -> Optional[APIRoute]:
    """The plugin route served by ``endpoint``."""
    from mlflow_oidc_auth.routers import get_all_routers
    from mlflow_oidc_auth.routers.workspace_permissions import workspace_permissions_router
    from mlflow_oidc_auth.routers.workspace_regex_permissions import workspace_regex_permissions_router

    for router in [*get_all_routers(), workspace_permissions_router, workspace_regex_permissions_router]:
        for route in router.routes:
            if isinstance(route, APIRoute) and route.endpoint is endpoint:
                return route
    return None


def checked(endpoint: Any) -> Any:
    """Wrap a route handler so a test that awaits it directly gets its response contract-checked.

    The ``JSONResponse`` the handler returns is validated against the model its route declares for
    that status. A handler that returns a model or a plain value (FastAPI serializes those itself,
    validating against ``response_model``) is passed through.
    """
    route = _route_of(endpoint)
    if route is None:
        raise LookupError(f"{endpoint!r} serves no plugin route")

    @functools.wraps(endpoint)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await endpoint(*args, **kwargs)
        media_type = getattr(result, "media_type", None) or ""
        body = getattr(result, "body", None)
        if "json" in media_type and body:
            model = _declared_model(route, result.status_code)
            if model is not None:
                check_body(model, body, f"{endpoint.__name__} -> {result.status_code}")
        return result

    return wrapper


def find_credentials(value: Any, where: str = "$") -> List[str]:
    """Paths of every key in a parsed JSON ``value`` named like a credential, at any depth."""
    found: List[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in CREDENTIAL_PROPERTIES:
                found.append(f"{where}.{key}")
            found += find_credentials(item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found += find_credentials(item, f"{where}[{index}]")
    return found
