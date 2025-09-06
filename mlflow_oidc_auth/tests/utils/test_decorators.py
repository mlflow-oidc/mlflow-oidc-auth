"""
Test cases for mlflow_oidc_auth.utils.decorators module.

This module contains comprehensive tests for permission decorators
that control access to MLflow operations.
"""

import unittest
from unittest.mock import patch

from flask import Flask

from mlflow_oidc_auth.dependencies import (
    check_experiment_permission,
    check_registered_model_permission,
    check_admin_permission,
)


class TestDecorators(unittest.TestCase):
    """Test cases for decorator utility functions."""

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

    @patch("mlflow_oidc_auth.utils.decorators.store")
    @patch("mlflow_oidc_auth.utils.decorators.get_is_admin")
    @patch("mlflow_oidc_auth.utils.decorators.get_username")
    @patch("mlflow_oidc_auth.utils.decorators.get_experiment_id")
    @patch("mlflow_oidc_auth.utils.decorators.can_manage_experiment")
    @patch("mlflow_oidc_auth.utils.decorators.make_forbidden_response")
    def test_check_experiment_permission(
        self,
        mock_make_forbidden_response,
        mock_can_manage_experiment,
        mock_get_experiment_id,
        mock_get_username,
        mock_get_is_admin,
        mock_store,
    ):
        """Test experiment permission decorator functionality."""
        with self.app.test_request_context():
            mock_get_is_admin.return_value = False
            mock_get_username.return_value = "user"
            mock_get_experiment_id.return_value = "exp_id"
            mock_can_manage_experiment.return_value = False
            mock_make_forbidden_response.return_value = "forbidden"

            @check_experiment_permission
            def mock_func():
                return "success"

            self.assertEqual(mock_func(), "forbidden")

            mock_can_manage_experiment.return_value = True
            self.assertEqual(mock_func(), "success")

            # Admin always allowed
            mock_get_is_admin.return_value = True
            self.assertEqual(mock_func(), "success")

    @patch("mlflow_oidc_auth.utils.decorators.store")
    @patch("mlflow_oidc_auth.utils.decorators.get_is_admin")
    @patch("mlflow_oidc_auth.utils.decorators.get_username")
    @patch("mlflow_oidc_auth.utils.decorators.get_model_name")
    @patch("mlflow_oidc_auth.utils.decorators.can_manage_registered_model")
    @patch("mlflow_oidc_auth.utils.decorators.make_forbidden_response")
    def test_check_registered_model_permission(
        self,
        mock_make_forbidden_response,
        mock_can_manage_registered_model,
        mock_get_model_name,
        mock_get_username,
        mock_get_is_admin,
        mock_store,
    ):
        """Test registered model permission decorator functionality."""
        with self.app.test_request_context():
            mock_get_is_admin.return_value = False
            mock_get_username.return_value = "user"
            mock_get_model_name.return_value = "model_name"
            mock_can_manage_registered_model.return_value = False
            mock_make_forbidden_response.return_value = "forbidden"

            @check_registered_model_permission
            def mock_func():
                return "success"

            self.assertEqual(mock_func(), "forbidden")

            mock_can_manage_registered_model.return_value = True
            self.assertEqual(mock_func(), "success")

            # Admin always allowed
            mock_get_is_admin.return_value = True
            self.assertEqual(mock_func(), "success")


if __name__ == "__main__":
    unittest.main()
