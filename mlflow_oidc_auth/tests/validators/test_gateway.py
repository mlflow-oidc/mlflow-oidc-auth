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
        """Test UPDATE resolves the current secret via secret_id (not a request secret_name)."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/secrets/update",
            method="POST",
            json={"secret_id": "sec-123"},
            content_type="application/json",
        ):
            with (
                patch(
                    "mlflow_oidc_auth.validators.gateway._resolve_secret_name_from_id",
                    return_value="my-secret",
                ),
                patch(
                    "mlflow_oidc_auth.validators.gateway.can_update_gateway_secret",
                    return_value=True,
                ),
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
        """Test READ when only ID is available (no name) — denies access per fail-closed policy."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/model-definitions/get",
            method="GET",
            query_string={"model_definition_id": "some-id"},
        ):
            # Should return False (fail-closed) since name can't be extracted
            assert validate_can_read_gateway_model_definition("user1") is False

    def test_update_gateway_model_definition_with_id(self):
        """Test UPDATE resolves the current model definition via model_definition_id.

        The ``name`` field carries the *new* name on a rename, so the check must
        resolve the current name from the id rather than trust a request ``name``.
        """
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/model-definitions/update",
            method="POST",
            json={"model_definition_id": "md-123", "name": "renamed"},
            content_type="application/json",
        ):
            with (
                patch(
                    "mlflow_oidc_auth.validators.gateway._resolve_model_definition_name_from_id",
                    return_value="my-model-def",
                ),
                patch(
                    "mlflow_oidc_auth.validators.gateway.can_update_gateway_model_definition",
                    return_value=True,
                ),
            ):
                assert validate_can_update_gateway_model_definition("user1") is True

    def test_update_gateway_model_definition_denied(self):
        """Test UPDATE denied when user lacks permission."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/model-definitions/update",
            method="POST",
            json={"model_definition_id": "md-123"},
            content_type="application/json",
        ):
            with (
                patch(
                    "mlflow_oidc_auth.validators.gateway._resolve_model_definition_name_from_id",
                    return_value="my-model-def",
                ),
                patch(
                    "mlflow_oidc_auth.validators.gateway.can_update_gateway_model_definition",
                    return_value=False,
                ),
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
        """Test DELETE returns False when no name can be resolved (ID-only, fail-closed)."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/model-definitions/delete",
            method="POST",
            json={"model_definition_id": "some-id"},
            content_type="application/json",
        ):
            assert validate_can_delete_gateway_model_definition("user1") is False

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


class TestGatewayCrossFieldBypass:
    """Regression tests for the #270 cross-field bypass.

    A request that names one resource the caller owns (via ``name``) and another
    the caller does NOT own (via ``*_id`` that MLflow actually dispatches on) must
    be denied — the caller has to be authorized on every resource referenced.
    """

    @staticmethod
    def _only_owns(owned):
        def _check(name, _username):
            return name == owned

        return _check

    def test_read_endpoint_denied_when_id_points_elsewhere(self):
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/endpoints/get",
            method="GET",
            query_string={"name": "own-endpoint", "endpoint_id": "victim-id"},
        ):
            with (
                patch(
                    "mlflow_oidc_auth.validators.gateway._resolve_endpoint_name_from_id",
                    return_value="victim-endpoint",
                ),
                patch(
                    "mlflow_oidc_auth.validators.gateway.can_read_gateway_endpoint",
                    side_effect=self._only_owns("own-endpoint"),
                ),
            ):
                assert validate_can_read_gateway_endpoint("attacker") is False

    def test_delete_endpoint_denied_when_id_points_elsewhere(self):
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/endpoints/delete",
            method="POST",
            json={"name": "own-endpoint", "endpoint_id": "victim-id"},
            content_type="application/json",
        ):
            with (
                patch(
                    "mlflow_oidc_auth.validators.gateway._resolve_endpoint_name_from_id",
                    return_value="victim-endpoint",
                ),
                patch(
                    "mlflow_oidc_auth.validators.gateway.can_manage_gateway_endpoint",
                    side_effect=self._only_owns("own-endpoint"),
                ),
            ):
                assert validate_can_delete_gateway_endpoint("attacker") is False

    def test_delete_secret_denied_when_id_points_elsewhere(self):
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/secrets/delete",
            method="POST",
            json={"secret_name": "own-secret", "secret_id": "victim-id"},
            content_type="application/json",
        ):
            with (
                patch(
                    "mlflow_oidc_auth.validators.gateway._resolve_secret_name_from_id",
                    return_value="victim-secret",
                ),
                patch(
                    "mlflow_oidc_auth.validators.gateway.can_manage_gateway_secret",
                    side_effect=self._only_owns("own-secret"),
                ),
            ):
                assert validate_can_delete_gateway_secret("attacker") is False

    def test_read_model_definition_denied_when_id_points_elsewhere(self):
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/model-definitions/get",
            method="GET",
            query_string={"name": "own-md", "model_definition_id": "victim-id"},
        ):
            with (
                patch(
                    "mlflow_oidc_auth.validators.gateway._resolve_model_definition_name_from_id",
                    return_value="victim-md",
                ),
                patch(
                    "mlflow_oidc_auth.validators.gateway.can_read_gateway_model_definition",
                    side_effect=self._only_owns("own-md"),
                ),
            ):
                assert validate_can_read_gateway_model_definition("attacker") is False

    def test_read_endpoint_allowed_when_both_name_the_same_resource(self):
        """A legit request that names one resource two ways (name + its own id) still passes."""
        with app.test_request_context(
            path="/api/3.0/mlflow/gateway/endpoints/get",
            method="GET",
            query_string={"name": "own-endpoint", "endpoint_id": "own-id"},
        ):
            with (
                patch(
                    "mlflow_oidc_auth.validators.gateway._resolve_endpoint_name_from_id",
                    return_value="own-endpoint",
                ),
                patch(
                    "mlflow_oidc_auth.validators.gateway.can_read_gateway_endpoint",
                    side_effect=self._only_owns("own-endpoint"),
                ),
            ):
                assert validate_can_read_gateway_endpoint("owner") is True


# ---------------------------------------------------------------------------
# Referenced resources: USE on the secret / model definitions
# ---------------------------------------------------------------------------

from mlflow_oidc_auth.validators import gateway as gateway_validators  # noqa: E402


def _ref_ctx(path, body):
    return app.test_request_context(path=path, method="POST", json=body, content_type="application/json")


def _names(mapping):
    return lambda resource_id: mapping.get(resource_id)


class TestReferencedSecret:
    PATH_CREATE = "/api/3.0/mlflow/gateway/model-definitions/create"
    PATH_UPDATE = "/api/3.0/mlflow/gateway/model-definitions/update"

    def test_create_without_secret_is_allowed(self):
        with _ref_ctx(self.PATH_CREATE, {"name": "md"}):
            assert gateway_validators.validate_can_create_gateway_model_definition("u") is True

    @pytest.mark.parametrize("can_use", [True, False])
    def test_create_checks_use_on_secret(self, can_use):
        with (
            _ref_ctx(self.PATH_CREATE, {"name": "md", "secret_id": "s1"}),
            patch.object(gateway_validators, "_resolve_secret_name_from_id", _names({"s1": "secret-a"})),
            patch.object(gateway_validators, "can_use_gateway_secret", return_value=can_use) as use,
        ):
            assert gateway_validators.validate_can_create_gateway_model_definition("u") is can_use
            use.assert_called_once_with("secret-a", "u")

    def test_create_with_unresolvable_secret_is_denied(self):
        with (
            _ref_ctx(self.PATH_CREATE, {"name": "md", "secret_id": "gone"}),
            patch.object(gateway_validators, "_resolve_secret_name_from_id", _names({})),
            patch.object(gateway_validators, "can_use_gateway_secret", return_value=True),
        ):
            assert gateway_validators.validate_can_create_gateway_model_definition("u") is False

    @pytest.mark.parametrize("can_use", [True, False])
    def test_update_checks_target_then_new_secret(self, can_use):
        with (
            _ref_ctx(self.PATH_UPDATE, {"model_definition_id": "md1", "secret_id": "s1"}),
            patch.object(gateway_validators, "_resolve_model_definition_name_from_id", _names({"md1": "md-a"})),
            patch.object(gateway_validators, "_resolve_secret_name_from_id", _names({"s1": "secret-a"})),
            patch.object(gateway_validators, "can_update_gateway_model_definition", return_value=True),
            patch.object(gateway_validators, "can_use_gateway_secret", return_value=can_use),
        ):
            assert gateway_validators.validate_can_update_gateway_model_definition("u") is can_use

    def test_update_denied_on_target_does_not_consult_secret(self):
        with (
            _ref_ctx(self.PATH_UPDATE, {"model_definition_id": "md1", "secret_id": "s1"}),
            patch.object(gateway_validators, "_resolve_model_definition_name_from_id", _names({"md1": "md-a"})),
            patch.object(gateway_validators, "can_update_gateway_model_definition", return_value=False),
            patch.object(gateway_validators, "can_use_gateway_secret", return_value=True) as use,
        ):
            assert gateway_validators.validate_can_update_gateway_model_definition("u") is False
            use.assert_not_called()


class TestReferencedModelDefinitions:
    CREATE = "/api/3.0/mlflow/gateway/endpoints/create"
    UPDATE = "/api/3.0/mlflow/gateway/endpoints/update"
    ATTACH = "/api/3.0/mlflow/gateway/endpoints/models/attach"
    MDS = {"md1": "md-a", "md2": "md-b"}

    def test_create_without_model_definitions_is_allowed(self):
        with _ref_ctx(self.CREATE, {"name": "ep"}):
            assert gateway_validators.validate_can_create_gateway_endpoint("u") is True

    def test_create_needs_use_on_every_model_definition(self):
        body = {"name": "ep", "model_configs": [{"model_definition_id": "md1"}, {"modelDefinitionId": "md2"}]}
        with (
            _ref_ctx(self.CREATE, body),
            patch.object(gateway_validators, "_resolve_model_definition_name_from_id", _names(self.MDS)),
            patch.object(gateway_validators, "can_use_gateway_model_definition", side_effect=lambda n, u: n == "md-a") as use,
        ):
            assert gateway_validators.validate_can_create_gateway_endpoint("u") is False
            assert [c.args[0] for c in use.call_args_list] == ["md-a", "md-b"]

    def test_create_with_unresolvable_model_definition_is_denied(self):
        with (
            _ref_ctx(self.CREATE, {"name": "ep", "model_configs": [{"model_definition_id": "gone"}]}),
            patch.object(gateway_validators, "_resolve_model_definition_name_from_id", _names(self.MDS)),
            patch.object(gateway_validators, "can_use_gateway_model_definition", return_value=True),
        ):
            assert gateway_validators.validate_can_create_gateway_endpoint("u") is False

    @pytest.mark.parametrize("can_use", [True, False])
    def test_update_config_checks_endpoint_and_model_definitions(self, can_use):
        with (
            _ref_ctx(self.UPDATE, {"endpoint_id": "ep1", "model_configs": [{"model_definition_id": "md1"}]}),
            patch.object(gateway_validators, "_resolve_endpoint_name_from_id", _names({"ep1": "ep-a"})),
            patch.object(gateway_validators, "_resolve_model_definition_name_from_id", _names(self.MDS)),
            patch.object(gateway_validators, "can_update_gateway_endpoint", return_value=True),
            patch.object(gateway_validators, "can_use_gateway_model_definition", return_value=can_use),
        ):
            assert gateway_validators.validate_can_update_gateway_endpoint_config("u") is can_use

    def test_update_config_denied_on_endpoint(self):
        with (
            _ref_ctx(self.UPDATE, {"endpoint_id": "ep1"}),
            patch.object(gateway_validators, "_resolve_endpoint_name_from_id", _names({"ep1": "ep-a"})),
            patch.object(gateway_validators, "can_update_gateway_endpoint", return_value=False),
        ):
            assert gateway_validators.validate_can_update_gateway_endpoint_config("u") is False

    @pytest.mark.parametrize("key", ["model_config", "modelConfig"])
    @pytest.mark.parametrize("can_use", [True, False])
    def test_attach_checks_endpoint_and_model_definition(self, key, can_use):
        with (
            _ref_ctx(self.ATTACH, {"endpoint_id": "ep1", key: {"model_definition_id": "md1"}}),
            patch.object(gateway_validators, "_resolve_endpoint_name_from_id", _names({"ep1": "ep-a"})),
            patch.object(gateway_validators, "_resolve_model_definition_name_from_id", _names(self.MDS)),
            patch.object(gateway_validators, "can_update_gateway_endpoint", return_value=True),
            patch.object(gateway_validators, "can_use_gateway_model_definition", return_value=can_use) as use,
        ):
            assert gateway_validators.validate_can_attach_model_to_gateway_endpoint("u") is can_use
            use.assert_called_once_with("md-a", "u")


class TestEndpointUsageExperiment:
    CREATE = "/api/3.0/mlflow/gateway/endpoints/create"
    UPDATE = "/api/3.0/mlflow/gateway/endpoints/update"

    @pytest.mark.parametrize("can_update, expected", [(True, True), (False, False)])
    def test_create_checks_update_on_experiment(self, can_update, expected):
        with (
            _ref_ctx(self.CREATE, {"name": "ep", "experiment_id": "7"}),
            patch.object(gateway_validators, "referenced_experiment_permission", return_value=MagicMock(can_update=can_update)) as perm,
        ):
            assert gateway_validators.validate_can_create_gateway_endpoint("u") is expected
            perm.assert_called_once_with("7", "u")

    def test_update_checks_update_on_experiment(self):
        with (
            _ref_ctx(self.UPDATE, {"endpoint_id": "ep1", "experimentId": "7"}),
            patch.object(gateway_validators, "_resolve_endpoint_name_from_id", _names({"ep1": "ep-a"})),
            patch.object(gateway_validators, "can_update_gateway_endpoint", return_value=True),
            patch.object(gateway_validators, "referenced_experiment_permission", return_value=MagicMock(can_update=False)) as perm,
        ):
            assert gateway_validators.validate_can_update_gateway_endpoint_config("u") is False
            perm.assert_called_once_with("7", "u")

    def test_no_experiment_is_not_checked(self):
        with (
            _ref_ctx(self.CREATE, {"name": "ep"}),
            patch.object(gateway_validators, "referenced_experiment_permission") as perm,
        ):
            assert gateway_validators.validate_can_create_gateway_endpoint("u") is True
            perm.assert_not_called()
