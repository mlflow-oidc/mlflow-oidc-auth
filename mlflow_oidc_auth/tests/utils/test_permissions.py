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
from mlflow_oidc_auth.utils.types import PermissionResult
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
    _get_registered_model_permission_from_regex,
    _get_experiment_permission_from_regex,
    _get_registered_model_group_permission_from_regex,
    _get_experiment_group_permission_from_regex,
    _permission_prompt_sources_config,
    _permission_experiment_sources_config,
    _permission_registered_model_sources_config,
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
    def test_get_permission_from_store_or_default(self, mock_get_permission, mock_config, mock_store):
        """Test permission retrieval with fallback to default permission."""
        with self.app.test_request_context():
            mock_store_permission_user_func = MagicMock()
            mock_store_permission_group_func = MagicMock()
            mock_store_permission_user_func.return_value = "user_perm"
            mock_store_permission_group_func.return_value = "group_perm"
            mock_get_permission.return_value = Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=True)
            mock_config.PERMISSION_SOURCE_ORDER = ["user", "group"]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "default_perm"

            # user permission found
            result = get_permission_from_store_or_default({"user": mock_store_permission_user_func, "group": mock_store_permission_group_func})
            self.assertTrue(result.permission.can_manage)
            self.assertEqual(result.type, "user")

            # user not found, group found
            mock_store_permission_user_func.side_effect = MlflowException("", RESOURCE_DOES_NOT_EXIST)
            result = get_permission_from_store_or_default({"user": mock_store_permission_user_func, "group": mock_store_permission_group_func})
            self.assertTrue(result.permission.can_manage)
            self.assertEqual(result.type, "group")

            # both not found, fallback to default
            mock_store_permission_group_func.side_effect = MlflowException("", RESOURCE_DOES_NOT_EXIST)
            result = get_permission_from_store_or_default({"user": mock_store_permission_user_func, "group": mock_store_permission_group_func})
            self.assertTrue(result.permission.can_manage)
            self.assertEqual(result.type, "fallback")

            # invalid source in config
            mock_config.PERMISSION_SOURCE_ORDER = ["invalid"]
            # Just call and check fallback, don't assert logs
            result = get_permission_from_store_or_default({"user": mock_store_permission_user_func, "group": mock_store_permission_group_func})
            self.assertEqual(result.type, "fallback")

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_can_manage_experiment(self, mock_get_permission_from_store_or_default, mock_store):
        """Test experiment management permission checking."""
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=True), "user"
            )
            self.assertTrue(can_manage_experiment("exp_id", "user"))

            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=False), "user"
            )
            self.assertFalse(can_manage_experiment("exp_id", "user"))

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_can_manage_registered_model(self, mock_get_permission_from_store_or_default, mock_store):
        """Test registered model management permission checking."""
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=True), "user"
            )
            self.assertTrue(can_manage_registered_model("model_name", "user"))

            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=False), "user"
            )
            self.assertFalse(can_manage_registered_model("model_name", "user"))

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_effective_experiment_permission(self, mock_get_permission_from_store_or_default, mock_store):
        """Test effective experiment permission retrieval."""
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=True), "user"
            )
            result = effective_experiment_permission("exp_id", "user")
            self.assertEqual(result.type, "user")

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_effective_registered_model_permission(self, mock_get_permission_from_store_or_default, mock_store):
        """Test effective registered model permission retrieval."""
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=True), "user"
            )
            result = effective_registered_model_permission("model_name", "user")
            self.assertEqual(result.type, "user")

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_effective_prompt_permission(self, mock_get_permission_from_store_or_default, mock_store):
        """Test effective prompt permission retrieval."""
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=True), "user"
            )
            result = effective_prompt_permission("model_name", "user")
            self.assertEqual(result.type, "user")

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_can_read_experiment(self, mock_get_permission_from_store_or_default, mock_store):
        """Test experiment read permission checking."""
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=True), "user"
            )
            self.assertTrue(can_read_experiment("exp_id", "user"))

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission_from_store_or_default")
    def test_can_read_registered_model(self, mock_get_permission_from_store_or_default, mock_store):
        """Test registered model read permission checking."""
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=True), "user"
            )
            self.assertTrue(can_read_registered_model("model_name", "user"))

    @patch("mlflow_oidc_auth.utils.permissions.store")
    def test_get_registered_model_permission_from_regex(self, mock_store):
        """Test registered model permission retrieval from regex patterns."""
        from mlflow_oidc_auth.entities import RegisteredModelRegexPermission

        regex_perms = [
            RegisteredModelRegexPermission(regex="test.*", permission="READ", priority=1, user_id=1),
            RegisteredModelRegexPermission(regex="prod.*", permission="MANAGE", priority=2, user_id=1),
        ]

        # Match found
        result = _get_registered_model_permission_from_regex(regex_perms, "test-model")
        self.assertEqual(result, "READ")

        # No match
        with self.assertRaises(MlflowException) as cm:
            _get_registered_model_permission_from_regex(regex_perms, "other-model")
        self.assertEqual(cm.exception.error_code, "RESOURCE_DOES_NOT_EXIST")

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions._get_tracking_store")
    def test_get_experiment_permission_from_regex(self, mock_tracking_store, mock_store):
        """Test experiment permission retrieval from regex patterns."""
        from mlflow_oidc_auth.entities import ExperimentRegexPermission

        mock_experiment = MagicMock()
        mock_experiment.name = "test-experiment"
        mock_tracking_store.return_value.get_experiment.return_value = mock_experiment

        regex_perms = [
            ExperimentRegexPermission(regex="test.*", permission="READ", priority=1, user_id=1),
            ExperimentRegexPermission(regex="prod.*", permission="MANAGE", priority=2, user_id=1),
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
    def test_get_registered_model_group_permission_from_regex(self, mock_store):
        """Test registered model group permission retrieval from regex patterns."""
        from mlflow_oidc_auth.entities import RegisteredModelGroupRegexPermission

        regex_perms = [
            RegisteredModelGroupRegexPermission(id_=1, regex="test.*", permission="READ", priority=1, group_id=1),
            RegisteredModelGroupRegexPermission(id_=2, regex="prod.*", permission="MANAGE", priority=2, group_id=1),
        ]

        # Match found
        result = _get_registered_model_group_permission_from_regex(regex_perms, "test-model")
        self.assertEqual(result, "READ")

        # No match
        with self.assertRaises(MlflowException) as cm:
            _get_registered_model_group_permission_from_regex(regex_perms, "other-model")
        self.assertEqual(cm.exception.error_code, "RESOURCE_DOES_NOT_EXIST")

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions._get_tracking_store")
    def test_get_experiment_group_permission_from_regex(self, mock_tracking_store, mock_store):
        """Test experiment group permission retrieval from regex patterns."""
        from mlflow_oidc_auth.entities import ExperimentGroupRegexPermission

        mock_experiment = MagicMock()
        mock_experiment.name = "test-experiment"
        mock_tracking_store.return_value.get_experiment.return_value = mock_experiment

        regex_perms = [
            ExperimentGroupRegexPermission(id_=1, regex="test.*", permission="READ", priority=1, group_id=1),
            ExperimentGroupRegexPermission(id_=2, regex="prod.*", permission="MANAGE", priority=2, group_id=1),
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
    def test_permission_sources_config(self, mock_store):
        """Test permission sources configuration functions."""
        # Test prompt sources config
        config = _permission_prompt_sources_config("model1", "user1")
        self.assertIn("user", config)
        self.assertIn("group", config)
        self.assertIn("regex", config)
        self.assertIn("group-regex", config)

        # Test experiment sources config
        config = _permission_experiment_sources_config("exp1", "user1")
        self.assertIn("user", config)
        self.assertIn("group", config)
        self.assertIn("regex", config)
        self.assertIn("group-regex", config)

        # Test registered model sources config
        config = _permission_registered_model_sources_config("model1", "user1")
        self.assertIn("user", config)
        self.assertIn("group", config)
        self.assertIn("regex", config)
        self.assertIn("group-regex", config)

    @patch("mlflow_oidc_auth.utils.permissions.store")
    @patch("mlflow_oidc_auth.utils.permissions.config")
    @patch("mlflow_oidc_auth.utils.permissions.get_permission")
    def test_get_permission_from_store_or_default_non_resource_exception(self, mock_get_permission, mock_config, mock_store):
        """Test permission retrieval with non-resource exceptions."""
        with self.app.test_request_context():
            mock_store_permission_user_func = MagicMock()
            mock_store_permission_user_func.side_effect = MlflowException("Other error", BAD_REQUEST)

            mock_config.PERMISSION_SOURCE_ORDER = ["user"]

            with self.assertRaises(MlflowException) as cm:
                get_permission_from_store_or_default({"user": mock_store_permission_user_func})
            self.assertEqual(cm.exception.error_code, "BAD_REQUEST")


if __name__ == "__main__":
    unittest.main()
