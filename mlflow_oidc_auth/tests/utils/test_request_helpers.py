"""
Test cases for mlflow_oidc_auth.utils.request_helpers module.

This module contains comprehensive tests for request handling functionality
including parameter extraction, authentication, and user information retrieval.
"""

import unittest
from unittest.mock import MagicMock, patch

from flask import Flask
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE, RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.utils import (
    get_url_param,
    get_optional_url_param,
    get_request_param,
    get_optional_request_param,
    get_username,
    get_is_admin,
    get_experiment_id,
    get_model_id,
    get_model_name,
)
from mlflow_oidc_auth.utils.request_helpers import _experiment_id_from_name


class TestRequestHelpers(unittest.TestCase):
    """Test cases for request helper utility functions."""

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

    @patch("mlflow_oidc_auth.utils.request_helpers.store")
    @patch("mlflow_oidc_auth.utils.request_helpers.get_username")
    def test_get_is_admin(self, mock_get_username, mock_store):
        """Test admin status retrieval for current user."""
        with self.app.test_request_context():
            mock_get_username.return_value = "user"
            mock_store.get_user.return_value.is_admin = True
            self.assertTrue(get_is_admin())
            mock_store.get_user.return_value.is_admin = False
            self.assertFalse(get_is_admin())

    def test_get_request_param(self):
        """Test request parameter extraction from various sources."""
        # Query args
        with self.app.test_request_context("/?param=value", method="GET"):
            self.assertEqual(get_request_param("param"), "value")

        # JSON data
        with self.app.test_request_context("/", method="POST", json={"param": "json_value"}, content_type="application/json"):
            self.assertEqual(get_request_param("param"), "json_value")

        # Form data
        with self.app.test_request_context("/", method="POST", data={"param": "form_value"}):
            self.assertEqual(get_request_param("param"), "form_value")

        # Missing parameter
        with self.app.test_request_context("/", method="GET"):
            with self.assertRaises(MlflowException) as cm:
                get_request_param("missing_param")
            self.assertEqual(cm.exception.error_code, "INVALID_PARAMETER_VALUE")

        # Empty parameter
        with self.app.test_request_context("/?param=", method="GET"):
            with self.assertRaises(MlflowException) as cm:
                get_request_param("param")
            self.assertEqual(cm.exception.error_code, "INVALID_PARAMETER_VALUE")

    def test_get_optional_request_param(self):
        """Test optional request parameter extraction."""
        # Query args
        with self.app.test_request_context("/?param=value", method="GET"):
            self.assertEqual(get_optional_request_param("param"), "value")

        # Missing parameter with default (note: function doesn't support default, just returns None)
        with self.app.test_request_context("/", method="GET"):
            self.assertIsNone(get_optional_request_param("missing_param"))

        # Missing parameter without default
        with self.app.test_request_context("/", method="GET"):
            self.assertIsNone(get_optional_request_param("missing_param"))

    @patch("mlflow_oidc_auth.utils.request_helpers._get_tracking_store")
    def test_get_experiment_id(self, mock_tracking_store):
        """Test experiment ID extraction from request parameters."""
        # Direct experiment_id
        with self.app.test_request_context("/?experiment_id=123", method="GET"):
            self.assertEqual(get_experiment_id(), "123")

        # Experiment name lookup
        mock_experiment = MagicMock()
        mock_experiment.experiment_id = "456"
        mock_tracking_store.return_value.get_experiment_by_name.return_value = mock_experiment
        with self.app.test_request_context("/?experiment_name=test", method="GET"):
            self.assertEqual(get_experiment_id(), "456")
            mock_tracking_store.return_value.get_experiment_by_name.assert_called_with("test")

        # Missing both
        with self.app.test_request_context("/", method="GET"):
            with self.assertRaises(MlflowException) as cm:
                get_experiment_id()
            self.assertEqual(cm.exception.error_code, "INVALID_PARAMETER_VALUE")

    @patch("mlflow_oidc_auth.utils.request_helpers.validate_token")
    @patch("mlflow_oidc_auth.utils.request_helpers.store")
    def test_get_username(self, mock_store, mock_validate_token):
        """Test username extraction from authentication headers."""
        # Basic auth
        with self.app.test_request_context("/", headers={"Authorization": "Basic dGVzdDp0ZXN0"}):
            mock_store.get_user.return_value.username = "test"
            self.assertEqual(get_username(), "test")

        # Bearer token
        mock_validate_token.return_value = {"email": "user@example.com"}
        with self.app.test_request_context("/", headers={"Authorization": "Bearer token123"}):
            self.assertEqual(get_username(), "user@example.com")

        # No auth header
        with self.app.test_request_context("/"):
            with self.assertRaises(MlflowException) as cm:
                get_username()
            self.assertEqual(cm.exception.error_code, "INVALID_PARAMETER_VALUE")

    @patch("mlflow_oidc_auth.utils.request_helpers._get_tracking_store")
    def test_get_experiment_id_experiment_name_not_found(self, mock_tracking_store):
        """Test experiment ID extraction when experiment name is not found."""
        mock_tracking_store.return_value.get_experiment_by_name.side_effect = MlflowException("Not found", RESOURCE_DOES_NOT_EXIST)

        with self.app.test_request_context("/?experiment_name=nonexistent", method="GET"):
            with self.assertRaises(MlflowException) as cm:
                get_experiment_id()
            self.assertEqual(cm.exception.error_code, "RESOURCE_DOES_NOT_EXIST")

    def test_get_url_param(self):
        """Test URL parameter extraction from view arguments."""
        with self.app.test_request_context("/user/123"):
            with patch("mlflow_oidc_auth.utils.request_helpers.request") as mock_request:
                mock_request.view_args = {"param": "value"}
                self.assertEqual(get_url_param("param"), "value")

        # Missing parameter
        with self.app.test_request_context("/"):
            with patch("mlflow_oidc_auth.utils.request_helpers.request") as mock_request:
                mock_request.view_args = {}
                with self.assertRaises(MlflowException) as cm:
                    get_url_param("missing_param")
                self.assertEqual(cm.exception.error_code, "INVALID_PARAMETER_VALUE")

    def test_get_optional_url_param(self):
        """Test optional URL parameter extraction."""
        with self.app.test_request_context("/user/123"):
            with patch("mlflow_oidc_auth.utils.request_helpers.request") as mock_request:
                mock_request.view_args = {"param": "value"}
                self.assertEqual(get_optional_url_param("param"), "value")

        # Missing parameter (note: function doesn't support default, just returns None)
        with self.app.test_request_context("/"):
            with patch("mlflow_oidc_auth.utils.request_helpers.request") as mock_request:
                mock_request.view_args = {}
                self.assertIsNone(get_optional_url_param("missing_param"))

        # Missing parameter without default
        with self.app.test_request_context("/"):
            with patch("mlflow_oidc_auth.utils.request_helpers.request") as mock_request:
                mock_request.view_args = {}
                self.assertIsNone(get_optional_url_param("missing_param"))

    def test_get_model_name(self):
        """Test model name extraction from request parameters."""
        # View args
        with self.app.test_request_context("/model/test_model"):
            with patch("mlflow_oidc_auth.utils.request_helpers.request") as mock_request:
                mock_request.view_args = {"name": "test_model"}
                mock_request.args = {}
                mock_request.json = None
                self.assertEqual(get_model_name(), "test_model")

        # Query args
        with self.app.test_request_context("/?name=query_model", method="GET"):
            self.assertEqual(get_model_name(), "query_model")

        # JSON data
        with self.app.test_request_context("/", method="POST", json={"name": "json_model"}, content_type="application/json"):
            self.assertEqual(get_model_name(), "json_model")

        # Missing name
        with self.app.test_request_context("/", method="GET"):
            with patch("mlflow_oidc_auth.utils.request_helpers.request") as mock_request:
                mock_request.view_args = {}
                mock_request.args = {}
                mock_request.json = None
                with self.assertRaises(MlflowException) as cm:
                    get_model_name()
                self.assertEqual(cm.exception.error_code, "INVALID_PARAMETER_VALUE")

    @patch("mlflow_oidc_auth.utils.request_helpers._get_tracking_store")
    def test_experiment_id_from_name(self, mock_tracking_store):
        """Test experiment ID lookup by name."""
        mock_experiment = MagicMock()
        mock_experiment.experiment_id = "789"
        mock_tracking_store.return_value.get_experiment_by_name.return_value = mock_experiment
        result = _experiment_id_from_name("test_experiment")
        self.assertEqual(result, "789")
        mock_tracking_store.return_value.get_experiment_by_name.assert_called_once_with("test_experiment")

    def test_get_request_param_run_id_fallback(self):
        """Test request parameter extraction with run_id fallback."""
        with self.app.test_request_context("/?run_uuid=uuid123", method="GET"):
            self.assertEqual(get_request_param("run_id"), "uuid123")

    def test_get_request_param_post_json(self):
        """Test request parameter extraction from POST JSON data."""
        with self.app.test_request_context("/", method="POST", json={"param": "json_value"}, content_type="application/json"):
            self.assertEqual(get_request_param("param"), "json_value")

    def test_get_optional_request_param_post_json(self):
        """Test optional request parameter extraction from POST JSON data."""
        with self.app.test_request_context("/", method="POST", json={"param": "json_value"}, content_type="application/json"):
            self.assertEqual(get_optional_request_param("param"), "json_value")

    def test_get_experiment_id_view_args(self):
        """Test experiment ID extraction from view arguments."""
        with self.app.test_request_context("/experiment/123"):
            with patch("mlflow_oidc_auth.utils.request_helpers.request") as mock_request:
                mock_request.view_args = {"experiment_id": "123"}
                mock_request.args = {}
                mock_request.json = None
                self.assertEqual(get_experiment_id(), "123")

    @patch("mlflow_oidc_auth.utils.request_helpers._get_tracking_store")
    def test_get_experiment_id_view_args_name(self, mock_tracking_store):
        """Test experiment ID extraction from experiment name in view arguments."""
        mock_experiment = MagicMock()
        mock_experiment.experiment_id = "456"
        mock_tracking_store.return_value.get_experiment_by_name.return_value = mock_experiment

        with self.app.test_request_context("/experiment/test_exp"):
            with patch("mlflow_oidc_auth.utils.request_helpers.request") as mock_request:
                mock_request.view_args = {"experiment_name": "test_exp"}
                mock_request.args = {}
                mock_request.json = None
                self.assertEqual(get_experiment_id(), "456")
                mock_tracking_store.return_value.get_experiment_by_name.assert_called_with("test_exp")

    @patch("mlflow_oidc_auth.utils.request_helpers._get_tracking_store")
    def test_get_experiment_id_json_name(self, mock_tracking_store):
        """Test experiment ID extraction from experiment name in JSON data."""
        mock_experiment = MagicMock()
        mock_experiment.experiment_id = "789"
        mock_tracking_store.return_value.get_experiment_by_name.return_value = mock_experiment

        with self.app.test_request_context("/", method="POST", json={"experiment_name": "test_exp"}, content_type="application/json"):
            self.assertEqual(get_experiment_id(), "789")
            mock_tracking_store.return_value.get_experiment_by_name.assert_called_with("test_exp")

    def test_get_username_bearer_missing_email(self):
        """Test username extraction from bearer token with missing email."""
        with self.app.test_request_context("/", headers={"Authorization": "Bearer token123"}):
            with patch("mlflow_oidc_auth.utils.request_helpers.validate_token") as mock_validate_token:
                mock_validate_token.return_value = {"sub": "user123"}  # No email field

                with self.assertRaises(MlflowException) as cm:
                    get_username()
                self.assertEqual(cm.exception.error_code, "INVALID_PARAMETER_VALUE")
                self.assertIn("Email claim is missing", str(cm.exception))

    def test_get_username_unknown_auth_type(self):
        """Test username extraction with unknown authentication type."""
        with self.app.test_request_context("/", headers={"Authorization": "Unknown token123"}):
            with self.assertRaises(MlflowException) as cm:
                get_username()
            self.assertEqual(cm.exception.error_code, "INVALID_PARAMETER_VALUE")
            self.assertIn("Unsupported authorization type", str(cm.exception))

    def test_get_model_id(self):
        """Test model ID extraction from request parameters."""
        # View args
        with self.app.test_request_context("/model/123"):
            with patch("mlflow_oidc_auth.utils.request_helpers.request") as mock_request:
                mock_request.view_args = {"model_id": "123"}
                mock_request.args = {}
                mock_request.json = None
                self.assertEqual(get_model_id(), "123")

        # Query args
        with self.app.test_request_context("/?model_id=456", method="GET"):
            self.assertEqual(get_model_id(), "456")

        # JSON data
        with self.app.test_request_context("/", method="POST", json={"model_id": "789"}, content_type="application/json"):
            self.assertEqual(get_model_id(), "789")

        # Missing model_id
        with self.app.test_request_context("/", method="GET"):
            with patch("mlflow_oidc_auth.utils.request_helpers.request") as mock_request:
                mock_request.view_args = None
                mock_request.args = {}
                mock_request.json = None
                with self.assertRaises(MlflowException) as cm:
                    get_model_id()
                self.assertEqual(cm.exception.error_code, "INVALID_PARAMETER_VALUE")
                self.assertIn("Model ID must be provided", str(cm.exception))

        # Empty view_args, but model_id in args
        with self.app.test_request_context("/?model_id=args_id", method="GET"):
            with patch("mlflow_oidc_auth.utils.request_helpers.request") as mock_request:
                mock_request.view_args = {}
                mock_request.args = {"model_id": "args_id"}
                mock_request.json = None
                self.assertEqual(get_model_id(), "args_id")

        # Empty view_args and args, but model_id in json
        with self.app.test_request_context("/", method="POST", json={"model_id": "json_id"}, content_type="application/json"):
            with patch("mlflow_oidc_auth.utils.request_helpers.request") as mock_request:
                mock_request.view_args = {}
                mock_request.args = {}
                mock_request.json = {"model_id": "json_id"}
                self.assertEqual(get_model_id(), "json_id")


if __name__ == "__main__":
    unittest.main()
