"""
Flask Hooks Bridge - Compatibility Layer for Flask Hooks with FastAPI Auth

Provides functions to retrieve authentication context from Flask's WSGI environ,
where it was injected by AuthAwareWSGIMiddleware from FastAPI's ASGI scope.

For FastAPI-native routes (OTel traces, gateway, etc.) that never enter Flask,
a ContextVar fallback allows the same bridge functions to work when the
FastAPI permission middleware sets the AuthContext before running validators.
"""

from contextvars import ContextVar, Token

from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

_auth_context_var: ContextVar[AuthContext | None] = ContextVar("_auth_context_var", default=None)


def set_auth_context(ctx: AuthContext) -> Token:
    """Set AuthContext in the ContextVar for non-Flask contexts (FastAPI-native routes).

    Returns:
        The token to hand back to :func:`clear_auth_context` so the previous value is restored.
    """
    return _auth_context_var.set(ctx)


def clear_auth_context(token: Token | None = None) -> None:
    """Clear the ContextVar after request processing.

    Parameters:
        token: The token returned by :func:`set_auth_context`. When given, the variable is
            restored to whatever it held before that call; without it the variable is blanked.
    """
    if token is not None:
        _auth_context_var.reset(token)
    else:
        _auth_context_var.set(None)


def get_auth_context() -> AuthContext:
    """Get the full AuthContext from Flask request environ or ContextVar fallback.

    Checks Flask's WSGI environ first (for routes that pass through
    AuthAwareWSGIMiddleware), then falls back to the ContextVar (for
    FastAPI-native routes where the permission middleware sets it).

    Returns:
        AuthContext object containing username, is_admin, and workspace.

    Raises:
        Exception: If AuthContext is not available from either source.
    """
    try:
        from flask import request

        if hasattr(request, "environ"):
            auth_context = request.environ.get(AUTH_CONTEXT_KEY)
            if isinstance(auth_context, AuthContext):
                logger.debug(f"Retrieved AuthContext from Flask environ: {auth_context.username}")
                return auth_context
    except Exception as e:
        logger.debug(f"Could not access AuthContext from Flask request: {e}")

    ctx = _auth_context_var.get()
    if isinstance(ctx, AuthContext):
        logger.debug(f"Retrieved AuthContext from ContextVar: {ctx.username}")
        return ctx

    raise Exception("Could not retrieve AuthContext")


def get_fastapi_username() -> str:
    """Get username from the current authentication context.

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
        logger.debug("AuthContext unavailable when resolving username")
    raise Exception("Could not retrieve FastAPI username")


def get_fastapi_admin_status() -> bool:
    """Get admin status from the current authentication context.

    Returns:
        True if user is admin, False otherwise.
    """
    try:
        return get_auth_context().is_admin
    except Exception:
        return False


def get_request_workspace() -> str | None:
    """Get the current workspace from the authentication context.

    Returns:
        Workspace name if workspaces are enabled and header was present, None otherwise.
    """
    try:
        return get_auth_context().workspace
    except Exception:
        return None
