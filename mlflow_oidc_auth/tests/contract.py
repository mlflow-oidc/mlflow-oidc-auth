"""Enforce the OpenAPI contract on every response a test receives (#458).

The plugin's handlers mostly build their own ``JSONResponse``, which FastAPI returns as is: the
``response_model`` a route declares documents the body but is never checked against it. This module
closes that gap in the test suite. ``check_response`` takes a response from a FastAPI app and, when
the matched route declares a model for that status code, validates the body against it:

- strictly — a string is not accepted for an integer, nor an integer for a string;
- with no undocumented fields — a key the model does not declare fails, at any depth. A new field
  added to a body without the contract (a hash, a full session id) fails the build rather than
  reaching the UI unannounced;
- with every field the serialization schema requires present, so a field the contract promises
  is always sent cannot quietly go missing.

``tests/conftest.py`` applies it to every ``TestClient`` request in the suite. When a body and its
model disagree, fix the model — unless the body is the bug (it leaks something).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi.routing import APIRoute
from pydantic import TypeAdapter, ValidationError
from starlette.routing import Match


class ContractViolation(AssertionError):
    """A response body that does not match the model its route declares."""


_ADAPTERS: Dict[Any, TypeAdapter] = {}

#: ``(method, route path, status)`` of every response checked in this process, for coverage reports.
CHECKED: set = set()


def _adapter(model: Any) -> TypeAdapter:
    adapter = _ADAPTERS.get(model)
    if adapter is None:
        adapter = _ADAPTERS[model] = TypeAdapter(model)
    return adapter


def _route_for(app: Any, method: str, path: str) -> Optional[APIRoute]:
    """The APIRoute ``app`` dispatches ``method path`` to, or None."""
    routes = getattr(app, "routes", None)
    if routes is None:
        return None
    scope = {"type": "http", "path": path, "method": method, "root_path": "", "path_params": {}}
    for route in routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route if isinstance(route, APIRoute) else None
    return None


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


def _resolve(schema: Dict[str, Any], defs: Dict[str, Any]) -> Dict[str, Any]:
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


def _undocumented_fields(schema: Dict[str, Any], value: Any, defs: Dict[str, Any], where: str) -> List[str]:
    """Paths of keys in ``value`` that ``schema`` does not declare, at any depth."""
    if "$ref" in schema:
        return _undocumented_fields(defs[schema["$ref"].rsplit("/", 1)[-1]], value, defs, where)
    for key in ("anyOf", "oneOf"):
        if key in schema:
            candidates = [branch for branch in schema[key] if _same_kind(_resolve(branch, defs), value)]
            branches = [_undocumented_fields(branch, value, defs, where) for branch in candidates]
            # The value is fine if a branch of its kind accounts for every key in it. A value of no
            # branch's kind is the strict validation's to reject.
            return min(branches, key=len) if branches and all(branches) else []
    if "allOf" in schema:
        return [problem for branch in schema["allOf"] for problem in _undocumented_fields(branch, value, defs, where)]
    if isinstance(value, dict):
        properties = schema.get("properties")
        problems: List[str] = []
        if properties is not None:
            problems += [f"{where}.{key} (undeclared)" for key in value if key not in properties]
            # The serialization schema lists what every body carries; a missing one is a gap too.
            problems += [f"{where}.{key} (missing)" for key in schema.get("required", []) if key not in value]
            for key, item in value.items():
                if key in properties:
                    problems += _undocumented_fields(properties[key], item, defs, f"{where}.{key}")
        extra = schema.get("additionalProperties")
        if isinstance(extra, dict):
            for key, item in value.items():
                if properties is None or key not in properties:
                    problems += _undocumented_fields(extra, item, defs, f"{where}.{key}")
        return problems
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        return [problem for index, item in enumerate(value) for problem in _undocumented_fields(schema["items"], item, defs, f"{where}[{index}]")]
    return []


def check_body(model: Any, body: bytes, label: str = "body") -> None:
    """Validate a JSON ``body`` against ``model``: strict types, no undocumented fields.

    Raises:
        ContractViolation: When the body does not match.
    """
    adapter = _adapter(model)
    try:
        adapter.validate_json(body, strict=True)
    except ValidationError as exc:
        raise ContractViolation(f"{label} does not match {model!r}:\n{exc}") from None
    schema = adapter.json_schema(mode="serialization")
    undocumented = _undocumented_fields(schema, json.loads(body), schema.get("$defs", {}), "$")
    if undocumented:
        raise ContractViolation(f"{label} does not match the fields {model!r} declares: {undocumented}")


def check_response(app: Any, response: Any) -> None:
    """Validate ``response`` against the model its route declares for its status, if any.

    Non-JSON responses, routes outside FastAPI's router and statuses with no declared model are
    left alone.
    """
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type or not response.content:
        return
    request = response.request
    route = _route_for(app, request.method, request.url.path)
    if route is None:
        return
    model = _declared_model(route, response.status_code)
    if model is None:
        return
    check_body(model, response.content, f"{request.method} {request.url.path} -> {response.status_code}")
    CHECKED.add((request.method, route.path, response.status_code))


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
    """Wrap a route handler so a test calling it directly gets its response contract-checked.

    For tests that await a handler rather than going through ``TestClient``: the ``JSONResponse``
    it returns is validated against the model its route declares for that status.
    """
    import functools

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
                CHECKED.add((sorted(route.methods)[0], route.path, result.status_code))
        return result

    return wrapper
