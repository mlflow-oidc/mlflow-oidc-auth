"""Workspace permission validators for before_request hooks.

All validators follow the standard bool contract used throughout the codebase:
return True to allow the request, False to deny (403 Forbidden).
"""

from flask import request

from mlflow_oidc_auth.bridge.user import get_auth_context
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached

logger = get_logger()


def _extract_workspace_name_from_path() -> str | None:
    """Extract workspace_name from Flask request path.

    Workspace paths: /api/3.0/mlflow/workspaces/<workspace_name>
    or: /ajax-api/3.0/mlflow/workspaces/<workspace_name>
    """
    parts = request.path.split("/mlflow/workspaces/")
    if len(parts) == 2 and parts[1]:
        # Remove trailing slash and any further path segments
        return parts[1].rstrip("/").split("/")[0]
    return None


def validate_can_create_workspace(username: str) -> bool:
    """Only admins can create workspaces."""
    auth_context = get_auth_context()
    return auth_context.is_admin


def validate_can_read_workspace(username: str) -> bool:
    """User must have any workspace permission to view workspace details."""
    auth_context = get_auth_context()
    if auth_context.is_admin:
        return True
    workspace_name = _extract_workspace_name_from_path()
    if workspace_name is None:
        return False
    perm = get_workspace_permission_cached(auth_context.username, workspace_name)
    return perm is not None


def validate_can_update_workspace(username: str) -> bool:
    """Admins or users with MANAGE workspace permission can update workspaces."""
    auth_context = get_auth_context()
    if auth_context.is_admin:
        return True
    workspace_name = _extract_workspace_name_from_path()
    if workspace_name is None:
        return False
    perm = get_workspace_permission_cached(auth_context.username, workspace_name)
    return perm is not None and perm.can_manage


def validate_can_delete_workspace(username: str) -> bool:
    """Admins or users with MANAGE workspace permission can delete workspaces."""
    auth_context = get_auth_context()
    if auth_context.is_admin:
        return True
    workspace_name = _extract_workspace_name_from_path()
    if workspace_name is None:
        return False
    perm = get_workspace_permission_cached(auth_context.username, workspace_name)
    return perm is not None and perm.can_manage


def validate_can_list_workspaces(username: str) -> bool:
    """All authenticated users can list workspaces (filtered in after_request)."""
    return True
