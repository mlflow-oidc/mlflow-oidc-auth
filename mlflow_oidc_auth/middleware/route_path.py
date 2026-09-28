"""
Routed-path helpers shared by the authentication and permission middleware.

Authorization decisions are made on the path the router dispatches, not on the raw request
path. Starlette routes on ``scope["path"]`` with a matching ``scope["root_path"]`` removed (the
prefix an ASGI server or ``ProxyHeadersMiddleware`` records for a deployment served under a
sub-path). Deciding on anything else lets the middleware and the router disagree about which
endpoint a request reaches, so every check in this package goes through :func:`routed_path`.
"""

from typing import Any, Mapping

try:  # pragma: no cover - exercised implicitly on every supported Starlette version
    from starlette._utils import get_route_path as _starlette_get_route_path
except ImportError:  # pragma: no cover - fallback if Starlette moves the private helper
    _starlette_get_route_path = None


def _get_route_path(scope: Mapping[str, Any]) -> str:
    """Strip a matching ``root_path`` from ``path`` exactly as Starlette's router does.

    Used only when Starlette's own helper is not importable. Kept identical to it, and a test
    compares the two, so the routed path never diverges from the router's.

    Parameters:
        scope: ASGI connection scope.

    Returns:
        The path the router matches routes against.
    """
    path: str = scope["path"]
    root_path = scope.get("root_path", "")
    if not root_path or not path.startswith(root_path):
        return path
    if path == root_path:
        return ""
    if path[len(root_path)] == "/":
        return path[len(root_path) :]
    return path


def routed_path(scope: Mapping[str, Any]) -> str:
    """Return the path the router will dispatch this request on.

    Parameters:
        scope: ASGI connection scope.

    Returns:
        The routed path, always starting with ``/`` (a request for exactly the root path
        routes as ``/``).
    """
    getter = _starlette_get_route_path or _get_route_path
    path = getter(scope)  # type: ignore[arg-type]
    return path or "/"


# Paths that do not require an authenticated user. See ``AuthMiddleware`` for what each one is.
UNPROTECTED_PREFIXES = (
    "/health",
    "/login",
    "/callback",
    "/oidc/static",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/oidc/ui",
    # MLflow's React bundle is served from /static-files/<path:path> with
    # content-addressed (hashed) filenames and ships publicly on PyPI.
    # Letting it load unauthenticated lets a session-expired SPA finish
    # loading chunks instead of dying with ChunkLoadError; the next
    # navigation will redirect through the IdP for re-auth.
    "/static-files",
    # SCIM 2.0 (#321). Not unauthenticated: every route under it depends on
    # ``require_scim_token``, a dedicated credential this chain does not understand, and a
    # catch-all keeps anything unmatched from reaching the Flask mount. Carved out so that
    # a user session or token can never authenticate a directory write. The trailing
    # slash keeps a sibling such as "/scim/v2x" protected.
    "/scim/v2/",
    # SAML single logout and SP metadata (#328, #329). The IdP calls the first with no
    # session of ours — that is the point of IdP-initiated logout — and every message it
    # accepts must carry the IdP's signature. The second is public by nature: entity id,
    # endpoint URLs and a public certificate. Trailing slashes keep "/slox" protected.
    "/slo/",
    "/saml/metadata/",
)

# Matched exactly rather than by prefix. A login page has to read this before anyone has
# signed in — it is the list of buttons to draw — but "/providers" as a prefix would
# silently unprotect any later route whose path merely began with it.
UNPROTECTED_EXACT = ("/providers",)


def is_unprotected_route(path: str) -> bool:
    """Return True when ``path`` does not require an authenticated user.

    Parameters:
        path: The routed path (see :func:`routed_path`), never the raw request path.

    Returns:
        True if the route is unprotected, False otherwise.
    """
    return path in UNPROTECTED_EXACT or path.startswith(UNPROTECTED_PREFIXES)
