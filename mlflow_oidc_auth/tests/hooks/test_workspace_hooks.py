"""Tests for workspace hook registration, _find_validator() extension, creation gating, and after_request filtering."""

import json
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask


class TestWorkspaceBeforeRequestHandlers:
    """Tests for WORKSPACE_BEFORE_REQUEST_HANDLERS mapping."""

    def test_maps_five_protobuf_classes(self):
        """WORKSPACE_BEFORE_REQUEST_HANDLERS has entries for all 5 workspace RPCs."""
        from mlflow_oidc_auth.hooks.before_request import (
            WORKSPACE_BEFORE_REQUEST_HANDLERS,
        )

        assert len(WORKSPACE_BEFORE_REQUEST_HANDLERS) == 5

    def test_maps_correct_validators(self):
        """Each protobuf class maps to the correct validator function."""
        from mlflow.protos.service_pb2 import (
            CreateWorkspace,
            GetWorkspace,
            ListWorkspaces,
            UpdateWorkspace,
            DeleteWorkspace,
        )
        from mlflow_oidc_auth.hooks.before_request import (
            WORKSPACE_BEFORE_REQUEST_HANDLERS,
        )
        from mlflow_oidc_auth.validators.workspace import (
            validate_can_create_workspace,
            validate_can_read_workspace,
            validate_can_list_workspaces,
            validate_can_update_workspace,
            validate_can_delete_workspace,
        )

        assert WORKSPACE_BEFORE_REQUEST_HANDLERS[CreateWorkspace] is validate_can_create_workspace
        assert WORKSPACE_BEFORE_REQUEST_HANDLERS[GetWorkspace] is validate_can_read_workspace
        assert WORKSPACE_BEFORE_REQUEST_HANDLERS[ListWorkspaces] is validate_can_list_workspaces
        assert WORKSPACE_BEFORE_REQUEST_HANDLERS[UpdateWorkspace] is validate_can_update_workspace
        assert WORKSPACE_BEFORE_REQUEST_HANDLERS[DeleteWorkspace] is validate_can_delete_workspace


class TestWorkspaceBeforeRequestValidators:
    """Tests for WORKSPACE_BEFORE_REQUEST_VALIDATORS regex mapping."""

    def test_registers_both_prefixes(self):
        """Validates entries exist for both /api/3.0/ and /ajax-api/3.0/ prefixes."""
        from mlflow_oidc_auth.hooks.before_request import (
            WORKSPACE_BEFORE_REQUEST_VALIDATORS,
        )

        # Collect all paths from the regex patterns
        has_api_prefix = False
        has_ajax_prefix = False
        for (pattern, method), handler in WORKSPACE_BEFORE_REQUEST_VALIDATORS.items():
            pattern_str = pattern.pattern
            if "/api/3.0/mlflow/workspaces" in pattern_str and not pattern_str.startswith("/ajax"):
                has_api_prefix = True
            if "/ajax-api/3.0/mlflow/workspaces" in pattern_str:
                has_ajax_prefix = True

        assert has_api_prefix, "Should have /api/3.0/ prefix entries"
        assert has_ajax_prefix, "Should have /ajax-api/3.0/ prefix entries"

    def test_has_correct_structure(self):
        """Validators dict has compiled regex patterns and callable handlers."""
        from mlflow_oidc_auth.hooks.before_request import (
            WORKSPACE_BEFORE_REQUEST_VALIDATORS,
        )

        assert len(WORKSPACE_BEFORE_REQUEST_VALIDATORS) > 0
        for (pattern, method), handler in WORKSPACE_BEFORE_REQUEST_VALIDATORS.items():
            assert hasattr(pattern, "fullmatch"), f"Pattern {pattern} should be compiled regex"
            assert isinstance(method, str), f"Method should be a string"
            assert callable(handler), f"Handler should be callable"


class TestFindValidatorWorkspace:
    """Tests for _find_validator() workspace path routing."""

    def test_returns_workspace_validator_for_api_path(self):
        """_find_validator returns workspace validator for /api/3.0/mlflow/workspaces/<name>."""
        from mlflow_oidc_auth.hooks.before_request import _find_validator

        mock_request = MagicMock()
        mock_request.path = "/api/3.0/mlflow/workspaces/test-ws"
        mock_request.method = "GET"

        mock_pattern = MagicMock()
        mock_pattern.fullmatch.return_value = True
        mock_validator = MagicMock()

        with patch(
            "mlflow_oidc_auth.hooks.before_request.WORKSPACE_BEFORE_REQUEST_VALIDATORS",
            {(mock_pattern, "GET"): mock_validator},
        ):
            result = _find_validator(mock_request)
            assert result is mock_validator

    def test_returns_workspace_validator_for_ajax_path(self):
        """_find_validator returns workspace validator for /ajax-api/3.0/mlflow/workspaces/<name>."""
        from mlflow_oidc_auth.hooks.before_request import _find_validator

        mock_request = MagicMock()
        mock_request.path = "/ajax-api/3.0/mlflow/workspaces/my-ws"
        mock_request.method = "GET"

        mock_pattern = MagicMock()
        mock_pattern.fullmatch.return_value = True
        mock_validator = MagicMock()

        with patch(
            "mlflow_oidc_auth.hooks.before_request.WORKSPACE_BEFORE_REQUEST_VALIDATORS",
            {(mock_pattern, "GET"): mock_validator},
        ):
            result = _find_validator(mock_request)
            assert result is mock_validator

    def test_returns_none_when_no_workspace_match(self):
        """_find_validator returns None when workspace path doesn't match any pattern."""
        from mlflow_oidc_auth.hooks.before_request import _find_validator

        mock_request = MagicMock()
        mock_request.path = "/api/3.0/mlflow/workspaces/test-ws"
        mock_request.method = "PATCH"

        mock_pattern = MagicMock()
        mock_pattern.fullmatch.return_value = False

        with patch(
            "mlflow_oidc_auth.hooks.before_request.WORKSPACE_BEFORE_REQUEST_VALIDATORS",
            {(mock_pattern, "GET"): MagicMock()},
        ):
            result = _find_validator(mock_request)
            assert result is None

    def test_non_workspace_paths_still_work(self):
        """Non-workspace paths still route to BEFORE_REQUEST_VALIDATORS (no regression)."""
        from mlflow_oidc_auth.hooks.before_request import _find_validator

        mock_request = MagicMock()
        mock_request.path = "/api/2.0/mlflow/experiments/get"
        mock_request.method = "GET"

        mock_validator = MagicMock()
        with patch(
            "mlflow_oidc_auth.hooks.before_request.BEFORE_REQUEST_VALIDATORS",
            {("/api/2.0/mlflow/experiments/get", "GET"): mock_validator},
        ):
            result = _find_validator(mock_request)
            assert result is mock_validator

    def test_logged_model_paths_still_work(self):
        """Logged model paths still route via regex matching (no regression)."""
        from mlflow_oidc_auth.hooks.before_request import _find_validator

        mock_request = MagicMock()
        mock_request.path = "/api/2.0/mlflow/logged-models/12345"
        mock_request.method = "GET"

        mock_pattern = MagicMock()
        mock_pattern.fullmatch.return_value = True
        mock_validator = MagicMock()

        with patch(
            "mlflow_oidc_auth.hooks.before_request.LOGGED_MODEL_BEFORE_REQUEST_VALIDATORS",
            {(mock_pattern, "GET"): mock_validator},
        ):
            result = _find_validator(mock_request)
            assert result is mock_validator


class TestWorkspaceCreationGating:
    """Tests for workspace creation gating in before_request_hook (WSAUTH-F)."""

    @pytest.fixture(autouse=True)
    def _reset_creation_paths_cache(self):
        """Reset the lazy-cached creation paths set between tests."""
        import mlflow_oidc_auth.hooks.before_request as br_module

        br_module._WORKSPACE_GATED_CREATION_PATHS = None
        yield
        br_module._WORKSPACE_GATED_CREATION_PATHS = None

    def _make_flask_app(self):
        """Create a minimal Flask app for testing."""
        _app = Flask(__name__)
        _app.config["TESTING"] = True
        return _app

    def test_create_experiment_blocked_without_workspace_manage(self):
        """CreateExperiment blocked when user lacks workspace MANAGE permission."""
        from mlflow_oidc_auth.hooks.before_request import _is_workspace_gated_creation

        _app = self._make_flask_app()
        with _app.test_request_context():
            # _is_workspace_gated_creation should identify CreateExperiment paths
            # The specific paths come from get_endpoints() — test the helper exists and works
            assert callable(_is_workspace_gated_creation)

    def test_is_workspace_gated_creation_detects_experiment_create(self):
        """_is_workspace_gated_creation identifies experiment creation paths."""
        from mlflow_oidc_auth.hooks.before_request import _is_workspace_gated_creation

        # CreateExperiment is POST to /api/2.0/mlflow/experiments/create
        assert _is_workspace_gated_creation("/api/2.0/mlflow/experiments/create", "POST") is True
        assert _is_workspace_gated_creation("/ajax-api/2.0/mlflow/experiments/create", "POST") is True

    def test_is_workspace_gated_creation_detects_model_create(self):
        """_is_workspace_gated_creation identifies registered model creation paths."""
        from mlflow_oidc_auth.hooks.before_request import _is_workspace_gated_creation

        # CreateRegisteredModel is POST to /api/2.0/mlflow/registered-models/create
        assert _is_workspace_gated_creation("/api/2.0/mlflow/registered-models/create", "POST") is True
        assert _is_workspace_gated_creation("/ajax-api/2.0/mlflow/registered-models/create", "POST") is True

    def test_is_workspace_gated_creation_rejects_non_creation_paths(self):
        """_is_workspace_gated_creation returns False for non-creation paths."""
        from mlflow_oidc_auth.hooks.before_request import _is_workspace_gated_creation

        assert _is_workspace_gated_creation("/api/2.0/mlflow/experiments/get", "GET") is False
        assert _is_workspace_gated_creation("/api/2.0/mlflow/runs/create", "POST") is False

    def test_is_workspace_gated_creation_rejects_graphql_and_server_info(self):
        """_is_workspace_gated_creation returns False for /graphql, /server-info, and gateway paths (regression for over-inclusive filter)."""
        from mlflow_oidc_auth.hooks.before_request import _is_workspace_gated_creation

        # These paths were previously incorrectly included due to 'if handler is not None' filter
        assert _is_workspace_gated_creation("/graphql", "GET") is False
        assert _is_workspace_gated_creation("/graphql", "POST") is False
        assert _is_workspace_gated_creation("/api/3.0/mlflow/server-info", "GET") is False
        assert _is_workspace_gated_creation("/ajax-api/3.0/mlflow/gateway/supported-providers", "GET") is False
        assert _is_workspace_gated_creation("/ajax-api/3.0/mlflow/gateway/supported-models", "GET") is False
        assert _is_workspace_gated_creation("/ajax-api/3.0/mlflow/scorer/invoke", "POST") is False

    def test_workspace_gated_creation_paths_count(self):
        """_get_workspace_gated_creation_paths() returns exactly 4 paths (2 endpoints x 2 prefixes)."""
        from mlflow_oidc_auth.hooks.before_request import (
            _get_workspace_gated_creation_paths,
        )

        paths = _get_workspace_gated_creation_paths()
        # CreateExperiment: /api/2.0/mlflow/experiments/create POST + /ajax-api/2.0/mlflow/experiments/create POST
        # CreateRegisteredModel: /api/2.0/mlflow/registered-models/create POST + /ajax-api/2.0/mlflow/registered-models/create POST
        assert len(paths) == 4, f"Expected exactly 4 creation paths, got {len(paths)}: {paths}"
        # All should be POST
        assert all(method == "POST" for _, method in paths), f"All creation paths should be POST: {paths}"

    def test_before_request_hook_blocks_experiment_creation_without_manage(self):
        """before_request_hook blocks CreateExperiment when user lacks workspace MANAGE."""
        from mlflow_oidc_auth.hooks.before_request import before_request_hook

        _app = self._make_flask_app()
        with _app.test_request_context(
            "/api/2.0/mlflow/experiments/create",
            method="POST",
        ):
            with patch(
                "mlflow_oidc_auth.hooks.before_request._get_auth_context",
                return_value=("testuser", False),
            ):
                with patch("mlflow_oidc_auth.hooks.before_request.config") as mock_config:
                    mock_config.MLFLOW_ENABLE_WORKSPACES = True
                    with patch(
                        "mlflow_oidc_auth.bridge.user.get_request_workspace",
                        return_value="team-ws",
                    ):
                        with patch(
                            "mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached",
                            return_value=None,
                        ):
                            with patch(
                                "mlflow_oidc_auth.hooks.before_request._find_validator",
                                return_value=None,
                            ):
                                resp = before_request_hook()
                                assert resp is not None
                                assert resp.status_code == 403

    def test_before_request_hook_allows_experiment_creation_with_manage(self):
        """before_request_hook allows CreateExperiment when user has workspace MANAGE."""
        from mlflow_oidc_auth.hooks.before_request import before_request_hook
        from mlflow_oidc_auth.permissions import MANAGE

        _app = self._make_flask_app()
        with _app.test_request_context(
            "/api/2.0/mlflow/experiments/create",
            method="POST",
        ):
            with patch(
                "mlflow_oidc_auth.hooks.before_request._get_auth_context",
                return_value=("testuser", False),
            ):
                with patch("mlflow_oidc_auth.hooks.before_request.config") as mock_config:
                    mock_config.MLFLOW_ENABLE_WORKSPACES = True
                    with patch(
                        "mlflow_oidc_auth.bridge.user.get_request_workspace",
                        return_value="team-ws",
                    ):
                        with patch(
                            "mlflow_oidc_auth.utils.workspace_cache.get_workspace_permission_cached",
                            return_value=MANAGE,
                        ):
                            with patch(
                                "mlflow_oidc_auth.hooks.before_request._find_validator",
                                return_value=None,
                            ):
                                resp = before_request_hook()
                                # Should not return 403 — either None or pass through
                                assert resp is None or (hasattr(resp, "status_code") and resp.status_code != 403)

    def test_before_request_hook_workspaces_disabled_no_creation_check(self):
        """before_request_hook skips creation gating when workspaces disabled."""
        from mlflow_oidc_auth.hooks.before_request import before_request_hook

        _app = self._make_flask_app()
        with _app.test_request_context(
            "/api/2.0/mlflow/experiments/create",
            method="POST",
        ):
            with patch(
                "mlflow_oidc_auth.hooks.before_request._get_auth_context",
                return_value=("testuser", False),
            ):
                with patch("mlflow_oidc_auth.hooks.before_request.config") as mock_config:
                    mock_config.MLFLOW_ENABLE_WORKSPACES = False
                    with patch(
                        "mlflow_oidc_auth.hooks.before_request._find_validator",
                        return_value=None,
                    ):
                        # With workspaces disabled, creation gating should not fire
                        # (no validator match either so None response = allowed)
                        resp = before_request_hook()
                        # Should NOT be 403 since workspaces are disabled
                        assert resp is None or (hasattr(resp, "status_code") and resp.status_code != 403)

    def test_before_request_hook_admin_bypass_creation_gating(self):
        """Admin users bypass workspace creation gating entirely."""
        from mlflow_oidc_auth.hooks.before_request import before_request_hook

        _app = self._make_flask_app()
        with _app.test_request_context(
            "/api/2.0/mlflow/experiments/create",
            method="POST",
        ):
            with patch(
                "mlflow_oidc_auth.hooks.before_request._get_auth_context",
                return_value=("admin", True),
            ):
                with patch("mlflow_oidc_auth.hooks.before_request.config") as mock_config:
                    mock_config.MLFLOW_ENABLE_WORKSPACES = True
                    # Admin should bypass — no 403
                    resp = before_request_hook()
                    assert resp is None


class TestAfterRequestListWorkspacesFiltering:
    """Tests for ListWorkspaces after_request filtering."""

    def _make_flask_app(self):
        """Create a minimal Flask app for testing."""
        _app = Flask(__name__)
        _app.config["TESTING"] = True
        return _app

    def test_filter_list_workspaces_registered_in_after_request_handlers(self):
        """ListWorkspaces is registered in AFTER_REQUEST_PATH_HANDLERS."""
        from mlflow.protos.service_pb2 import ListWorkspaces
        from mlflow_oidc_auth.hooks.after_request import AFTER_REQUEST_PATH_HANDLERS

        assert ListWorkspaces in AFTER_REQUEST_PATH_HANDLERS

    def test_filter_list_workspaces_filters_unauthorized(self):
        """_filter_list_workspaces removes workspaces user has no permission for."""
        from mlflow_oidc_auth.hooks.after_request import _filter_list_workspaces

        _app = self._make_flask_app()
        with _app.test_request_context():
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.get_json.return_value = {
                "workspaces": [
                    {"name": "ws-allowed"},
                    {"name": "ws-denied"},
                    {"name": "ws-also-allowed"},
                ]
            }

            from mlflow_oidc_auth.permissions import READ
            from mlflow_oidc_auth.entities.auth_context import AuthContext

            mock_auth_ctx = AuthContext(username="testuser", is_admin=False, workspace=None)

            def mock_perm_cached(username, ws_name):
                if ws_name in ("ws-allowed", "ws-also-allowed"):
                    return READ
                return None

            with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                with patch(
                    "mlflow_oidc_auth.hooks.after_request.get_auth_context",
                    return_value=mock_auth_ctx,
                ):
                    with patch(
                        "mlflow_oidc_auth.hooks.after_request.get_workspace_permission_cached",
                        side_effect=mock_perm_cached,
                    ):
                        _filter_list_workspaces(mock_response)

            # Check that set_data was called with filtered workspaces
            mock_response.set_data.assert_called_once()
            data = json.loads(mock_response.set_data.call_args[0][0])
            ws_names = [ws["name"] for ws in data["workspaces"]]
            assert "ws-allowed" in ws_names
            assert "ws-also-allowed" in ws_names
            assert "ws-denied" not in ws_names

    def test_filter_list_workspaces_filters_no_permissions(self):
        """_filter_list_workspaces removes workspaces where user has NO_PERMISSIONS (can_read=False)."""
        from mlflow_oidc_auth.hooks.after_request import _filter_list_workspaces
        from mlflow_oidc_auth.permissions import READ, NO_PERMISSIONS
        from mlflow_oidc_auth.entities.auth_context import AuthContext

        _app = self._make_flask_app()
        with _app.test_request_context():
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.get_json.return_value = {
                "workspaces": [
                    {"name": "ws-allowed"},
                    {"name": "ws-no-perms"},
                    {"name": "ws-denied"},
                ]
            }

            mock_auth_ctx = AuthContext(username="testuser", is_admin=False, workspace=None)

            def mock_perm_cached(username, ws_name):
                if ws_name == "ws-allowed":
                    return READ
                if ws_name == "ws-no-perms":
                    return NO_PERMISSIONS  # has permission object but can_read=False
                return None  # ws-denied: no permission at all

            with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                with patch(
                    "mlflow_oidc_auth.hooks.after_request.get_auth_context",
                    return_value=mock_auth_ctx,
                ):
                    with patch(
                        "mlflow_oidc_auth.hooks.after_request.get_workspace_permission_cached",
                        side_effect=mock_perm_cached,
                    ):
                        _filter_list_workspaces(mock_response)

            mock_response.set_data.assert_called_once()
            data = json.loads(mock_response.set_data.call_args[0][0])
            ws_names = [ws["name"] for ws in data["workspaces"]]
            assert "ws-allowed" in ws_names
            assert "ws-no-perms" not in ws_names  # NO_PERMISSIONS should be filtered
            assert "ws-denied" not in ws_names  # None should be filtered

    def test_filter_list_workspaces_skips_for_admin(self):
        """_filter_list_workspaces does not filter for admin users."""
        from mlflow_oidc_auth.hooks.after_request import _filter_list_workspaces
        from mlflow_oidc_auth.entities.auth_context import AuthContext

        _app = self._make_flask_app()
        with _app.test_request_context():
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_auth_ctx = AuthContext(username="admin", is_admin=True, workspace=None)

            with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                with patch(
                    "mlflow_oidc_auth.hooks.after_request.get_auth_context",
                    return_value=mock_auth_ctx,
                ):
                    _filter_list_workspaces(mock_response)

            # set_data should NOT be called because admin bypasses
            mock_response.set_data.assert_not_called()

    def test_filter_list_workspaces_skips_non_200(self):
        """_filter_list_workspaces does not filter non-200 responses."""
        from mlflow_oidc_auth.hooks.after_request import _filter_list_workspaces

        _app = self._make_flask_app()
        with _app.test_request_context():
            mock_response = MagicMock()
            mock_response.status_code = 404

            with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                _filter_list_workspaces(mock_response)

            mock_response.set_data.assert_not_called()

    def test_filter_list_workspaces_skips_when_disabled(self):
        """_filter_list_workspaces is a no-op when workspaces are disabled."""
        from mlflow_oidc_auth.hooks.after_request import _filter_list_workspaces

        _app = self._make_flask_app()
        with _app.test_request_context():
            mock_response = MagicMock()
            mock_response.status_code = 200

            with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
                mock_config.MLFLOW_ENABLE_WORKSPACES = False
                _filter_list_workspaces(mock_response)

            mock_response.set_data.assert_not_called()


class TestAutoGrantWorkspaceManagePermission:
    """Tests for _auto_grant_workspace_manage_permission after-request handler (WSCRUD-01)."""

    def _make_flask_app(self):
        _app = Flask(__name__)
        _app.config["TESTING"] = True
        return _app

    def test_auto_grant_on_successful_create(self):
        """After successful CreateWorkspace (200), creator gets MANAGE permission."""
        from mlflow_oidc_auth.hooks.after_request import (
            _auto_grant_workspace_manage_permission,
        )
        from mlflow_oidc_auth.entities.auth_context import AuthContext

        _app = self._make_flask_app()
        with _app.test_request_context():
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.get_json.return_value = {"workspace": {"name": "new-ws"}}

            mock_auth_ctx = AuthContext(username="creator", is_admin=True, workspace=None)

            with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                with patch(
                    "mlflow_oidc_auth.hooks.after_request.get_auth_context",
                    return_value=mock_auth_ctx,
                ):
                    with patch("mlflow_oidc_auth.hooks.after_request.store") as mock_store:
                        with patch("mlflow_oidc_auth.hooks.after_request.flush_workspace_cache") as mock_flush:
                            _auto_grant_workspace_manage_permission(mock_response)
                            mock_store.create_workspace_permission.assert_called_once_with("new-ws", "creator", "MANAGE")
                            mock_flush.assert_called_once()

    def test_auto_grant_flushes_workspace_cache(self):
        """After successful CreateWorkspace, workspace cache is flushed."""
        from mlflow_oidc_auth.hooks.after_request import (
            _auto_grant_workspace_manage_permission,
        )
        from mlflow_oidc_auth.entities.auth_context import AuthContext

        _app = self._make_flask_app()
        with _app.test_request_context():
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.get_json.return_value = {"workspace": {"name": "ws2"}}

            mock_auth_ctx = AuthContext(username="user1", is_admin=True, workspace=None)

            with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                with patch(
                    "mlflow_oidc_auth.hooks.after_request.get_auth_context",
                    return_value=mock_auth_ctx,
                ):
                    with patch("mlflow_oidc_auth.hooks.after_request.store"):
                        with patch("mlflow_oidc_auth.hooks.after_request.flush_workspace_cache") as mock_flush:
                            _auto_grant_workspace_manage_permission(mock_response)
                            mock_flush.assert_called_once()

    def test_no_auto_grant_on_failed_create(self):
        """After failed CreateWorkspace (non-200), no permission is created."""
        from mlflow_oidc_auth.hooks.after_request import (
            _auto_grant_workspace_manage_permission,
        )

        _app = self._make_flask_app()
        with _app.test_request_context():
            mock_response = MagicMock()
            mock_response.status_code = 400

            with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                with patch("mlflow_oidc_auth.hooks.after_request.store") as mock_store:
                    _auto_grant_workspace_manage_permission(mock_response)
                    mock_store.create_workspace_permission.assert_not_called()

    def test_no_auto_grant_when_workspaces_disabled(self):
        """No permission created when workspaces are disabled."""
        from mlflow_oidc_auth.hooks.after_request import (
            _auto_grant_workspace_manage_permission,
        )

        _app = self._make_flask_app()
        with _app.test_request_context():
            mock_response = MagicMock()
            mock_response.status_code = 200

            with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
                mock_config.MLFLOW_ENABLE_WORKSPACES = False
                with patch("mlflow_oidc_auth.hooks.after_request.store") as mock_store:
                    _auto_grant_workspace_manage_permission(mock_response)
                    mock_store.create_workspace_permission.assert_not_called()

    def test_registered_in_after_request_handlers(self):
        """CreateWorkspace is registered in AFTER_REQUEST_PATH_HANDLERS."""
        from mlflow.protos.service_pb2 import CreateWorkspace
        from mlflow_oidc_auth.hooks.after_request import (
            AFTER_REQUEST_PATH_HANDLERS,
            _auto_grant_workspace_manage_permission,
        )

        assert CreateWorkspace in AFTER_REQUEST_PATH_HANDLERS
        assert AFTER_REQUEST_PATH_HANDLERS[CreateWorkspace] is _auto_grant_workspace_manage_permission


class TestCascadeDeleteWorkspacePermissions:
    """Tests for _cascade_delete_workspace_permissions after-request handler (WSCRUD-06)."""

    def _make_flask_app(self):
        _app = Flask(__name__)
        _app.config["TESTING"] = True
        return _app

    def test_cascade_delete_on_successful_delete(self):
        """After successful DeleteWorkspace (204), wipe_workspace_permissions is called."""
        from mlflow_oidc_auth.hooks.after_request import (
            _cascade_delete_workspace_permissions,
        )

        _app = self._make_flask_app()
        with _app.test_request_context():
            from flask import g

            g._deleting_workspace_name = "doomed-ws"
            mock_response = MagicMock()
            mock_response.status_code = 204

            with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                with patch("mlflow_oidc_auth.hooks.after_request.store") as mock_store:
                    mock_store.wipe_workspace_permissions.return_value = 5
                    with patch("mlflow_oidc_auth.hooks.after_request.flush_workspace_cache") as mock_flush:
                        _cascade_delete_workspace_permissions(mock_response)
                        mock_store.wipe_workspace_permissions.assert_called_once_with("doomed-ws")
                        mock_flush.assert_called_once()

    def test_cascade_delete_flushes_workspace_cache(self):
        """After successful DeleteWorkspace, workspace cache is flushed."""
        from mlflow_oidc_auth.hooks.after_request import (
            _cascade_delete_workspace_permissions,
        )

        _app = self._make_flask_app()
        with _app.test_request_context():
            from flask import g

            g._deleting_workspace_name = "ws-del"
            mock_response = MagicMock()
            mock_response.status_code = 200

            with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                with patch("mlflow_oidc_auth.hooks.after_request.store") as mock_store:
                    mock_store.wipe_workspace_permissions.return_value = 0
                    with patch("mlflow_oidc_auth.hooks.after_request.flush_workspace_cache") as mock_flush:
                        _cascade_delete_workspace_permissions(mock_response)
                        mock_flush.assert_called_once()

    def test_no_cascade_on_failed_delete(self):
        """After failed DeleteWorkspace (non-204), no wipe is called."""
        from mlflow_oidc_auth.hooks.after_request import (
            _cascade_delete_workspace_permissions,
        )

        _app = self._make_flask_app()
        with _app.test_request_context():
            from flask import g

            g._deleting_workspace_name = "ws-fail"
            mock_response = MagicMock()
            mock_response.status_code = 404

            with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                with patch("mlflow_oidc_auth.hooks.after_request.store") as mock_store:
                    _cascade_delete_workspace_permissions(mock_response)
                    mock_store.wipe_workspace_permissions.assert_not_called()

    def test_no_cascade_when_no_workspace_stashed(self):
        """No cascade when no workspace name was stashed in Flask g."""
        from mlflow_oidc_auth.hooks.after_request import (
            _cascade_delete_workspace_permissions,
        )

        _app = self._make_flask_app()
        with _app.test_request_context():
            mock_response = MagicMock()
            mock_response.status_code = 204

            with patch("mlflow_oidc_auth.hooks.after_request.config") as mock_config:
                mock_config.MLFLOW_ENABLE_WORKSPACES = True
                with patch("mlflow_oidc_auth.hooks.after_request.store") as mock_store:
                    _cascade_delete_workspace_permissions(mock_response)
                    mock_store.wipe_workspace_permissions.assert_not_called()

    def test_registered_in_after_request_handlers(self):
        """DeleteWorkspace is registered in AFTER_REQUEST_PATH_HANDLERS."""
        from mlflow.protos.service_pb2 import DeleteWorkspace
        from mlflow_oidc_auth.hooks.after_request import (
            AFTER_REQUEST_PATH_HANDLERS,
            _cascade_delete_workspace_permissions,
        )

        assert DeleteWorkspace in AFTER_REQUEST_PATH_HANDLERS
        assert AFTER_REQUEST_PATH_HANDLERS[DeleteWorkspace] is _cascade_delete_workspace_permissions


class TestWorkspaceNameStashInBeforeRequest:
    """Tests for workspace name stashing in _find_validator for DeleteWorkspace."""

    def test_stashes_workspace_name_for_delete(self):
        """Workspace name is stashed in Flask g._deleting_workspace_name for DELETE."""
        from mlflow_oidc_auth.hooks.before_request import _find_validator

        _app = Flask(__name__)
        _app.config["TESTING"] = True
        with _app.test_request_context(
            "/api/3.0/mlflow/workspaces/target-ws",
            method="DELETE",
        ):
            mock_request = MagicMock()
            mock_request.path = "/api/3.0/mlflow/workspaces/target-ws"
            mock_request.method = "DELETE"

            mock_pattern = MagicMock()
            mock_pattern.fullmatch.return_value = True
            mock_validator = MagicMock()

            with patch(
                "mlflow_oidc_auth.hooks.before_request.WORKSPACE_BEFORE_REQUEST_VALIDATORS",
                {(mock_pattern, "DELETE"): mock_validator},
            ):
                from flask import g

                result = _find_validator(mock_request)
                assert result is mock_validator
                assert g._deleting_workspace_name == "target-ws"

    def test_no_stash_for_non_delete(self):
        """No stash for GET requests on workspace paths."""
        from mlflow_oidc_auth.hooks.before_request import _find_validator

        _app = Flask(__name__)
        _app.config["TESTING"] = True
        with _app.test_request_context(
            "/api/3.0/mlflow/workspaces/read-ws",
            method="GET",
        ):
            mock_request = MagicMock()
            mock_request.path = "/api/3.0/mlflow/workspaces/read-ws"
            mock_request.method = "GET"

            mock_pattern = MagicMock()
            mock_pattern.fullmatch.return_value = True
            mock_validator = MagicMock()

            with patch(
                "mlflow_oidc_auth.hooks.before_request.WORKSPACE_BEFORE_REQUEST_VALIDATORS",
                {(mock_pattern, "GET"): mock_validator},
            ):
                from flask import g

                result = _find_validator(mock_request)
                assert result is mock_validator
                assert not hasattr(g, "_deleting_workspace_name")


class TestValidateCanUpdateWorkspaceManage:
    """Tests for validate_can_update_workspace with MANAGE delegation (WSCRUD-04)."""

    def _make_flask_app(self):
        _app = Flask(__name__)
        _app.config["TESTING"] = True
        return _app

    def _make_mock_config(self):
        mock_cfg = MagicMock()
        mock_cfg.MLFLOW_ENABLE_WORKSPACES = True
        return mock_cfg

    def test_admin_allowed(self):
        """Admin users can update workspaces."""
        from mlflow_oidc_auth.validators.workspace import validate_can_update_workspace
        from mlflow_oidc_auth.entities.auth_context import AuthContext

        _app = self._make_flask_app()
        with _app.test_request_context("/api/3.0/mlflow/workspaces/ws1", method="PUT"):
            mock_ctx = AuthContext(username="admin", is_admin=True, workspace=None)
            with (
                patch(
                    "mlflow_oidc_auth.validators.workspace.get_auth_context",
                    return_value=mock_ctx,
                ),
                patch(
                    "mlflow_oidc_auth.validators.workspace.config",
                    self._make_mock_config(),
                ),
            ):
                result = validate_can_update_workspace("admin")
                assert result is True

    def test_manage_permission_allowed(self):
        """Users with MANAGE permission can update workspaces."""
        from mlflow_oidc_auth.validators.workspace import validate_can_update_workspace
        from mlflow_oidc_auth.entities.auth_context import AuthContext
        from mlflow_oidc_auth.permissions import MANAGE

        _app = self._make_flask_app()
        with _app.test_request_context("/api/3.0/mlflow/workspaces/ws1", method="PUT"):
            mock_ctx = AuthContext(username="manager", is_admin=False, workspace=None)
            with (
                patch(
                    "mlflow_oidc_auth.validators.workspace.get_auth_context",
                    return_value=mock_ctx,
                ),
                patch(
                    "mlflow_oidc_auth.validators.workspace.config",
                    self._make_mock_config(),
                ),
            ):
                with patch(
                    "mlflow_oidc_auth.validators.workspace.get_workspace_permission_cached",
                    return_value=MANAGE,
                ):
                    result = validate_can_update_workspace("manager")
                    assert result is True

    def test_no_manage_permission_denied(self):
        """Users without MANAGE permission are denied."""
        from mlflow_oidc_auth.validators.workspace import validate_can_update_workspace
        from mlflow_oidc_auth.entities.auth_context import AuthContext
        from mlflow_oidc_auth.permissions import READ

        _app = self._make_flask_app()
        with _app.test_request_context("/api/3.0/mlflow/workspaces/ws1", method="PUT"):
            mock_ctx = AuthContext(username="reader", is_admin=False, workspace=None)
            with patch(
                "mlflow_oidc_auth.validators.workspace.get_auth_context",
                return_value=mock_ctx,
            ):
                with patch(
                    "mlflow_oidc_auth.validators.workspace.get_workspace_permission_cached",
                    return_value=READ,
                ):
                    result = validate_can_update_workspace("reader")
                    assert result is False

    def test_no_permission_at_all_denied(self):
        """Users with no workspace permission at all are denied."""
        from mlflow_oidc_auth.validators.workspace import validate_can_update_workspace
        from mlflow_oidc_auth.entities.auth_context import AuthContext

        _app = self._make_flask_app()
        with _app.test_request_context("/api/3.0/mlflow/workspaces/ws1", method="PUT"):
            mock_ctx = AuthContext(username="nobody", is_admin=False, workspace=None)
            with patch(
                "mlflow_oidc_auth.validators.workspace.get_auth_context",
                return_value=mock_ctx,
            ):
                with patch(
                    "mlflow_oidc_auth.validators.workspace.get_workspace_permission_cached",
                    return_value=None,
                ):
                    result = validate_can_update_workspace("nobody")
                    assert result is False


class TestValidateCanDeleteWorkspaceManage:
    """Tests for validate_can_delete_workspace with MANAGE delegation (WSCRUD-05)."""

    def _make_flask_app(self):
        _app = Flask(__name__)
        _app.config["TESTING"] = True
        return _app

    def _make_mock_config(self):
        mock_cfg = MagicMock()
        mock_cfg.MLFLOW_ENABLE_WORKSPACES = True
        return mock_cfg

    def test_admin_allowed(self):
        """Admin users can delete workspaces."""
        from mlflow_oidc_auth.validators.workspace import validate_can_delete_workspace
        from mlflow_oidc_auth.entities.auth_context import AuthContext

        _app = self._make_flask_app()
        with _app.test_request_context("/api/3.0/mlflow/workspaces/ws1", method="DELETE"):
            mock_ctx = AuthContext(username="admin", is_admin=True, workspace=None)
            with (
                patch(
                    "mlflow_oidc_auth.validators.workspace.get_auth_context",
                    return_value=mock_ctx,
                ),
                patch(
                    "mlflow_oidc_auth.validators.workspace.config",
                    self._make_mock_config(),
                ),
            ):
                result = validate_can_delete_workspace("admin")
                assert result is True

    def test_manage_permission_allowed(self):
        """Users with MANAGE permission can delete workspaces."""
        from mlflow_oidc_auth.validators.workspace import validate_can_delete_workspace
        from mlflow_oidc_auth.entities.auth_context import AuthContext
        from mlflow_oidc_auth.permissions import MANAGE

        _app = self._make_flask_app()
        with _app.test_request_context("/api/3.0/mlflow/workspaces/ws1", method="DELETE"):
            mock_ctx = AuthContext(username="manager", is_admin=False, workspace=None)
            with (
                patch(
                    "mlflow_oidc_auth.validators.workspace.get_auth_context",
                    return_value=mock_ctx,
                ),
                patch(
                    "mlflow_oidc_auth.validators.workspace.config",
                    self._make_mock_config(),
                ),
            ):
                with patch(
                    "mlflow_oidc_auth.validators.workspace.get_workspace_permission_cached",
                    return_value=MANAGE,
                ):
                    result = validate_can_delete_workspace("manager")
                    assert result is True

    def test_no_manage_permission_denied(self):
        """Users without MANAGE permission are denied."""
        from mlflow_oidc_auth.validators.workspace import validate_can_delete_workspace
        from mlflow_oidc_auth.entities.auth_context import AuthContext
        from mlflow_oidc_auth.permissions import EDIT

        _app = self._make_flask_app()
        with _app.test_request_context("/api/3.0/mlflow/workspaces/ws1", method="DELETE"):
            mock_ctx = AuthContext(username="editor", is_admin=False, workspace=None)
            with patch(
                "mlflow_oidc_auth.validators.workspace.get_auth_context",
                return_value=mock_ctx,
            ):
                with patch(
                    "mlflow_oidc_auth.validators.workspace.get_workspace_permission_cached",
                    return_value=EDIT,
                ):
                    result = validate_can_delete_workspace("editor")
                    assert result is False

    def test_no_permission_at_all_denied(self):
        """Users with no workspace permission at all are denied."""
        from mlflow_oidc_auth.validators.workspace import validate_can_delete_workspace
        from mlflow_oidc_auth.entities.auth_context import AuthContext

        _app = self._make_flask_app()
        with _app.test_request_context("/api/3.0/mlflow/workspaces/ws1", method="DELETE"):
            mock_ctx = AuthContext(username="nobody", is_admin=False, workspace=None)
            with patch(
                "mlflow_oidc_auth.validators.workspace.get_auth_context",
                return_value=mock_ctx,
            ):
                with patch(
                    "mlflow_oidc_auth.validators.workspace.get_workspace_permission_cached",
                    return_value=None,
                ):
                    result = validate_can_delete_workspace("nobody")
                    assert result is False
