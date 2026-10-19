"""Route class for the group permission routes: the group name is exactly one path segment.

A group name may contain "/" — Keycloak sends full paths such as ``/data-science`` — and clients
send it percent-encoded as ``%2F``. Starlette routes on the decoded path, where that ``%2F`` is
already a "/", so a ``{group_name:path}`` parameter cannot tell a "/" inside the name from one
that ends it: ``/groups/x%2Fprompts/prompts/p`` reads equally as group ``x/prompts`` and as group
``x`` with prompt ``prompts/p``, and whichever route is registered first decides which group's
grants are read or changed.

Routes of this class match on the path as the client sent it instead (``raw_path``), with every
segment decoded except "/" and "%", which stay percent-encoded. ``{group_name}`` then matches one
segment only, an encoded "/" never separates, and the route's own path parameters are decoded
once matched. When ``raw_path`` is missing, or no longer decodes to ``path`` because something
rewrote the path, the route matches nothing: the decoded path is exactly where a group name could
be read as another group's.

The ``root_path`` a proxy forwards is stripped exactly as the middleware strips it
(:func:`~mlflow_oidc_auth.middleware.route_path.routed_path`, on the decoded path), so the router and
the authentication and permission middleware always decide on the same route.
"""

from typing import Optional, Tuple
from urllib.parse import unquote

from fastapi.routing import APIRoute
from starlette.routing import Match
from starlette.types import Scope

from mlflow_oidc_auth.middleware.route_path import routed_path

# The router tries every group route in turn on the same scope: work the path out once per request.
_CACHE_KEY = "mlflow_oidc_auth.segment_preserving_path"


def segment_preserving_path(scope: Scope) -> Optional[str]:
    """Return the routed path of ``scope`` decoded segment by segment, with "/" and "%" left percent-encoded.

    The ``root_path`` is removed first, from the decoded path, as ``routed_path`` removes it for the
    middleware; the rest is rebuilt from the same segments of ``raw_path``.

    Parameters:
        scope: The ASGI HTTP scope.

    Returns:
        The routed path to match on, or None when ``raw_path`` is missing, does not decode to
        ``scope["path"]``, or the ``root_path`` ends inside one of its segments.
    """
    key = (scope.get("raw_path"), scope["path"], scope.get("root_path"))
    cached = scope.get(_CACHE_KEY)
    if cached is not None and cached[0] == key:
        return cached[1]
    result = _segment_preserving_path(scope)
    scope[_CACHE_KEY] = (key, result)
    return result


def _segment_preserving_path(scope: Scope) -> Optional[str]:
    raw_path = scope.get("raw_path")
    if not raw_path:
        return None
    try:
        raw = raw_path.decode("utf-8")
    except UnicodeDecodeError:
        return None
    path = scope["path"]
    route_path = routed_path(scope)
    if "%" not in raw:
        # Nothing was encoded, so nothing needs keeping encoded: the common case, and cheap.
        return route_path if raw == path else None
    decoded = [unquote(segment) for segment in raw.split("/")]
    if "/".join(decoded) != path or not path.endswith(route_path):
        return None
    root = path[: len(path) - len(route_path)]
    for count in range(1, len(decoded) + 1):
        if "/".join(decoded[:count]) == root:
            return "/" + "/".join(segment.replace("%", "%25").replace("/", "%2F") for segment in decoded[count:])
    return None


class GroupNameRoute(APIRoute):
    """An ``APIRoute`` that matches ``{group_name}`` as one segment of the path as sent (see the module docstring)."""

    def matches(self, scope: Scope) -> Tuple[Match, Scope]:
        if scope["type"] != "http" or "group_name" not in self.param_convertors:
            # A route of a group router without a group name in it has nothing to keep apart.
            return super().matches(scope)
        path = segment_preserving_path(scope)
        if path is None:
            return Match.NONE, {}
        # Already routed: no root_path left to strip from it.
        match, child_scope = super().matches({**scope, "path": path, "root_path": ""})
        if match != Match.NONE:
            params = child_scope["path_params"]
            # Only this route's own parameters were matched on the encoded path; anything an
            # enclosing scope supplied is decoded already.
            child_scope["path_params"] = {key: unquote(value) if key in self.param_convertors else value for key, value in params.items()}
        return match, child_scope
