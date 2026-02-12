"""Tests for gateway-related filter functions in batch_permissions module.

The existing test_batch_permissions.py covers experiments, models, and prompts.
These tests cover the gateway endpoint, secret, and model definition filter functions.
"""

from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.utils.batch_permissions import (
    filter_manageable_gateway_endpoints,
    filter_manageable_gateway_model_definitions,
    filter_manageable_gateway_secrets,
)


class TestFilterManageableGatewayEndpoints:
    """Tests for filter_manageable_gateway_endpoints."""

    @patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_endpoint")
    def test_returns_manageable_endpoints(self, mock_can_manage: MagicMock) -> None:
        """Should return only endpoints the user can manage."""
        mock_can_manage.side_effect = lambda name, user: name == "ep-allowed"

        endpoints = [
            {"name": "ep-allowed", "endpoint_type": "chat"},
            {"name": "ep-denied", "endpoint_type": "completions"},
        ]

        result = filter_manageable_gateway_endpoints("alice", endpoints)

        assert len(result) == 1
        assert result[0]["name"] == "ep-allowed"

    @patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_endpoint")
    def test_returns_empty_when_none_manageable(self, mock_can_manage: MagicMock) -> None:
        """Should return empty list when no endpoints are manageable."""
        mock_can_manage.return_value = False

        endpoints = [{"name": "ep-1"}, {"name": "ep-2"}]
        result = filter_manageable_gateway_endpoints("alice", endpoints)

        assert result == []

    @patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_endpoint")
    def test_returns_all_when_all_manageable(self, mock_can_manage: MagicMock) -> None:
        """Should return all endpoints when all are manageable."""
        mock_can_manage.return_value = True

        endpoints = [{"name": "ep-1"}, {"name": "ep-2"}]
        result = filter_manageable_gateway_endpoints("admin", endpoints)

        assert len(result) == 2

    def test_returns_empty_for_empty_input(self) -> None:
        """Should return empty list for empty input."""
        result = filter_manageable_gateway_endpoints("alice", [])
        assert result == []

    @patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_endpoint")
    def test_skips_endpoints_without_name(self, mock_can_manage: MagicMock) -> None:
        """Should skip endpoints without a 'name' key."""
        mock_can_manage.return_value = True

        endpoints = [{"name": ""}, {"name": "valid-ep"}, {"type": "chat"}]
        result = filter_manageable_gateway_endpoints("alice", endpoints)

        assert len(result) == 1
        assert result[0]["name"] == "valid-ep"

    @patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_endpoint")
    def test_handles_permission_check_exception(self, mock_can_manage: MagicMock) -> None:
        """Should skip endpoints that raise exceptions during permission check."""
        mock_can_manage.side_effect = [True, Exception("DB error"), True]

        endpoints = [{"name": "ep-1"}, {"name": "ep-2"}, {"name": "ep-3"}]
        result = filter_manageable_gateway_endpoints("alice", endpoints)

        assert len(result) == 2
        assert result[0]["name"] == "ep-1"
        assert result[1]["name"] == "ep-3"


class TestFilterManageableGatewaySecrets:
    """Tests for filter_manageable_gateway_secrets."""

    @patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_secret")
    def test_returns_manageable_secrets(self, mock_can_manage: MagicMock) -> None:
        """Should return only secrets the user can manage."""
        mock_can_manage.side_effect = lambda name, user: name == "secret-ok"

        secrets = [
            {"name": "secret-ok"},
            {"name": "secret-nope"},
        ]

        result = filter_manageable_gateway_secrets("alice", secrets)

        assert len(result) == 1
        assert result[0]["name"] == "secret-ok"

    @patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_secret")
    def test_uses_key_when_name_absent(self, mock_can_manage: MagicMock) -> None:
        """Should fall back to 'key' field when 'name' is not present."""
        mock_can_manage.return_value = True

        secrets = [{"key": "my-key"}]
        result = filter_manageable_gateway_secrets("alice", secrets)

        assert len(result) == 1
        mock_can_manage.assert_called_once_with("my-key", "alice")

    @patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_secret")
    def test_skips_secrets_without_name_or_key(self, mock_can_manage: MagicMock) -> None:
        """Should skip secrets that have neither 'name' nor 'key'."""
        mock_can_manage.return_value = True

        secrets = [{"description": "orphan"}]
        result = filter_manageable_gateway_secrets("alice", secrets)

        assert result == []
        mock_can_manage.assert_not_called()

    def test_returns_empty_for_empty_input(self) -> None:
        """Should return empty list for empty input."""
        result = filter_manageable_gateway_secrets("alice", [])
        assert result == []

    @patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_secret")
    def test_handles_exception_gracefully(self, mock_can_manage: MagicMock) -> None:
        """Should skip secrets that raise exceptions during permission check."""
        mock_can_manage.side_effect = Exception("DB error")

        secrets = [{"name": "secret-1"}]
        result = filter_manageable_gateway_secrets("alice", secrets)

        assert result == []


class TestFilterManageableGatewayModelDefinitions:
    """Tests for filter_manageable_gateway_model_definitions."""

    @patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_model_definition")
    def test_returns_manageable_model_definitions(self, mock_can_manage: MagicMock) -> None:
        """Should return only model definitions the user can manage."""
        mock_can_manage.side_effect = lambda name, user: name == "model-ok"

        models = [
            {"name": "model-ok", "source": "openai"},
            {"name": "model-no", "source": "anthropic"},
        ]

        result = filter_manageable_gateway_model_definitions("alice", models)

        assert len(result) == 1
        assert result[0]["name"] == "model-ok"

    @patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_model_definition")
    def test_returns_empty_when_none_manageable(self, mock_can_manage: MagicMock) -> None:
        """Should return empty list when no model definitions are manageable."""
        mock_can_manage.return_value = False

        models = [{"name": "model-1"}, {"name": "model-2"}]
        result = filter_manageable_gateway_model_definitions("alice", models)

        assert result == []

    @patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_model_definition")
    def test_skips_models_without_name(self, mock_can_manage: MagicMock) -> None:
        """Should skip model definitions without a 'name' key."""
        mock_can_manage.return_value = True

        models = [{"name": ""}, {"name": "valid"}, {"source": "openai"}]
        result = filter_manageable_gateway_model_definitions("alice", models)

        assert len(result) == 1
        assert result[0]["name"] == "valid"

    def test_returns_empty_for_empty_input(self) -> None:
        """Should return empty list for empty input."""
        result = filter_manageable_gateway_model_definitions("alice", [])
        assert result == []

    @patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_model_definition")
    def test_handles_exception_gracefully(self, mock_can_manage: MagicMock) -> None:
        """Should skip model definitions that raise exceptions during permission check."""
        mock_can_manage.side_effect = [True, Exception("Network error")]

        models = [{"name": "m-1"}, {"name": "m-2"}]
        result = filter_manageable_gateway_model_definitions("alice", models)

        assert len(result) == 1
        assert result[0]["name"] == "m-1"
