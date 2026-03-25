"""Tests for workspace permission validators."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from mlflow_oidc_auth.entities.auth_context import AuthContext

_app = Flask(__name__)
_app.secret_key = "test_secret_key"

# Mock config with workspaces enabled — applied to all tests unless overridden
_mock_config = MagicMock()
_mock_config.MLFLOW_ENABLE_WORKSPACES = True


def _make_auth_context(username="testuser", is_admin=False, workspace=None):
    return AuthContext(username=username, is_admin=is_admin, workspace=workspace)


class TestExtractWorkspaceNameFromPath:
    """Tests for _extract_workspace_name_from_path."""

    def test_extracts_workspace_from_api_path(self):
        """Extract workspace_name from /api/3.0/mlflow/workspaces/<name>."""
        from mlflow_oidc_auth.validators.workspace import (
            _extract_workspace_name_from_path,
        )

        mock_request = MagicMock()
        mock_request.path = "/api/3.0/mlflow/workspaces/my-workspace"
        with patch("mlflow_oidc_auth.validators.workspace.request", mock_request):
            result = _extract_workspace_name_from_path()
            assert result == "my-workspace"

    def test_extracts_workspace_from_ajax_path(self):
        """Extract workspace_name from /ajax-api/3.0/mlflow/workspaces/<name>."""
        from mlflow_oidc_auth.validators.workspace import (
            _extract_workspace_name_from_path,
        )

        mock_request = MagicMock()
        mock_request.path = "/ajax-api/3.0/mlflow/workspaces/another-ws"
        with patch("mlflow_oidc_auth.validators.workspace.request", mock_request):
            result = _extract_workspace_name_from_path()
            assert result == "another-ws"

    def test_returns_none_for_list_path(self):
        """Returns None for /api/3.0/mlflow/workspaces (no name segment)."""
        from mlflow_oidc_auth.validators.workspace import (
            _extract_workspace_name_from_path,
        )

        mock_request = MagicMock()
        mock_request.path = "/api/3.0/mlflow/workspaces"
        with patch("mlflow_oidc_auth.validators.workspace.request", mock_request):
            result = _extract_workspace_name_from_path()
            assert result is None

    def test_strips_trailing_slash(self):
        """Strips trailing slash from workspace name."""
        from mlflow_oidc_auth.validators.workspace import (
            _extract_workspace_name_from_path,
        )

        mock_request = MagicMock()
        mock_request.path = "/api/3.0/mlflow/workspaces/ws-name/"
        with patch("mlflow_oidc_auth.validators.workspace.request", mock_request):
            result = _extract_workspace_name_from_path()
            assert result == "ws-name"

    def test_returns_none_for_unrelated_path(self):
        """Returns None for paths not containing /mlflow/workspaces/."""
        from mlflow_oidc_auth.validators.workspace import (
            _extract_workspace_name_from_path,
        )

        mock_request = MagicMock()
        mock_request.path = "/api/2.0/mlflow/experiments/get"
        with patch("mlflow_oidc_auth.validators.workspace.request", mock_request):
            result = _extract_workspace_name_from_path()
            assert result is None


@patch("mlflow_oidc_auth.validators.workspace.config", _mock_config)
class TestValidateCanCreateWorkspace:
    """Tests for validate_can_create_workspace."""

    def test_returns_false_for_non_admin(self):
        """Non-admin users are denied (returns False)."""
        from mlflow_oidc_auth.validators.workspace import validate_can_create_workspace

        ctx = _make_auth_context(is_admin=False)
        with _app.test_request_context():
            with patch(
                "mlflow_oidc_auth.validators.workspace.get_auth_context",
                return_value=ctx,
            ):
                result = validate_can_create_workspace("testuser")
                assert result is False

    def test_returns_true_for_admin(self):
        """Admin users are allowed (returns True)."""
        from mlflow_oidc_auth.validators.workspace import validate_can_create_workspace

        ctx = _make_auth_context(is_admin=True)
        with _app.test_request_context():
            with patch(
                "mlflow_oidc_auth.validators.workspace.get_auth_context",
                return_value=ctx,
            ):
                result = validate_can_create_workspace("adminuser")
                assert result is True

    def test_returns_false_when_workspaces_disabled(self):
        """Returns False when MLFLOW_ENABLE_WORKSPACES is disabled."""
        from mlflow_oidc_auth.validators.workspace import validate_can_create_workspace

        disabled_config = MagicMock()
        disabled_config.MLFLOW_ENABLE_WORKSPACES = False
        with patch("mlflow_oidc_auth.validators.workspace.config", disabled_config):
            result = validate_can_create_workspace("adminuser")
            assert result is False


@patch("mlflow_oidc_auth.validators.workspace.config", _mock_config)
class TestValidateCanReadWorkspace:
    """Tests for validate_can_read_workspace."""

    def test_returns_true_for_admin(self):
        """Admin users bypass permission check."""
        from mlflow_oidc_auth.validators.workspace import validate_can_read_workspace

        ctx = _make_auth_context(is_admin=True)
        with _app.test_request_context():
            with patch(
                "mlflow_oidc_auth.validators.workspace.get_auth_context",
                return_value=ctx,
            ):
                result = validate_can_read_workspace("adminuser")
                assert result is True

    def test_returns_false_for_user_without_permission(self):
        """Users without workspace permission are denied."""
        from mlflow_oidc_auth.validators.workspace import validate_can_read_workspace

        ctx = _make_auth_context(is_admin=False)
        mock_request = MagicMock()
        mock_request.path = "/api/3.0/mlflow/workspaces/secret-ws"
        with _app.test_request_context():
            with (
                patch(
                    "mlflow_oidc_auth.validators.workspace.get_auth_context",
                    return_value=ctx,
                ),
                patch("mlflow_oidc_auth.validators.workspace.request", mock_request),
                patch(
                    "mlflow_oidc_auth.validators.workspace.get_workspace_permission_cached",
                    return_value=None,
                ),
            ):
                result = validate_can_read_workspace("testuser")
                assert result is False

    def test_returns_true_for_user_with_permission(self):
        """Users with workspace permission are allowed."""
        from mlflow_oidc_auth.validators.workspace import validate_can_read_workspace

        ctx = _make_auth_context(is_admin=False)
        mock_request = MagicMock()
        mock_request.path = "/api/3.0/mlflow/workspaces/my-ws"
        mock_perm = MagicMock()  # Any non-None permission
        with _app.test_request_context():
            with (
                patch(
                    "mlflow_oidc_auth.validators.workspace.get_auth_context",
                    return_value=ctx,
                ),
                patch("mlflow_oidc_auth.validators.workspace.request", mock_request),
                patch(
                    "mlflow_oidc_auth.validators.workspace.get_workspace_permission_cached",
                    return_value=mock_perm,
                ),
            ):
                result = validate_can_read_workspace("testuser")
                assert result is True

    def test_extracts_workspace_name_from_path(self):
        """Workspace name is extracted from Flask request path."""
        from mlflow_oidc_auth.validators.workspace import validate_can_read_workspace

        ctx = _make_auth_context(username="alice", is_admin=False)
        mock_request = MagicMock()
        mock_request.path = "/api/3.0/mlflow/workspaces/team-alpha"
        mock_perm = MagicMock()
        with _app.test_request_context():
            with (
                patch(
                    "mlflow_oidc_auth.validators.workspace.get_auth_context",
                    return_value=ctx,
                ),
                patch("mlflow_oidc_auth.validators.workspace.request", mock_request),
                patch(
                    "mlflow_oidc_auth.validators.workspace.get_workspace_permission_cached",
                    return_value=mock_perm,
                ) as mock_cache,
            ):
                validate_can_read_workspace("alice")
                mock_cache.assert_called_once_with("alice", "team-alpha")

    def test_returns_forbidden_when_no_workspace_in_path(self):
        """Returns forbidden when workspace name cannot be extracted."""
        from mlflow_oidc_auth.validators.workspace import validate_can_read_workspace

        ctx = _make_auth_context(is_admin=False)
        mock_request = MagicMock()
        mock_request.path = "/api/3.0/mlflow/workspaces"  # No name segment
        with _app.test_request_context():
            with (
                patch(
                    "mlflow_oidc_auth.validators.workspace.get_auth_context",
                    return_value=ctx,
                ),
                patch("mlflow_oidc_auth.validators.workspace.request", mock_request),
            ):
                result = validate_can_read_workspace("testuser")
                assert result is False


@patch("mlflow_oidc_auth.validators.workspace.config", _mock_config)
class TestValidateCanUpdateWorkspace:
    """Tests for validate_can_update_workspace."""

    def test_returns_false_for_non_admin(self):
        """Non-admin users are denied."""
        from mlflow_oidc_auth.validators.workspace import validate_can_update_workspace

        ctx = _make_auth_context(is_admin=False)
        with _app.test_request_context():
            with patch(
                "mlflow_oidc_auth.validators.workspace.get_auth_context",
                return_value=ctx,
            ):
                result = validate_can_update_workspace("testuser")
                assert result is False

    def test_returns_true_for_admin(self):
        """Admin users are allowed."""
        from mlflow_oidc_auth.validators.workspace import validate_can_update_workspace

        ctx = _make_auth_context(is_admin=True)
        with _app.test_request_context():
            with patch(
                "mlflow_oidc_auth.validators.workspace.get_auth_context",
                return_value=ctx,
            ):
                result = validate_can_update_workspace("adminuser")
                assert result is True


@patch("mlflow_oidc_auth.validators.workspace.config", _mock_config)
class TestValidateCanDeleteWorkspace:
    """Tests for validate_can_delete_workspace."""

    def test_returns_false_for_non_admin(self):
        """Non-admin users are denied."""
        from mlflow_oidc_auth.validators.workspace import validate_can_delete_workspace

        ctx = _make_auth_context(is_admin=False)
        with _app.test_request_context():
            with patch(
                "mlflow_oidc_auth.validators.workspace.get_auth_context",
                return_value=ctx,
            ):
                result = validate_can_delete_workspace("testuser")
                assert result is False

    def test_returns_true_for_admin(self):
        """Admin users are allowed."""
        from mlflow_oidc_auth.validators.workspace import validate_can_delete_workspace

        ctx = _make_auth_context(is_admin=True)
        with _app.test_request_context():
            with patch(
                "mlflow_oidc_auth.validators.workspace.get_auth_context",
                return_value=ctx,
            ):
                result = validate_can_delete_workspace("adminuser")
                assert result is True


@patch("mlflow_oidc_auth.validators.workspace.config", _mock_config)
class TestValidateCanListWorkspaces:
    """Tests for validate_can_list_workspaces."""

    def test_is_noop_returns_true(self):
        """All authenticated users can list workspaces (returns True = allow)."""
        from mlflow_oidc_auth.validators.workspace import validate_can_list_workspaces

        result = validate_can_list_workspaces("anyuser")
        assert result is True

    def test_returns_false_when_workspaces_disabled(self):
        """Returns False when MLFLOW_ENABLE_WORKSPACES is disabled."""
        from mlflow_oidc_auth.validators.workspace import validate_can_list_workspaces

        disabled_config = MagicMock()
        disabled_config.MLFLOW_ENABLE_WORKSPACES = False
        with patch("mlflow_oidc_auth.validators.workspace.config", disabled_config):
            result = validate_can_list_workspaces("anyuser")
            assert result is False
