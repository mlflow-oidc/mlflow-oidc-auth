"""
Typed authentication context for middleware-to-bridge communication.

Replaces individual environ keys (mlflow_oidc_auth.username, mlflow_oidc_auth.is_admin)
with a single frozen dataclass that carries all auth state through the ASGI → WSGI bridge.
"""

from dataclasses import dataclass


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
