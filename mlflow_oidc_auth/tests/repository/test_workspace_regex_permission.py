"""Tests for WorkspaceRegexPermissionRepository."""

from mlflow_oidc_auth.db.models.workspace import SqlWorkspaceRegexPermission
from mlflow_oidc_auth.repository._base import BaseRegexPermissionRepository
from mlflow_oidc_auth.repository.workspace_regex_permission import (
    WorkspaceRegexPermissionRepository,
)


class TestWorkspaceRegexPermissionRepository:
    """Tests for WorkspaceRegexPermissionRepository class attributes."""

    def test_model_class_is_sql_workspace_regex_permission(self):
        """model_class is SqlWorkspaceRegexPermission."""
        assert (
            WorkspaceRegexPermissionRepository.model_class
            is SqlWorkspaceRegexPermission
        )

    def test_backward_compat_alias_exists(self):
        """_get_workspace_regex_permission alias equals base _get_regex_permission."""
        assert (
            WorkspaceRegexPermissionRepository._get_workspace_regex_permission
            is BaseRegexPermissionRepository._get_regex_permission
        )
