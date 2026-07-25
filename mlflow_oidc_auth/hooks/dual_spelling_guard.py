"""Reject ambiguous requests before any authorization decision (issue #270).

MLflow parses request bodies as proto-JSON.  ``protobuf.ParseDict`` accepts a
field under BOTH its snake_case name AND its lowerCamelCase ``json_name``, and
when both keys appear it silently resolves to the LAST one in JSON order, which
is caller-controlled.  Any authorization check that reads a single spelling of a
field can therefore be bypassed::

    {"experiment_id": "attacker_own", "experimentId": "victim"}

makes the validator authorize ``attacker_own`` (which the caller owns) while
MLflow operates on ``victim``.  The impact spans cross-tenant READ as well as
WRITE/DELETE on every gated mutating route.

No legitimate MLflow client emits a field under two spellings: the Python client
serializes with ``preserving_proto_field_name=True`` (snake_case) and the browser
UI sends snake_case request bodies.  Rejecting a dual-spelling request with 400
therefore cannot break a real client — it only closes the ambiguity an attacker
relies on.

GET requests need care.  MLflow's ``_get_request_message`` builds the proto from
``request.args`` (keyed by snake_case ``field.name``, so camelCase query params
are never read) **only when the query string is non-empty**::

    if flask_request.method == "GET" and flask_request.args:   # args path
        ...
    else:                                                       # body path
        request_json = _get_normalized_request_json(flask_request)
    parse_dict(request_json, request_message)

A GET with an *empty* query string therefore falls through and proto-parses the
JSON **body**, with full dual-spelling semantics.  Worse, validators that read
only ``request.args`` find nothing in such a request and authorize *vacuously*
(no store lookup at all) while MLflow serves whatever the body named.  So a GET
that carries a body MLflow will parse is rejected outright — see
``has_unexpected_get_body``.  No legitimate client sends a GET body; real clients
put GET parameters in the query string, which stays on the safe args path.

The ``(path, method) -> proto class`` map is derived from MLflow's own service
registry via ``get_endpoints``, so it covers every proto endpoint MLflow serves —
current and future — with no manual maintenance.  A few proto-parsing handlers are
registered with ``@app.route`` instead and never appear in that registry, so they
are bound by enumerating the real Flask routing table (see
``_NON_REGISTRY_PROTO_ROUTES``).  The request body is read through MLflow's own
``_get_normalized_request_json`` so the guard inspects exactly the dict MLflow will
``parse_dict`` (force-parsed, double-encoding aware), leaving no room for a
``Content-Type`` evasion.
"""

import re
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple

from flask import Request

from mlflow.protos.service_pb2 import SearchDatasets
from mlflow.server.handlers import get_endpoints, _get_normalized_request_json

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

# A "collidable" field is one whose snake_case name differs from its camelCase
# json_name (i.e. a multi-word field).  Single-word fields have name == json_name
# and cannot be spelled two ways, so they can never collide.
_CollidablePairs = List[Tuple[str, str]]

_EXACT_COLLIDABLE: Dict[Tuple[str, str], _CollidablePairs] = {}
_PATTERN_COLLIDABLE: List[Tuple[Pattern[str], str, _CollidablePairs]] = []

# Every proto-backed route, whether or not it has collidable fields. Used to decide
# whether a GET body would be proto-parsed by MLflow.
_EXACT_PROTO_ROUTES: Set[Tuple[str, str]] = set()
_PATTERN_PROTO_ROUTES: List[Tuple[Pattern[str], str]] = []

# Proto-parsing handlers MLflow registers with @app.route rather than through the
# service registry, so get_endpoints() never yields their live path. MLflow also
# registers malformed twins of some of these ("/api/2.0mlflow/...", missing the
# slash) which DO appear in the registry — binding only those would leave the real
# route unguarded. Enumerating the routing table avoids having to predict spellings.
_NON_REGISTRY_PROTO_ROUTES = (("mlflow/experiments/search-datasets", "POST", SearchDatasets),)


def _re_compile_path(path: str) -> Pattern[str]:
    """Turn a path with ``<param>`` segments into a full-match regex."""
    return re.compile(re.sub(r"<([^>]+)>", r"([^/]+)", path))


def _register_route(http_path: str, methods, descriptor) -> None:
    """Record one route's proto membership and its collidable field pairs."""
    collidable = [(f.name, f.json_name) for f in descriptor.fields if f.name != f.json_name]
    parameterized = "<" in http_path
    compiled = _re_compile_path(http_path) if parameterized else None
    for method in methods:
        if parameterized:
            _PATTERN_PROTO_ROUTES.append((compiled, method))
            if collidable:
                _PATTERN_COLLIDABLE.append((compiled, method, collidable))
        else:
            _EXACT_PROTO_ROUTES.add((http_path, method))
            if collidable:
                _EXACT_COLLIDABLE[(http_path, method)] = collidable


def _bind_non_registry_proto_routes() -> None:
    """Bind proto-parsing routes that MLflow serves outside the service registry."""
    from mlflow.server import app as mlflow_flask_app

    for suffix, method, proto in _NON_REGISTRY_PROTO_ROUTES:
        for rule in mlflow_flask_app.url_map.iter_rules():
            path = str(rule)
            if path.endswith(suffix) and method in (rule.methods or set()):
                _register_route(path, [method], proto.DESCRIPTOR)


def _build_proto_route_maps() -> None:
    """Populate the route maps from MLflow's full proto surface.

    ``get_endpoints(lambda rc: rc)`` yields ``(path, handler, methods)`` for every
    registered endpoint, with the handler being the request proto class for proto
    routes and a plain function (``_graphql``, server-info, scoring, ...) otherwise.
    """
    for http_path, handler, methods in get_endpoints(lambda rc: rc):
        descriptor = getattr(handler, "DESCRIPTOR", None)
        if descriptor is None:
            continue  # non-proto handler
        _register_route(http_path, methods, descriptor)
    _bind_non_registry_proto_routes()


_build_proto_route_maps()


def _assert_maps_populated() -> None:
    """Fail loudly if the route maps came up empty.

    The maps are derived from MLflow's registry rather than hardcoded, so a future
    MLflow release that changes the ``get_endpoints`` handler contract (or stops
    exposing proto classes) would yield empty maps — and this guard would silently
    become a no-op, quietly reopening the cross-tenant bypass it exists to close.
    A security control must not fail open silently, so refuse to start instead.
    MLflow always serves proto routes with multi-word fields (experiment_id, run_id,
    ...), so empty maps mean the derivation broke, never a legitimate state.
    """
    if not _EXACT_COLLIDABLE and not _PATTERN_COLLIDABLE:
        raise RuntimeError(
            "mlflow-oidc-auth: could not derive any proto routes from MLflow's endpoint "
            "registry, so the dual-spelling authorization guard would be inert. This "
            "usually means the installed MLflow version changed the get_endpoints() "
            "contract. Refusing to start rather than run without the guard (issue #270)."
        )


_assert_maps_populated()


def _collidable_fields_for(path: str, method: str) -> Optional[_CollidablePairs]:
    """Return the collidable field pairs for a route, or ``None`` if it has none.

    Exact paths are looked up first (the common case, O(1)); the regex list is
    scanned only for parameterized paths.
    """
    fields = _EXACT_COLLIDABLE.get((path, method))
    if fields is not None:
        return fields
    for compiled, m, collidable in _PATTERN_COLLIDABLE:
        if m == method and compiled.fullmatch(path):
            return collidable
    return None


def _is_proto_route(path: str, method: str) -> bool:
    """True when MLflow will build a proto message for this route."""
    # werkzeug registers HEAD alongside every GET rule and routes it to the same
    # handler, so a HEAD reaches the same proto route as its GET.
    if method == "HEAD":
        method = "GET"
    if (path, method) in _EXACT_PROTO_ROUTES:
        return True
    for compiled, m in _PATTERN_PROTO_ROUTES:
        if m == method and compiled.fullmatch(path):
            return True
    return False


def _request_body(req: Request) -> Optional[Dict[str, Any]]:
    """The dict MLflow will ``parse_dict``, or ``None`` if there isn't one."""
    try:
        data = _get_normalized_request_json(req)
    except Exception:
        # Malformed / wrong-content-type body: MLflow will reject it downstream,
        # so there is nothing for the guard to protect.
        return None
    return data if isinstance(data, dict) else None


def _mlflow_reads_args(req: Request) -> bool:
    """True when MLflow builds the proto from the query string and ignores the body.

    Mirrors ``_get_request_message``: the args path is taken only for a GET whose
    query string is non-empty. Query args are keyed by snake_case ``field.name``,
    so camelCase params are never read and dual spelling is not a vector there.
    """
    return req.method == "GET" and bool(req.args)


def find_dual_spelling_collision(req: Request) -> Optional[str]:
    """Return the snake_case name of a dual-spelled field, or ``None`` if clean."""
    collidable = _collidable_fields_for(req.path, req.method)
    if not collidable:
        return None
    if _mlflow_reads_args(req):
        return None

    data = _request_body(req)
    if not data:
        return None

    keys = data.keys()
    for snake, camel in collidable:
        if snake in keys and camel in keys:
            return snake
    return None


def _snake_to_camel(name: str) -> str:
    """protobuf's ``json_name`` spelling for a snake_case field name."""
    head, *rest = name.split("_")
    return head + "".join(word[:1].upper() + word[1:] for word in rest)


def proto_request_value(req: Request, field: str) -> Tuple[bool, Optional[Any]]:
    """What value will MLflow see for ``field`` on this request?

    Returns ``(route_is_proto, value)``. When ``route_is_proto`` is False the caller
    must fall back to its own heuristics — MLflow serves that route with a plain
    handler whose parameter sourcing this module cannot know.

    Authorization has to read a parameter from the SAME place MLflow will (issue
    #285). ``_get_request_message`` consults the query string only for a GET with a
    non-empty one; every other method is proto-parsed from the BODY and the query
    string is ignored outright. A validator that prefers the query string therefore
    authorizes one resource while MLflow acts on another::

        POST /experiments/update?experiment_id=<own>
        {"experiment_id": "<victim>", "new_name": "PWNED"}

    Reading through the same normalized body the guard inspects means the two cannot
    diverge. Both spellings are accepted on the body path because ``ParseDict`` does:
    a camelCase-only body is unambiguous (``find_dual_spelling_collision`` has already
    rejected the both-spellings case), and MLflow will honour it. Query args are keyed
    by snake_case ``field.name`` only, so no camelCase lookup applies there.
    """
    if not _is_proto_route(req.path, req.method):
        return False, None
    if _mlflow_reads_args(req):
        return True, req.args.get(field)
    data = _request_body(req)
    if not data:
        return True, None
    for key in (field, _snake_to_camel(field)):
        if key in data:
            return True, data[key]
    return True, None


def has_unexpected_get_body(req: Request) -> bool:
    """True for a GET or HEAD that carries a body MLflow will proto-parse.

    With an empty query string MLflow parses the JSON body instead of the args. A
    validator that reads ``request.args`` then finds nothing and authorizes without
    consulting the store at all, while MLflow serves whatever the body named — a
    cross-tenant read that needs no dual spelling. No legitimate client sends a GET
    body (real clients put GET parameters in the query string), so reject it.

    HEAD is asymmetric and must not be exempted by a query string: MLflow's
    ``_get_request_message`` takes ``request.args`` only when the method is literally
    "GET", so a HEAD is ALWAYS proto-parsed from the body. Without this a request could
    carry ``?path=<own>`` for the validator while the body named another tenant — the
    stripped response still leaks an exact Content-Length oracle over their artifacts.
    """
    if req.method not in ("GET", "HEAD"):
        return False
    if req.method == "GET" and req.args:
        return False
    if not _is_proto_route(req.path, req.method):
        return False
    return bool(_request_body(req))
