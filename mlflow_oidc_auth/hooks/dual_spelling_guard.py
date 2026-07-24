"""Reject requests that carry one proto field under two spellings (issue #270).

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

The ``(path, method) -> proto class`` map is derived directly from MLflow's own
service registry via ``get_endpoints``, so it covers every proto endpoint MLflow
serves — current and future — with no manual maintenance.  The request body is
read through MLflow's own ``_get_normalized_request_json`` so the guard inspects
exactly the dict MLflow will ``parse_dict`` (force-parsed, double-encoding aware),
leaving no room for a ``Content-Type`` evasion.
"""

import re
from typing import List, Optional, Pattern, Tuple

from flask import Request

from mlflow.server.handlers import get_endpoints, _get_normalized_request_json

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

# A "collidable" field is one whose snake_case name differs from its camelCase
# json_name (i.e. a multi-word field).  Single-word fields have name == json_name
# and cannot be spelled two ways, so they can never collide.
_CollidablePairs = List[Tuple[str, str]]

_EXACT_COLLIDABLE: dict[Tuple[str, str], _CollidablePairs] = {}
_PATTERN_COLLIDABLE: List[Tuple[Pattern[str], str, _CollidablePairs]] = []


def _re_compile_path(path: str) -> Pattern[str]:
    """Turn a path with ``<param>`` segments into a full-match regex."""
    return re.compile(re.sub(r"<([^>]+)>", r"([^/]+)", path))


def _build_proto_route_maps() -> None:
    """Populate the collidable-field maps from MLflow's full proto surface.

    ``get_endpoints(lambda rc: rc)`` yields ``(path, handler, methods)`` for every
    registered endpoint, with the handler being the request proto class for proto
    routes and a plain function (``_graphql``, server-info, scoring, ...) otherwise.
    We keep only proto handlers that actually have collidable fields.
    """
    for http_path, handler, methods in get_endpoints(lambda rc: rc):
        descriptor = getattr(handler, "DESCRIPTOR", None)
        if descriptor is None:
            continue  # non-proto handler
        collidable = [(f.name, f.json_name) for f in descriptor.fields if f.name != f.json_name]
        if not collidable:
            continue
        if "<" in http_path:
            compiled = _re_compile_path(http_path)
            for method in methods:
                _PATTERN_COLLIDABLE.append((compiled, method, collidable))
        else:
            for method in methods:
                _EXACT_COLLIDABLE[(http_path, method)] = collidable


_build_proto_route_maps()


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


def find_dual_spelling_collision(req: Request) -> Optional[str]:
    """Return the snake_case name of a dual-spelled field, or ``None`` if clean.

    Only the request body is inspected: on GET, MLflow builds the proto solely
    from ``request.args`` keyed by ``field.name`` (snake_case), so a camelCase
    query parameter is never read and no dual-spelling vector exists there.
    """
    collidable = _collidable_fields_for(req.path, req.method)
    if not collidable:
        return None
    if req.method == "GET":
        return None

    try:
        data = _get_normalized_request_json(req)
    except Exception:
        # Malformed / wrong-content-type body: MLflow will reject it downstream,
        # so there is nothing for the guard to protect.
        return None
    if not isinstance(data, dict):
        return None

    keys = data.keys()
    for snake, camel in collidable:
        if snake in keys and camel in keys:
            return snake
    return None
