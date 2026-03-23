"""Tests for gateway permission resolution functions in utils/permissions.py.

Covers effective_gateway_*_permission and can_*_gateway_* helpers for
endpoints, secrets, and model definitions. Uses the generic _match_regex_permission
for regex matching instead of the old per-resource regex functions.
"""

from unittest.mock import MagicMock, patch

import pytest
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.utils.permissions import (
    _match_regex_permission,
    can_manage_gateway_endpoint,
    can_manage_gateway_model_definition,
    can_manage_gateway_secret,
    can_read_gateway_endpoint,
    can_read_gateway_model_definition,
    can_read_gateway_secret,
    can_update_gateway_endpoint,
    can_update_gateway_model_definition,
    can_update_gateway_secret,
    can_use_gateway_endpoint,
    can_use_gateway_model_definition,
    can_use_gateway_secret,
    effective_gateway_endpoint_permission,
    effective_gateway_model_definition_permission,
    effective_gateway_secret_permission,
)

# ---------------------------------------------------------------------------
# Regex matchers (all use generic _match_regex_permission now)
# ---------------------------------------------------------------------------


class TestGatewayEndpointRegexPermission:
    """Tests for endpoint regex permission matching via _match_regex_permission."""

    def test_returns_matching_permission(self) -> None:
        """Should return permission of the first matching regex."""
        regex = MagicMock(regex="^ep-.*", permission="READ", priority=1)
        result = _match_regex_permission([regex], "ep-chat", "gateway name")
        assert result == "READ"

    def test_raises_when_no_match(self) -> None:
        """Should raise MlflowException when no regex matches."""
        regex = MagicMock(regex="^other-.*", permission="READ", priority=1)
        with pytest.raises(MlflowException):
            _match_regex_permission([regex], "ep-chat", "gateway name")

    def test_returns_first_match_priority(self) -> None:
        """Should return first matching regex (by list order)."""
        r1 = MagicMock(regex=".*", permission="READ", priority=10)
        r2 = MagicMock(regex="^ep-.*", permission="MANAGE", priority=1)
        result = _match_regex_permission([r1, r2], "ep-chat", "gateway name")
        assert result == "READ"

    def test_empty_list_raises(self) -> None:
        """Should raise when regex list is empty."""
        with pytest.raises(MlflowException):
            _match_regex_permission([], "ep-1", "gateway name")


class TestGatewayEndpointGroupRegexPermission:
    """Tests for endpoint group regex permission matching via _match_regex_permission."""

    def test_returns_matching_permission(self) -> None:
        """Should return permission of the first matching regex."""
        regex = MagicMock(regex="^ep-.*", permission="MANAGE", priority=1)
        result = _match_regex_permission([regex], "ep-test", "gateway name")
        assert result == "MANAGE"

    def test_raises_when_no_match(self) -> None:
        """Should raise when no regex matches."""
        regex = MagicMock(regex="^other-.*", permission="READ", priority=1)
        with pytest.raises(MlflowException):
            _match_regex_permission([regex], "ep-test", "gateway name")


class TestGatewaySecretRegexPermission:
    """Tests for secret regex permission matching via _match_regex_permission."""

    def test_returns_matching_permission(self) -> None:
        """Should return permission when regex matches."""
        regex = MagicMock(regex="^api-.*", permission="READ", priority=1)
        result = _match_regex_permission([regex], "api-key-1", "gateway name")
        assert result == "READ"

    def test_raises_when_no_match(self) -> None:
        """Should raise when no regex matches."""
        regex = MagicMock(regex="^xxx-.*", permission="READ", priority=1)
        with pytest.raises(MlflowException):
            _match_regex_permission([regex], "api-key", "gateway name")


class TestGatewaySecretGroupRegexPermission:
    """Tests for secret group regex permission matching via _match_regex_permission."""

    def test_returns_matching_permission(self) -> None:
        """Should return permission when regex matches."""
        regex = MagicMock(regex="^team-.*", permission="MANAGE", priority=1)
        result = _match_regex_permission([regex], "team-secret", "gateway name")
        assert result == "MANAGE"

    def test_raises_when_no_match(self) -> None:
        """Should raise when no regex matches."""
        regex = MagicMock(regex="^other-.*", permission="READ", priority=1)
        with pytest.raises(MlflowException):
            _match_regex_permission([regex], "team-secret", "gateway name")


class TestGatewayModelDefinitionRegexPermission:
    """Tests for model definition regex permission matching via _match_regex_permission."""

    def test_returns_matching_permission(self) -> None:
        """Should return permission when regex matches."""
        regex = MagicMock(regex="^gpt-.*", permission="READ", priority=1)
        result = _match_regex_permission([regex], "gpt-4", "gateway name")
        assert result == "READ"

    def test_raises_when_no_match(self) -> None:
        """Should raise when no regex matches."""
        regex = MagicMock(regex="^claude-.*", permission="READ", priority=1)
        with pytest.raises(MlflowException):
            _match_regex_permission([regex], "gpt-4", "gateway name")


class TestGatewayModelDefinitionGroupRegexPermission:
    """Tests for model definition group regex permission matching via _match_regex_permission."""

    def test_returns_matching_permission(self) -> None:
        """Should return permission when regex matches."""
        regex = MagicMock(regex="^shared-.*", permission="EDIT", priority=1)
        result = _match_regex_permission([regex], "shared-model", "gateway name")
        assert result == "EDIT"

    def test_raises_when_no_match(self) -> None:
        """Should raise when no regex matches."""
        regex = MagicMock(regex="^private-.*", permission="READ", priority=1)
        with pytest.raises(MlflowException):
            _match_regex_permission([regex], "shared-model", "gateway name")


# ---------------------------------------------------------------------------
# Effective permission + can_* helpers
# ---------------------------------------------------------------------------


class TestEffectiveGatewayEndpointPermission:
    """Tests for effective_gateway_endpoint_permission and can_* wrappers."""

    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_effective_delegates_to_store_or_default(
        self, mock_resolver: MagicMock
    ) -> None:
        """Should delegate to get_permission_from_store_or_default."""
        mock_result = MagicMock()
        mock_resolver.return_value = mock_result

        result = effective_gateway_endpoint_permission("ep-1", "alice")

        assert result is mock_result
        mock_resolver.assert_called_once()

    @patch("mlflow_oidc_auth.utils.permissions.effective_gateway_endpoint_permission")
    def test_can_read(self, mock_eff: MagicMock) -> None:
        """can_read_gateway_endpoint should check can_read on the permission."""
        mock_eff.return_value.permission.can_read = True
        assert can_read_gateway_endpoint("ep-1", "alice") is True

        mock_eff.return_value.permission.can_read = False
        assert can_read_gateway_endpoint("ep-1", "alice") is False

    @patch("mlflow_oidc_auth.utils.permissions.effective_gateway_endpoint_permission")
    def test_can_use(self, mock_eff: MagicMock) -> None:
        """can_use_gateway_endpoint should check can_use."""
        mock_eff.return_value.permission.can_use = True
        assert can_use_gateway_endpoint("ep-1", "alice") is True

    @patch("mlflow_oidc_auth.utils.permissions.effective_gateway_endpoint_permission")
    def test_can_update(self, mock_eff: MagicMock) -> None:
        """can_update_gateway_endpoint should check can_update."""
        mock_eff.return_value.permission.can_update = True
        assert can_update_gateway_endpoint("ep-1", "alice") is True

    @patch("mlflow_oidc_auth.utils.permissions.effective_gateway_endpoint_permission")
    def test_can_manage(self, mock_eff: MagicMock) -> None:
        """can_manage_gateway_endpoint should check can_manage."""
        mock_eff.return_value.permission.can_manage = True
        assert can_manage_gateway_endpoint("ep-1", "alice") is True

        mock_eff.return_value.permission.can_manage = False
        assert can_manage_gateway_endpoint("ep-1", "alice") is False


class TestEffectiveGatewaySecretPermission:
    """Tests for effective_gateway_secret_permission and can_* wrappers."""

    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_effective_delegates_to_store_or_default(
        self, mock_resolver: MagicMock
    ) -> None:
        """Should delegate to get_permission_from_store_or_default."""
        mock_result = MagicMock()
        mock_resolver.return_value = mock_result

        result = effective_gateway_secret_permission("s-1", "alice")

        assert result is mock_result
        mock_resolver.assert_called_once()

    @patch("mlflow_oidc_auth.utils.permissions.effective_gateway_secret_permission")
    def test_can_read(self, mock_eff: MagicMock) -> None:
        """can_read_gateway_secret should check can_read."""
        mock_eff.return_value.permission.can_read = True
        assert can_read_gateway_secret("s-1", "alice") is True

    @patch("mlflow_oidc_auth.utils.permissions.effective_gateway_secret_permission")
    def test_can_use(self, mock_eff: MagicMock) -> None:
        """can_use_gateway_secret should check can_use."""
        mock_eff.return_value.permission.can_use = True
        assert can_use_gateway_secret("s-1", "alice") is True

    @patch("mlflow_oidc_auth.utils.permissions.effective_gateway_secret_permission")
    def test_can_update(self, mock_eff: MagicMock) -> None:
        """can_update_gateway_secret should check can_update."""
        mock_eff.return_value.permission.can_update = True
        assert can_update_gateway_secret("s-1", "alice") is True

    @patch("mlflow_oidc_auth.utils.permissions.effective_gateway_secret_permission")
    def test_can_manage(self, mock_eff: MagicMock) -> None:
        """can_manage_gateway_secret should check can_manage."""
        mock_eff.return_value.permission.can_manage = True
        assert can_manage_gateway_secret("s-1", "alice") is True

        mock_eff.return_value.permission.can_manage = False
        assert can_manage_gateway_secret("s-1", "alice") is False


class TestEffectiveGatewayModelDefinitionPermission:
    """Tests for effective_gateway_model_definition_permission and can_* wrappers."""

    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_effective_delegates_to_store_or_default(
        self, mock_resolver: MagicMock
    ) -> None:
        """Should delegate to get_permission_from_store_or_default."""
        mock_result = MagicMock()
        mock_resolver.return_value = mock_result

        result = effective_gateway_model_definition_permission("m-1", "alice")

        assert result is mock_result
        mock_resolver.assert_called_once()

    @patch(
        "mlflow_oidc_auth.utils.permissions.effective_gateway_model_definition_permission"
    )
    def test_can_read(self, mock_eff: MagicMock) -> None:
        """can_read_gateway_model_definition should check can_read."""
        mock_eff.return_value.permission.can_read = True
        assert can_read_gateway_model_definition("m-1", "alice") is True

    @patch(
        "mlflow_oidc_auth.utils.permissions.effective_gateway_model_definition_permission"
    )
    def test_can_use(self, mock_eff: MagicMock) -> None:
        """can_use_gateway_model_definition should check can_use."""
        mock_eff.return_value.permission.can_use = True
        assert can_use_gateway_model_definition("m-1", "alice") is True

    @patch(
        "mlflow_oidc_auth.utils.permissions.effective_gateway_model_definition_permission"
    )
    def test_can_update(self, mock_eff: MagicMock) -> None:
        """can_update_gateway_model_definition should check can_update."""
        mock_eff.return_value.permission.can_update = True
        assert can_update_gateway_model_definition("m-1", "alice") is True

    @patch(
        "mlflow_oidc_auth.utils.permissions.effective_gateway_model_definition_permission"
    )
    def test_can_manage(self, mock_eff: MagicMock) -> None:
        """can_manage_gateway_model_definition should check can_manage."""
        mock_eff.return_value.permission.can_manage = True
        assert can_manage_gateway_model_definition("m-1", "alice") is True

        mock_eff.return_value.permission.can_manage = False
        assert can_manage_gateway_model_definition("m-1", "alice") is False
