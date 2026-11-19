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

    This is only the workspace the request's ``X-MLFLOW-WORKSPACE`` header names. Callers that
    decide what a request may do use :func:`get_authorization_workspace` instead.

    Returns:
        Workspace name if workspaces are enabled and header was present, None otherwise.
    """
    try:
        return get_auth_context().workspace
    except Exception:
        return None


def get_authorization_workspace() -> str | None:
    """The workspace a permission decision for the current request is made in.

    That is the workspace the request's header names. A request without the header gets None,
    unless MLflow serves it from the process-wide ``MLFLOW_WORKSPACE`` environment variable.

    The variable is normally unset on a server, but MLflow's ``WorkspaceContext`` sets it for the
    whole process while it runs. Its admin-only demo generation does, for several seconds. Flask
    requests run on several threads (``WSGI_THREADS``), so a header-less request can run
    meanwhile. When MLflow resolved no workspace for that request (a workspace provider without a
    default workspace), MLflow's ``get_request_workspace()`` falls back to the variable and serves
    the request from the other request's workspace. If the permission decision saw None there, it
    would skip the workspace membership checks (issue #482).

    Header-only callers keep :func:`get_request_workspace`: the scope of a new regex pattern, where
    None means every workspace, and the rule that a creation must name its workspace.

    Returns:
        The workspace name, or None for a request that names none and is not served from the
        variable, when workspaces are disabled, or without an authentication context.
    """
    return get_request_workspace() or _environment_served_workspace()


def _environment_served_workspace() -> str | None:
    """The workspace MLflow serves a header-less request from, when that is ``MLFLOW_WORKSPACE``.

    Returns:
        The variable's value when workspaces are enabled, MLflow resolved no workspace for this
        request, and MLflow resolves it to the variable. None otherwise: a workspace MLflow
        resolved for the request itself, such as the provider's default workspace, keeps the
        header-less behaviour.
    """
    from mlflow_oidc_auth.config import config

    if not config.MLFLOW_ENABLE_WORKSPACES:
        return None
    from mlflow.environment_variables import MLFLOW_WORKSPACE
    from mlflow.utils import workspace_context

    env_workspace = (MLFLOW_WORKSPACE.get() or "").strip()
    if not env_workspace:
        return None
    # MLflow keeps the request's own workspace in a private ContextVar. Without it (a future
    # MLflow), the comparison below still holds, but it also takes a request whose own workspace
    # equals the variable.
    request_var = getattr(workspace_context, "_WORKSPACE", None)
    if request_var is not None and (request_var.get() or "").strip():
        return None
    if workspace_context.get_request_workspace() == env_workspace:
        return env_workspace
    return None
