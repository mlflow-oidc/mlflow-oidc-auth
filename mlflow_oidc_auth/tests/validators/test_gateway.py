"""Unit tests for AI Gateway validators."""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

from mlflow_oidc_auth.validators.gateway import (
    validate_can_read_gateway_endpoint,
    validate_can_update_gateway_endpoint,
    validate_can_delete_gateway_endpoint,
    validate_can_manage_gateway_endpoint_validator,
    validate_can_read_gateway_secret,
    validate_can_update_gateway_secret,
    validate_can_delete_gateway_secret,
    validate_can_read_gateway_model_definition,
    validate_can_update_gateway_model_definition,
    validate_can_delete_gateway_model_definition,
)

app = Flask(__name__)


class TestGatewayEndpointValidators:
    """Tests for gateway endpoint validators."""

    def test_read_gateway_endpoint_allowed(self):
        """Test READ when user has permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/endpoints/get",
            method="GET",
            query_string={"name": "my-endpoint"},
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway.can_read_gateway_endpoint",
                return_value=True,
            ):
                assert validate_can_read_gateway_endpoint("user1") is True

    def test_read_gateway_endpoint_denied(self):
        """Test READ when user lacks permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/endpoints/get",
            method="GET",
            query_string={"name": "my-endpoint"},
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway.can_read_gateway_endpoint",
                return_value=False,
            ):
                assert validate_can_read_gateway_endpoint("user1") is False

    def test_read_gateway_endpoint_no_name(self):
        """Test READ when no name provided returns False."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/endpoints/get",
            method="GET",
            query_string={},
        ):
            assert validate_can_read_gateway_endpoint("user1") is False

    def test_update_gateway_endpoint_allowed(self):
        """Test UPDATE when user has permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/endpoints/update",
            method="POST",
            json={"endpoint_id": "ep-uuid-123", "name": "new-name"},
            content_type="application/json",
        ):
            with (
                patch(
                    "mlflow_oidc_auth.validators.gateway._resolve_endpoint_name_from_id",
                    return_value="my-endpoint",
                ),
                patch(
                    "mlflow_oidc_auth.validators.gateway.can_update_gateway_endpoint",
                    return_value=True,
                ),
            ):
                assert validate_can_update_gateway_endpoint("user1") is True

    def test_update_gateway_endpoint_denied(self):
        """Test UPDATE when user lacks permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/endpoints/update",
            method="POST",
            json={"endpoint_id": "ep-uuid-123", "name": "new-name"},
            content_type="application/json",
        ):
            with (
                patch(
                    "mlflow_oidc_auth.validators.gateway._resolve_endpoint_name_from_id",
                    return_value="my-endpoint",
                ),
                patch(
                    "mlflow_oidc_auth.validators.gateway.can_update_gateway_endpoint",
                    return_value=False,
                ),
            ):
                assert validate_can_update_gateway_endpoint("user1") is False

    def test_update_gateway_endpoint_no_endpoint_id(self):
        """Test UPDATE returns False when endpoint_id cannot be resolved."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/endpoints/update",
            method="POST",
            json={"name": "new-name"},
            content_type="application/json",
        ):
            assert validate_can_update_gateway_endpoint("user1") is False

    def test_manage_gateway_endpoint_allowed(self):
        """Test MANAGE when user has permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/endpoints/get",
            method="GET",
            query_string={"name": "my-endpoint"},
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway.can_manage_gateway_endpoint",
                return_value=True,
            ):
                assert validate_can_manage_gateway_endpoint_validator("user1") is True

    def test_delete_gateway_endpoint_allowed(self):
        """Test DELETE when user has MANAGE permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/endpoints/delete",
            method="POST",
            json={"name": "my-endpoint"},
            content_type="application/json",
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway.can_manage_gateway_endpoint",
                return_value=True,
            ):
                assert validate_can_delete_gateway_endpoint("user1") is True

    def test_delete_gateway_endpoint_denied(self):
        """Test DELETE denied when user lacks MANAGE permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/endpoints/delete",
            method="POST",
            json={"name": "my-endpoint"},
            content_type="application/json",
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway.can_manage_gateway_endpoint",
                return_value=False,
            ):
                assert validate_can_delete_gateway_endpoint("user1") is False

    def test_read_gateway_endpoint_fallback_to_id(self):
        """Test READ falls back to resolving endpoint_id via tracking store."""
        mock_endpoint = MagicMock()
        mock_endpoint.name = "resolved-endpoint"
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/endpoints/get",
            method="GET",
            query_string={"endpoint_id": "ep-123"},
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway._resolve_endpoint_name_from_id",
                return_value="resolved-endpoint",
            ):
                with patch(
                    "mlflow_oidc_auth.validators.gateway.can_read_gateway_endpoint",
                    return_value=True,
                ):
                    assert validate_can_read_gateway_endpoint("user1") is True


class TestGatewaySecretValidators:
    """Tests for gateway secret validators."""

    def test_read_gateway_secret_allowed(self):
        """Test READ when user has permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/secrets/get",
            method="GET",
            query_string={"secret_name": "my-secret"},
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway.can_read_gateway_secret",
                return_value=True,
            ):
                assert validate_can_read_gateway_secret("user1") is True

    def test_read_gateway_secret_denied(self):
        """Test READ when user lacks permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/secrets/get",
            method="GET",
            query_string={"secret_name": "my-secret"},
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway.can_read_gateway_secret",
                return_value=False,
            ):
                assert validate_can_read_gateway_secret("user1") is False

    def test_read_gateway_secret_no_name(self):
        """Test READ when no secret_name provided returns False."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/secrets/get",
            method="GET",
            query_string={},
        ):
            assert validate_can_read_gateway_secret("user1") is False

    def test_update_gateway_secret_allowed(self):
        """Test UPDATE when user has permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/secrets/update",
            method="POST",
            json={"secret_name": "my-secret"},
            content_type="application/json",
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway.can_update_gateway_secret",
                return_value=True,
            ):
                assert validate_can_update_gateway_secret("user1") is True

    def test_delete_gateway_secret_allowed(self):
        """Test DELETE when user has MANAGE permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/secrets/delete",
            method="POST",
            json={"secret_name": "my-secret"},
            content_type="application/json",
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway.can_manage_gateway_secret",
                return_value=True,
            ):
                assert validate_can_delete_gateway_secret("user1") is True

    def test_delete_gateway_secret_denied(self):
        """Test DELETE denied when user lacks MANAGE permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/secrets/delete",
            method="POST",
            json={"secret_name": "my-secret"},
            content_type="application/json",
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway.can_manage_gateway_secret",
                return_value=False,
            ):
                assert validate_can_delete_gateway_secret("user1") is False

    def test_read_gateway_secret_fallback_to_id(self):
        """Test READ falls back to resolving secret_id via tracking store."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/secrets/get",
            method="GET",
            query_string={"secret_id": "sec-123"},
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway._resolve_secret_name_from_id",
                return_value="resolved-secret",
            ):
                with patch(
                    "mlflow_oidc_auth.validators.gateway.can_read_gateway_secret",
                    return_value=True,
                ):
                    assert validate_can_read_gateway_secret("user1") is True


class TestGatewayModelDefinitionValidators:
    """Tests for gateway model definition validators."""

    def test_read_gateway_model_definition_with_name(self):
        """Test READ when name is available and user has permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/model-definitions/get",
            method="GET",
            query_string={"name": "my-model-def"},
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway.can_read_gateway_model_definition",
                return_value=True,
            ):
                assert validate_can_read_gateway_model_definition("user1") is True

    def test_read_gateway_model_definition_no_name_fallback(self):
        """Test READ when only ID is available (no name) — allows through per design."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/model-definitions/get",
            method="GET",
            query_string={"model_definition_id": "some-id"},
        ):
            # Should return True (fallback) since name can't be extracted
            assert validate_can_read_gateway_model_definition("user1") is True

    def test_update_gateway_model_definition_with_name(self):
        """Test UPDATE when name is available and user has permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/model-definitions/update",
            method="POST",
            json={"name": "my-model-def"},
            content_type="application/json",
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway.can_update_gateway_model_definition",
                return_value=True,
            ):
                assert validate_can_update_gateway_model_definition("user1") is True

    def test_update_gateway_model_definition_denied(self):
        """Test UPDATE denied when user lacks permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/model-definitions/update",
            method="POST",
            json={"name": "my-model-def"},
            content_type="application/json",
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway.can_update_gateway_model_definition",
                return_value=False,
            ):
                assert validate_can_update_gateway_model_definition("user1") is False

    def test_delete_gateway_model_definition_allowed(self):
        """Test DELETE when user has MANAGE permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/model-definitions/delete",
            method="POST",
            json={"name": "my-model-def"},
            content_type="application/json",
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway.can_manage_gateway_model_definition",
                return_value=True,
            ):
                assert validate_can_delete_gateway_model_definition("user1") is True

    def test_delete_gateway_model_definition_denied(self):
        """Test DELETE denied when user lacks MANAGE permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/model-definitions/delete",
            method="POST",
            json={"name": "my-model-def"},
            content_type="application/json",
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway.can_manage_gateway_model_definition",
                return_value=False,
            ):
                assert validate_can_delete_gateway_model_definition("user1") is False

    def test_delete_gateway_model_definition_no_name_fallback(self):
        """Test DELETE returns True when no name can be resolved (ID-only)."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/model-definitions/delete",
            method="POST",
            json={"model_definition_id": "some-id"},
            content_type="application/json",
        ):
            assert validate_can_delete_gateway_model_definition("user1") is True

    def test_read_model_definition_fallback_to_id(self):
        """Test READ falls back to resolving model_definition_id via tracking store."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/model-definitions/get",
            method="GET",
            query_string={"model_definition_id": "md-123"},
        ):
            with patch(
                "mlflow_oidc_auth.validators.gateway._resolve_model_definition_name_from_id",
                return_value="resolved-model-def",
            ):
                with patch(
                    "mlflow_oidc_auth.validators.gateway.can_read_gateway_model_definition",
                    return_value=True,
                ):
                    assert validate_can_read_gateway_model_definition("user1") is True
