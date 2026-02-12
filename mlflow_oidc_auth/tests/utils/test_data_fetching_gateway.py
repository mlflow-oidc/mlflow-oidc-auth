"""Tests for utils/data_fetching.py — gateway data fetching functions.

Covers fetch_all_gateway_endpoints, fetch_all_gateway_secrets,
and fetch_all_gateway_model_definitions.
"""

from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.utils.data_fetching import (
    fetch_all_gateway_endpoints,
    fetch_all_gateway_model_definitions,
    fetch_all_gateway_secrets,
)


class TestFetchAllGatewayEndpoints:
    """Tests for fetch_all_gateway_endpoints."""

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    def test_returns_list_of_dicts_from_to_dict(self, mock_get_store: MagicMock) -> None:
        """Should call to_dict() on endpoints that support it."""
        ep1 = MagicMock()
        ep1.to_dict.return_value = {"name": "ep1", "endpoint_type": "chat"}

        mock_get_store.return_value.list_gateway_endpoints.return_value = [ep1]

        result = fetch_all_gateway_endpoints()

        assert len(result) == 1
        assert result[0] == {"name": "ep1", "endpoint_type": "chat"}
        ep1.to_dict.assert_called_once()

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    def test_falls_back_to_vars_when_no_to_dict(self, mock_get_store: MagicMock) -> None:
        """Should use vars() when object has no to_dict method."""

        class SimpleEndpoint:
            def __init__(self, name: str) -> None:
                self.name = name

        ep = SimpleEndpoint("ep-x")
        mock_get_store.return_value.list_gateway_endpoints.return_value = [ep]

        result = fetch_all_gateway_endpoints()

        assert len(result) == 1
        assert result[0]["name"] == "ep-x"

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    def test_passes_through_plain_dicts(self, mock_get_store: MagicMock) -> None:
        """Should pass through plain dicts unchanged."""
        ep_dict = {"name": "raw-ep", "type": "embeddings"}
        mock_get_store.return_value.list_gateway_endpoints.return_value = [ep_dict]

        result = fetch_all_gateway_endpoints()

        assert result == [ep_dict]

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    def test_returns_empty_list_when_no_endpoints(self, mock_get_store: MagicMock) -> None:
        """Should return empty list when no endpoints exist."""
        mock_get_store.return_value.list_gateway_endpoints.return_value = []

        result = fetch_all_gateway_endpoints()

        assert result == []

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    def test_handles_multiple_endpoints(self, mock_get_store: MagicMock) -> None:
        """Should handle multiple endpoints of mixed types."""
        ep1 = MagicMock()
        ep1.to_dict.return_value = {"name": "ep1"}
        ep2 = {"name": "ep2"}

        mock_get_store.return_value.list_gateway_endpoints.return_value = [ep1, ep2]

        result = fetch_all_gateway_endpoints()

        assert len(result) == 2
        assert result[0]["name"] == "ep1"
        assert result[1]["name"] == "ep2"


class TestFetchAllGatewaySecrets:
    """Tests for fetch_all_gateway_secrets."""

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    def test_returns_secrets_via_to_dict(self, mock_get_store: MagicMock) -> None:
        """Should convert secrets using to_dict() when available."""
        secret = MagicMock()
        secret.to_dict.return_value = {"name": "api-key", "scope": "workspace"}

        mock_get_store.return_value.list_secret_infos.return_value = [secret]

        result = fetch_all_gateway_secrets()

        assert len(result) == 1
        assert result[0] == {"name": "api-key", "scope": "workspace"}

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    def test_falls_back_to_vars(self, mock_get_store: MagicMock) -> None:
        """Should fall back to vars() when no to_dict."""

        class SimpleSecret:
            def __init__(self) -> None:
                self.key = "my-secret"

        mock_get_store.return_value.list_secret_infos.return_value = [SimpleSecret()]

        result = fetch_all_gateway_secrets()

        assert len(result) == 1
        assert result[0]["key"] == "my-secret"

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    def test_passes_through_plain_dicts(self, mock_get_store: MagicMock) -> None:
        """Should pass through plain dicts unchanged."""
        secret = {"key": "raw-secret"}
        mock_get_store.return_value.list_secret_infos.return_value = [secret]

        result = fetch_all_gateway_secrets()

        assert result == [secret]

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    def test_returns_empty_list(self, mock_get_store: MagicMock) -> None:
        """Should return empty list when no secrets exist."""
        mock_get_store.return_value.list_secret_infos.return_value = []

        result = fetch_all_gateway_secrets()

        assert result == []


class TestFetchAllGatewayModelDefinitions:
    """Tests for fetch_all_gateway_model_definitions."""

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    def test_returns_model_defs_via_to_dict(self, mock_get_store: MagicMock) -> None:
        """Should convert model definitions using to_dict() when available."""
        model = MagicMock()
        model.to_dict.return_value = {"name": "gpt-4", "source": "openai"}

        mock_get_store.return_value.list_gateway_model_definitions.return_value = [model]

        result = fetch_all_gateway_model_definitions()

        assert len(result) == 1
        assert result[0] == {"name": "gpt-4", "source": "openai"}

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    def test_falls_back_to_vars(self, mock_get_store: MagicMock) -> None:
        """Should fall back to vars() when no to_dict."""

        class SimpleModelDef:
            def __init__(self) -> None:
                self.name = "claude"
                self.provider = "anthropic"

        mock_get_store.return_value.list_gateway_model_definitions.return_value = [SimpleModelDef()]

        result = fetch_all_gateway_model_definitions()

        assert len(result) == 1
        assert result[0]["name"] == "claude"
        assert result[0]["provider"] == "anthropic"

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    def test_passes_through_plain_dicts(self, mock_get_store: MagicMock) -> None:
        """Should pass through plain dicts unchanged."""
        model = {"name": "raw-model"}
        mock_get_store.return_value.list_gateway_model_definitions.return_value = [model]

        result = fetch_all_gateway_model_definitions()

        assert result == [model]

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    def test_returns_empty_list(self, mock_get_store: MagicMock) -> None:
        """Should return empty list when no model definitions exist."""
        mock_get_store.return_value.list_gateway_model_definitions.return_value = []

        result = fetch_all_gateway_model_definitions()

        assert result == []
