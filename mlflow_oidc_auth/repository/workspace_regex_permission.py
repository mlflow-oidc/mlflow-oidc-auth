"""Workspace regex permission repository."""

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.db.models.workspace import SqlWorkspaceRegexPermission
from mlflow_oidc_auth.entities.workspace import WorkspaceRegexPermission
from mlflow_oidc_auth.repository._base import BaseRegexPermissionRepository


class WorkspaceRegexPermissionRepository(BaseRegexPermissionRepository[SqlWorkspaceRegexPermission, WorkspaceRegexPermission]):
    grant_kind = permission_kinds.WORKSPACE

    # -- Backward-compatible alias for the private helper ---------------------
    _get_workspace_regex_permission = BaseRegexPermissionRepository._get_regex_permission
