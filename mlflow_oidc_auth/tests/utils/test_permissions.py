"""
Test cases for mlflow_oidc_auth.utils.permissions module.

This module contains comprehensive tests for permission-related functionality
including permission retrieval, caching, and access control checks.
"""

import unittest
from unittest.mock import MagicMock, patch

from flask import Flask
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import BAD_REQUEST, RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.permissions import Permission
from mlflow_oidc_auth.models import PermissionResult
from mlflow_oidc_auth.utils import (
    can_manage_experiment,
    can_manage_registered_model,
    can_read_experiment,
    can_read_registered_model,
    effective_experiment_permission,
    effective_prompt_permission,
    effective_registered_model_permission,
    get_permission_from_store_or_default,
)
from mlflow_oidc_auth.utils.permissions import (
    PERMISSION_REGISTRY,
    _build_experiment_sources,
    _build_prompt_sources,
    _build_registered_model_sources,
    _get_experiment_group_permission_from_regex,
    _get_experiment_permission_from_regex,
    _match_regex_permission,
    resolve_permission,
)


class TestPermissions(unittest.TestCase):
    """Test cases for permissions utility functions."""

    def setUp(self) -> None:
        """Set up test environment with Flask application context."""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        """Clean up test environment."""
        self.app_context.pop()

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.config")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission")
    def test_get_permission_from_store_or_default(
        self, mock_get_permission, mock_config, mock_store
    ):
        """Test permission retrieval with fallback to default permission."""
        with self.app.test_request_context():
            mock_store_permission_user_func = MagicMock()
            mock_store_permission_group_func = MagicMock()
            mock_store_permission_user_func.return_value = "user_perm"
            mock_store_permission_group_func.return_value = "group_perm"
            mock_get_permission.return_value = Permission(
                name="perm",
                priority=1,
                can_read=True,
                can_use=True,
                can_update=True,
                can_delete=True,
                can_manage=True,
            )
            mock_config.PERMISSION_SOURCE_ORDER = ["user", "group"]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "default_perm"

            # user permission found
            result = get_permission_from_store_or_default(
                {
                    "user": mock_store_permission_user_func,
                    "group": mock_store_permission_group_func,
                }
            )
            self.assertTrue(result.permission.can_manage)
            self.assertEqual(result.kind, "user")

            # user not found, group found
            mock_store_permission_user_func.side_effect = MlflowException(
                "", RESOURCE_DOES_NOT_EXIST
            )
            result = get_permission_from_store_or_default(
                {
                    "user": mock_store_permission_user_func,
                    "group": mock_store_permission_group_func,
                }
            )
            self.assertTrue(result.permission.can_manage)
            self.assertEqual(result.kind, "group")

            # both not found, fallback to default
            mock_store_permission_group_func.side_effect = MlflowException(
                "", RESOURCE_DOES_NOT_EXIST
            )
            result = get_permission_from_store_or_default(
                {
                    "user": mock_store_permission_user_func,
                    "group": mock_store_permission_group_func,
                }
            )
            self.assertTrue(result.permission.can_manage)
            self.assertEqual(result.kind, "fallback")

            # invalid source in config
            mock_config.PERMISSION_SOURCE_ORDER = ["invalid"]
            # Just call and check fallback, don't assert logs
            result = get_permission_from_store_or_default(
                {
                    "user": mock_store_permission_user_func,
                    "group": mock_store_permission_group_func,
                }
            )
            self.assertEqual(result.kind, "fallback")

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_can_manage_experiment(
        self, mock_get_permission_from_store_or_default, mock_store
    ):
        """Test experiment management permission checking."""
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(
                    name="perm",
                    priority=1,
                    can_read=True,
                    can_use=True,
                    can_update=True,
                    can_delete=True,
                    can_manage=True,
                ),
                "user",
            )
            self.assertTrue(can_manage_experiment("exp_id", "user"))

            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(
                    name="perm",
                    priority=1,
                    can_read=True,
                    can_use=True,
                    can_update=True,
                    can_delete=True,
                    can_manage=False,
                ),
                "user",
            )
            self.assertFalse(can_manage_experiment("exp_id", "user"))

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_can_manage_registered_model(
        self, mock_get_permission_from_store_or_default, mock_store
    ):
        """Test registered model management permission checking."""
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(
                    name="perm",
                    priority=1,
                    can_read=True,
                    can_use=True,
                    can_update=True,
                    can_delete=True,
                    can_manage=True,
                ),
                "user",
            )
            self.assertTrue(can_manage_registered_model("model_name", "user"))

            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(
                    name="perm",
                    priority=1,
                    can_read=True,
                    can_use=True,
                    can_update=True,
                    can_delete=True,
                    can_manage=False,
                ),
                "user",
            )
            self.assertFalse(can_manage_registered_model("model_name", "user"))

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_effective_experiment_permission(
        self, mock_get_permission_from_store_or_default, mock_store
    ):
        """Test effective experiment permission retrieval."""
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(
                    name="perm",
                    priority=1,
                    can_read=True,
                    can_use=True,
                    can_update=True,
                    can_delete=True,
                    can_manage=True,
                ),
                "user",
            )
            result = effective_experiment_permission("exp_id", "user")
            self.assertEqual(result.kind, "user")

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_effective_registered_model_permission(
        self, mock_get_permission_from_store_or_default, mock_store
    ):
        """Test effective registered model permission retrieval."""
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(
                    name="perm",
                    priority=1,
                    can_read=True,
                    can_use=True,
                    can_update=True,
                    can_delete=True,
                    can_manage=True,
                ),
                "user",
            )
            result = effective_registered_model_permission("model_name", "user")
            self.assertEqual(result.kind, "user")

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_effective_prompt_permission(
        self, mock_get_permission_from_store_or_default, mock_store
    ):
        """Test effective prompt permission retrieval."""
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(
                    name="perm",
                    priority=1,
                    can_read=True,
                    can_use=True,
                    can_update=True,
                    can_delete=True,
                    can_manage=True,
                ),
                "user",
            )
            result = effective_prompt_permission("model_name", "user")
            self.assertEqual(result.kind, "user")

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_can_read_experiment(
        self, mock_get_permission_from_store_or_default, mock_store
    ):
        """Test experiment read permission checking."""
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(
                    name="perm",
                    priority=1,
                    can_read=True,
                    can_use=True,
                    can_update=True,
                    can_delete=True,
                    can_manage=True,
                ),
                "user",
            )
            self.assertTrue(can_read_experiment("exp_id", "user"))

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_can_read_registered_model(
        self, mock_get_permission_from_store_or_default, mock_store
    ):
        """Test registered model read permission checking."""
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(
                    name="perm",
                    priority=1,
                    can_read=True,
                    can_use=True,
                    can_update=True,
                    can_delete=True,
                    can_manage=True,
                ),
                "user",
            )
            self.assertTrue(can_read_registered_model("model_name", "user"))

    @patch("mlflow_oidc_auth.utils.permissions.store")
    def test_match_regex_permission(self, mock_store):
        """Test generic regex permission matching."""
        from mlflow_oidc_auth.entities import RegisteredModelRegexPermission

        regex_perms = [
            RegisteredModelRegexPermission(
                id_=1, regex="test.*", permission="READ", priority=1, user_id=1
            ),
            RegisteredModelRegexPermission(
                id_=2, regex="prod.*", permission="MANAGE", priority=2, user_id=1
            ),
        ]

        # Match found
        result = _match_regex_permission(regex_perms, "test-model", "model name")
        self.assertEqual(result, "READ")

        # No match
        with self.assertRaises(MlflowException) as cm:
            _match_regex_permission(regex_perms, "other-model", "model name")
        self.assertEqual(cm.exception.error_code, "RESOURCE_DOES_NOT_EXIST")

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions._get_tracking_store")
    def test_get_experiment_permission_from_regex(
        self, mock_tracking_store, mock_store
    ):
        """Test experiment permission retrieval from regex patterns."""
        from mlflow_oidc_auth.entities import ExperimentRegexPermission

        mock_experiment = MagicMock()
        mock_experiment.name = "test-experiment"
        mock_tracking_store.return_value.get_experiment.return_value = mock_experiment

        regex_perms = [
            ExperimentRegexPermission(
                id_=1, regex="test.*", permission="READ", priority=1, user_id=1
            ),
            ExperimentRegexPermission(
                id_=2, regex="prod.*", permission="MANAGE", priority=2, user_id=1
            ),
        ]

        # Match found
        result = _get_experiment_permission_from_regex(regex_perms, "exp123")
        self.assertEqual(result, "READ")

        # No match
        mock_experiment.name = "other-experiment"
        with self.assertRaises(MlflowException) as cm:
            _get_experiment_permission_from_regex(regex_perms, "exp123")
        self.assertEqual(cm.exception.error_code, "RESOURCE_DOES_NOT_EXIST")

    @patch("mlflow_oidc_auth.utils.permissions.store")
    def test_match_regex_permission_group(self, mock_store):
        """Test group regex permission matching via generic matcher."""
        from mlflow_oidc_auth.entities import RegisteredModelGroupRegexPermission

        regex_perms = [
            RegisteredModelGroupRegexPermission(
                id_=1, regex="test.*", permission="READ", priority=1, group_id=1
            ),
            RegisteredModelGroupRegexPermission(
                id_=2, regex="prod.*", permission="MANAGE", priority=2, group_id=1
            ),
        ]

        # Match found
        result = _match_regex_permission(regex_perms, "test-model", "model name")
        self.assertEqual(result, "READ")

        # No match
        with self.assertRaises(MlflowException) as cm:
            _match_regex_permission(regex_perms, "other-model", "model name")
        self.assertEqual(cm.exception.error_code, "RESOURCE_DOES_NOT_EXIST")

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions._get_tracking_store")
    def test_get_experiment_group_permission_from_regex(
        self, mock_tracking_store, mock_store
    ):
        """Test experiment group permission retrieval from regex patterns."""
        from mlflow_oidc_auth.entities import ExperimentGroupRegexPermission

        mock_experiment = MagicMock()
        mock_experiment.name = "test-experiment"
        mock_tracking_store.return_value.get_experiment.return_value = mock_experiment

        regex_perms = [
            ExperimentGroupRegexPermission(
                id_=1, regex="test.*", permission="READ", priority=1, group_id=1
            ),
            ExperimentGroupRegexPermission(
                id_=2, regex="prod.*", permission="MANAGE", priority=2, group_id=1
            ),
        ]

        # Match found
        result = _get_experiment_group_permission_from_regex(regex_perms, "exp123")
        self.assertEqual(result, "READ")

        # No match
        mock_experiment.name = "other-experiment"
        with self.assertRaises(MlflowException) as cm:
            _get_experiment_group_permission_from_regex(regex_perms, "exp123")
        self.assertEqual(cm.exception.error_code, "RESOURCE_DOES_NOT_EXIST")

    @patch("mlflow_oidc_auth.utils.permissions.store")
    def test_build_sources_config(self, mock_store):
        """Test builder functions return correct source keys."""
        # Test prompt builder
        config = _build_prompt_sources("model1", "user1")
        self.assertIn("user", config)
        self.assertIn("group", config)
        self.assertIn("regex", config)
        self.assertIn("group-regex", config)

        # Test experiment builder
        config = _build_experiment_sources("exp1", "user1")
        self.assertIn("user", config)
        self.assertIn("group", config)
        self.assertIn("regex", config)
        self.assertIn("group-regex", config)

        # Test registered model builder
        config = _build_registered_model_sources("model1", "user1")
        self.assertIn("user", config)
        self.assertIn("group", config)
        self.assertIn("regex", config)
        self.assertIn("group-regex", config)

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.config")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission")
    def test_get_permission_from_store_or_default_non_resource_exception(
        self, mock_get_permission, mock_config, mock_store
    ):
        """Test permission retrieval with non-resource exceptions."""
        with self.app.test_request_context():
            mock_store_permission_user_func = MagicMock()
            mock_store_permission_user_func.side_effect = MlflowException(
                "Other error", BAD_REQUEST
            )

            mock_config.PERMISSION_SOURCE_ORDER = ["user"]

            with self.assertRaises(MlflowException) as cm:
                get_permission_from_store_or_default(
                    {"user": mock_store_permission_user_func}
                )
            self.assertEqual(cm.exception.error_code, "BAD_REQUEST")


class TestResolvePermission(unittest.TestCase):
    """Tests for resolve_permission() and PERMISSION_REGISTRY."""

    def test_registry_has_seven_entries(self) -> None:
        """PERMISSION_REGISTRY should contain exactly 7 resource types."""
        self.assertEqual(len(PERMISSION_REGISTRY), 7)
        self.assertIn("experiment", PERMISSION_REGISTRY)
        self.assertIn("registered_model", PERMISSION_REGISTRY)
        self.assertIn("prompt", PERMISSION_REGISTRY)
        self.assertIn("scorer", PERMISSION_REGISTRY)
        self.assertIn("gateway_endpoint", PERMISSION_REGISTRY)
        self.assertIn("gateway_secret", PERMISSION_REGISTRY)
        self.assertIn("gateway_model_definition", PERMISSION_REGISTRY)

    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_resolve_experiment_calls_builder_and_resolver(self, mock_resolver):
        """resolve_permission('experiment', ...) should call the experiment builder from PERMISSION_REGISTRY and then get_permission_from_store_or_default."""
        mock_builder = MagicMock()
        mock_sources = {"user": MagicMock(), "group": MagicMock()}
        mock_builder.return_value = mock_sources
        mock_resolver.return_value = MagicMock()

        with patch.dict(
            "mlflow_oidc_auth.utils.permissions.PERMISSION_REGISTRY",
            {"experiment": mock_builder},
        ):
            resolve_permission("experiment", "exp-1", "user1")

        mock_builder.assert_called_once_with("exp-1", "user1")
        mock_resolver.assert_called_once_with(mock_sources)

    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_resolve_scorer_passes_kwargs(self, mock_resolver):
        """resolve_permission('scorer', ..., scorer_name='s1') should pass scorer_name through **kwargs."""
        mock_builder = MagicMock()
        mock_sources = {"user": MagicMock()}
        mock_builder.return_value = mock_sources
        mock_resolver.return_value = MagicMock()

        with patch.dict(
            "mlflow_oidc_auth.utils.permissions.PERMISSION_REGISTRY",
            {"scorer": mock_builder},
        ):
            resolve_permission("scorer", "exp-1", "user1", scorer_name="scorer-1")

        mock_builder.assert_called_once_with("exp-1", "user1", scorer_name="scorer-1")
        mock_resolver.assert_called_once_with(mock_sources)

    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_resolve_prompt_routes_to_prompt_builder(self, mock_resolver):
        """resolve_permission('prompt', ...) should route to the prompt builder."""
        mock_builder = MagicMock()
        mock_sources = {"user": MagicMock()}
        mock_builder.return_value = mock_sources
        mock_resolver.return_value = MagicMock()

        with patch.dict(
            "mlflow_oidc_auth.utils.permissions.PERMISSION_REGISTRY",
            {"prompt": mock_builder},
        ):
            resolve_permission("prompt", "model-1", "user1")

        mock_builder.assert_called_once_with("model-1", "user1")
        mock_resolver.assert_called_once_with(mock_sources)

    def test_resolve_unknown_type_raises_key_error(self) -> None:
        """resolve_permission('unknown_type', ...) should raise KeyError."""
        with self.assertRaises(KeyError):
            resolve_permission("unknown_type", "id-1", "user1")


if __name__ == "__main__":
    unittest.main()
