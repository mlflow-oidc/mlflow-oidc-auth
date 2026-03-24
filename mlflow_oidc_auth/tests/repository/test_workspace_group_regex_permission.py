"""Tests for WorkspaceGroupRegexPermissionRepository."""

from mlflow_oidc_auth.db.models.workspace import SqlWorkspaceGroupRegexPermission
from mlflow_oidc_auth.repository._base import BaseGroupRegexPermissionRepository
from mlflow_oidc_auth.repository.workspace_group_regex_permission import (
    WorkspaceGroupRegexPermissionRepository,
)


class TestWorkspaceGroupRegexPermissionRepository:
    """Tests for WorkspaceGroupRegexPermissionRepository class attributes."""

    def test_model_class_is_sql_workspace_group_regex_permission(self):
        """model_class is SqlWorkspaceGroupRegexPermission."""
        assert (
            WorkspaceGroupRegexPermissionRepository.model_class
            is SqlWorkspaceGroupRegexPermission
        )

    def test_backward_compat_alias_exists(self):
        """_get_workspace_group_regex_permission alias equals base _get_group_regex_permission."""
        assert (
            WorkspaceGroupRegexPermissionRepository._get_workspace_group_regex_permission
            is BaseGroupRegexPermissionRepository._get_group_regex_permission
        )
