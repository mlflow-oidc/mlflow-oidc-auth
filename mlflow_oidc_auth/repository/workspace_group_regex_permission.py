"""Workspace group regex permission repository."""

from mlflow_oidc_auth.db.models.workspace import SqlWorkspaceGroupRegexPermission
from mlflow_oidc_auth.entities.workspace import WorkspaceGroupRegexPermission
from mlflow_oidc_auth.repository._base import BaseGroupRegexPermissionRepository


class WorkspaceGroupRegexPermissionRepository(
    BaseGroupRegexPermissionRepository[
        SqlWorkspaceGroupRegexPermission, WorkspaceGroupRegexPermission
    ]
):
    model_class = SqlWorkspaceGroupRegexPermission

    # -- Backward-compatible alias for the private helper ---------------------
    _get_workspace_group_regex_permission = (
        BaseGroupRegexPermissionRepository._get_group_regex_permission
    )
