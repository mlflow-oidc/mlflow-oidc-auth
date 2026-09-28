"""
Typed authentication context for middleware-to-bridge communication.

Replaces individual environ keys (mlflow_oidc_auth.username, mlflow_oidc_auth.is_admin)
with a single frozen dataclass that carries all auth state through the ASGI → WSGI bridge.
"""

from dataclasses import dataclass

#: Key used to store/retrieve AuthContext in both ASGI scope and WSGI environ.
#: AuthMiddleware sets scope[AUTH_CONTEXT_KEY], AuthAwareWSGIMiddleware copies it
#: to environ[AUTH_CONTEXT_KEY], and bridge functions read from environ[AUTH_CONTEXT_KEY].
AUTH_CONTEXT_KEY = "mlflow_oidc_auth"

#: How AuthMiddleware authenticated a request, on ``request.state.auth_method`` (issue #189): a
#: server-side browser session, an IdP-issued bearer token, a workload token from a non-interactive
#: provider (a Kubernetes service account, a CI workload-identity issuer), or
#: HTTP basic auth with one of our own access tokens. ``require_interactive_login`` reads it.
AUTH_METHOD_SESSION = "session"
AUTH_METHOD_BEARER = "bearer"
AUTH_METHOD_WORKLOAD = "workload"
AUTH_METHOD_BASIC = "basic"


@dataclass(frozen=True)
class AuthContext:
    """Authentication context propagated through the middleware chain.

    Set by AuthMiddleware in ASGI scope, passed through AuthAwareWSGIMiddleware
    to Flask environ, and read by bridge functions.

    Attributes:
        username: Authenticated user's username/email.
        is_admin: Whether the user has admin privileges.
        workspace: Current workspace from X-MLFLOW-WORKSPACE header, or None if
                   workspaces are disabled or header not present.
    """

    username: str
    is_admin: bool
    workspace: str | None = None
