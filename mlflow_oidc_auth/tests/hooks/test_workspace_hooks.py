"""Tests for workspace hook registration and _find_validator() extension."""

from unittest.mock import MagicMock, patch

import pytest


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

        assert (
            WORKSPACE_BEFORE_REQUEST_HANDLERS[CreateWorkspace]
            is validate_can_create_workspace
        )
        assert (
            WORKSPACE_BEFORE_REQUEST_HANDLERS[GetWorkspace]
            is validate_can_read_workspace
        )
        assert (
            WORKSPACE_BEFORE_REQUEST_HANDLERS[ListWorkspaces]
            is validate_can_list_workspaces
        )
        assert (
            WORKSPACE_BEFORE_REQUEST_HANDLERS[UpdateWorkspace]
            is validate_can_update_workspace
        )
        assert (
            WORKSPACE_BEFORE_REQUEST_HANDLERS[DeleteWorkspace]
            is validate_can_delete_workspace
        )


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
            if (
                "/api/3.0/mlflow/workspaces" in pattern_str
                and not pattern_str.startswith("/ajax")
            ):
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
            assert hasattr(pattern, "fullmatch"), (
                f"Pattern {pattern} should be compiled regex"
            )
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
