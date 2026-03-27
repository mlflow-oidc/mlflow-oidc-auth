"""
Flask Hooks Bridge - Compatibility Layer for Flask Hooks with FastAPI Auth

Provides functions to retrieve authentication context from Flask's WSGI environ,
where it was injected by AuthAwareWSGIMiddleware from FastAPI's ASGI scope.
"""

from mlflow_oidc_auth.entities.auth_context import AuthContext
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


def get_auth_context() -> AuthContext:
    """Get the full AuthContext from Flask request environ.

    Returns:
        AuthContext object containing username, is_admin, and workspace.

    Raises:
        Exception: If AuthContext is not available in the environ.
    """
    try:
        from flask import request

        if hasattr(request, "environ"):
            auth_context = request.environ.get("mlflow_oidc_auth")
            if isinstance(auth_context, AuthContext):
                logger.debug(f"Retrieved AuthContext from Flask environ: {auth_context.username}")
                return auth_context
    except Exception as e:
        logger.debug(f"Could not access AuthContext from Flask request: {e}")

    raise Exception("Could not retrieve AuthContext")


def get_fastapi_username() -> str:
    """Get username from FastAPI authentication context via Flask request environ.

    Returns:
        Username if authenticated.

    Raises:
        Exception: If username is not available.
    """
    try:
        ctx = get_auth_context()
        if ctx.username:
            return ctx.username
    except Exception:
        pass
    raise Exception("Could not retrieve FastAPI username")


def get_fastapi_admin_status() -> bool:
    """Get admin status from FastAPI authentication context via Flask request environ.

    Returns:
        True if user is admin, False otherwise.
    """
    try:
        return get_auth_context().is_admin
    except Exception:
        return False


def get_request_workspace() -> str | None:
    """Get the current workspace from Flask request environ.

    Returns:
        Workspace name if workspaces are enabled and header was present, None otherwise.
    """
    try:
        return get_auth_context().workspace
    except Exception:
        return None
