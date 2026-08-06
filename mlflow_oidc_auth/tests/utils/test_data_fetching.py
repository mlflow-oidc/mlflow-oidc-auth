"""
Test cases for mlflow_oidc_auth.utils.data_fetching module.

This module contains comprehensive tests for data fetching functionality
including experiments, models, and logged models retrieval with pagination support.
"""

import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from mlflow_oidc_auth.utils import (
    fetch_all_registered_models,
    fetch_all_experiments,
    fetch_all_prompts,
    fetch_registered_models_paginated,
    fetch_experiments_paginated,
    fetch_readable_experiments,
    fetch_readable_registered_models,
    fetch_readable_logged_models,
)


class TestDataFetching(unittest.TestCase):
    """Test cases for data fetching utility functions."""

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

    @patch("mlflow_oidc_auth.utils.data_fetching._get_model_registry_store")
    def test_fetch_all_registered_models(self, mock_model_store):
        """Test fetching all registered models with pagination handling."""
        # Single page
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([MagicMock(name="model1"), MagicMock(name="model2")]))
        mock_result.__len__ = MagicMock(return_value=2)
        mock_result.token = None
        mock_model_store().search_registered_models.return_value = mock_result

        result = fetch_all_registered_models()
        self.assertEqual(len(result), 2)

        # Multiple pages
        first_page = MagicMock()
        first_page.__iter__ = MagicMock(return_value=iter([MagicMock(name="model1")]))
        first_page.__len__ = MagicMock(return_value=1)
        first_page.token = "token123"

        second_page = MagicMock()
        second_page.__iter__ = MagicMock(return_value=iter([MagicMock(name="model2")]))
        second_page.__len__ = MagicMock(return_value=1)
        second_page.token = None

        mock_model_store().search_registered_models.side_effect = [
            first_page,
            second_page,
        ]

        result = fetch_all_registered_models()
        self.assertEqual(len(result), 2)

    @patch("mlflow_oidc_auth.utils.data_fetching.fetch_all_registered_models")
    def test_fetch_all_prompts(self, mock_fetch_models):
        """Test fetching all prompts by filtering registered models."""
        mock_models = [MagicMock(name="prompt1"), MagicMock(name="prompt2")]
        mock_fetch_models.return_value = mock_models

        result = fetch_all_prompts()
        self.assertEqual(result, mock_models)
        mock_fetch_models.assert_called_once_with(
            filter_string="tags.`mlflow.prompt.is_prompt` = 'true'",
            max_results_per_page=1000,
        )

    @patch("mlflow_oidc_auth.utils.data_fetching._get_model_registry_store")
    def test_fetch_registered_models_paginated(self, mock_model_store):
        """Test fetching registered models with pagination parameters."""
        mock_result = MagicMock()
        mock_model_store().search_registered_models.return_value = mock_result

        result = fetch_registered_models_paginated(
            filter_string="test_filter",
            max_results=100,
            order_by=["name"],
            page_token="token123",
        )

        self.assertEqual(result, mock_result)
        mock_model_store().search_registered_models.assert_called_once_with(
            filter_string="test_filter",
            max_results=100,
            order_by=["name"],
            page_token="token123",
        )

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    def test_fetch_all_experiments(self, mock_tracking_store):
        """Test fetching all experiments with pagination handling."""
        # Single page
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([MagicMock(name="exp1"), MagicMock(name="exp2")]))
        mock_result.__len__ = MagicMock(return_value=2)
        mock_result.token = None
        mock_tracking_store().search_experiments.return_value = mock_result

        result = fetch_all_experiments()
        self.assertEqual(len(result), 2)

        # Multiple pages
        first_page = MagicMock()
        first_page.__iter__ = MagicMock(return_value=iter([MagicMock(name="exp1")]))
        first_page.__len__ = MagicMock(return_value=1)
        first_page.token = "token123"

        second_page = MagicMock()
        second_page.__iter__ = MagicMock(return_value=iter([MagicMock(name="exp2")]))
        second_page.__len__ = MagicMock(return_value=1)
        second_page.token = None

        mock_tracking_store().search_experiments.side_effect = [first_page, second_page]

        result = fetch_all_experiments()
        self.assertEqual(len(result), 2)

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    def test_fetch_experiments_paginated(self, mock_tracking_store):
        """Test fetching experiments with pagination parameters."""
        mock_result = MagicMock()
        mock_tracking_store().search_experiments.return_value = mock_result

        result = fetch_experiments_paginated(
            view_type=1,
            max_results=100,
            order_by=["name"],
            filter_string="test_filter",
            page_token="token123",
        )

        self.assertEqual(result, mock_result)
        mock_tracking_store().search_experiments.assert_called_once_with(
            view_type=1,
            max_results=100,
            order_by=["name"],
            filter_string="test_filter",
            page_token="token123",
        )

    @patch("mlflow_oidc_auth.utils.data_fetching.fetch_all_experiments")
    @patch("mlflow_oidc_auth.utils.data_fetching.can_read_experiment")
    def test_fetch_readable_experiments(self, mock_can_read, mock_fetch_all):
        """Test fetching experiments filtered by read permissions."""
        with self.app.test_request_context():
            mock_exp1 = MagicMock()
            mock_exp1.experiment_id = "1"
            mock_exp2 = MagicMock()
            mock_exp2.experiment_id = "2"
            mock_fetch_all.return_value = [mock_exp1, mock_exp2]

            # Mock can_read_experiment to return True only for experiment "1"
            def mock_can_read_side_effect(exp_id, user):
                return exp_id == "1"

            mock_can_read.side_effect = mock_can_read_side_effect

            result = fetch_readable_experiments("user")

            # Verify the calls were made correctly
            mock_fetch_all.assert_called_once()
            mock_can_read.assert_any_call("1", "user")
            mock_can_read.assert_any_call("2", "user")
            self.assertEqual(mock_can_read.call_count, 2)

            # Check result
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0], mock_exp1)

    @patch("mlflow_oidc_auth.utils.data_fetching.fetch_all_registered_models")
    @patch("mlflow_oidc_auth.utils.data_fetching.can_read_registered_model")
    def test_fetch_readable_registered_models(self, mock_can_read, mock_fetch_all):
        """Test fetching registered models filtered by read permissions."""
        with self.app.test_request_context():
            mock_model1 = MagicMock()
            mock_model1.name = "model1"
            mock_model2 = MagicMock()
            mock_model2.name = "model2"
            mock_fetch_all.return_value = [mock_model1, mock_model2]

            # Mock can_read_registered_model to return True only for "model1"
            def mock_can_read_side_effect(name, user):
                return name == "model1"

            mock_can_read.side_effect = mock_can_read_side_effect

            result = fetch_readable_registered_models("user")

            # Verify the calls were made correctly
            mock_fetch_all.assert_called_once()
            mock_can_read.assert_any_call("model1", "user")
            mock_can_read.assert_any_call("model2", "user")
            self.assertEqual(mock_can_read.call_count, 2)

            # Check result
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0], mock_model1)

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    @patch("mlflow_oidc_auth.utils.data_fetching.effective_experiment_permission")
    def test_fetch_readable_logged_models_default_username(self, mock_eff_perm, mock_tracking_store):
        """Readable model is kept when the effective experiment permission grants read."""
        with self.app.test_request_context():
            mock_eff_perm.return_value.permission.can_read = True

            mock_logged_model = MagicMock()
            mock_logged_model.experiment_id = "exp1"
            mock_search_result = MagicMock()
            mock_search_result.__iter__ = lambda self: iter([mock_logged_model])
            mock_search_result.token = None
            mock_tracking_store.return_value.search_logged_models.return_value = mock_search_result

            result = fetch_readable_logged_models("test_user")

            mock_eff_perm.assert_called_once_with("exp1", "test_user")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].experiment_id, "exp1")

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    @patch("mlflow_oidc_auth.utils.data_fetching.effective_experiment_permission")
    def test_fetch_readable_logged_models_with_username(self, mock_eff_perm, mock_tracking_store):
        """All readable models across pages are returned."""
        with self.app.test_request_context():
            mock_eff_perm.return_value.permission.can_read = True

            mock_logged_model1 = MagicMock()
            mock_logged_model1.experiment_id = "exp1"
            mock_logged_model2 = MagicMock()
            mock_logged_model2.experiment_id = "exp2"

            mock_search_result1 = MagicMock()
            mock_search_result1.__iter__ = lambda self: iter([mock_logged_model1])
            mock_search_result1.token = "token123"
            mock_search_result2 = MagicMock()
            mock_search_result2.__iter__ = lambda self: iter([mock_logged_model2])
            mock_search_result2.token = None
            mock_tracking_store.return_value.search_logged_models.side_effect = [
                mock_search_result1,
                mock_search_result2,
            ]

            result = fetch_readable_logged_models(
                experiment_ids=["exp1", "exp2"],
                filter_string="filter",
                order_by=[{"field_name": "name"}],
                username="custom_user",
            )

            self.assertEqual(len(result), 2)
            self.assertEqual(mock_tracking_store.return_value.search_logged_models.call_count, 2)
            mock_eff_perm.assert_any_call("exp1", "custom_user")
            mock_eff_perm.assert_any_call("exp2", "custom_user")

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    @patch("mlflow_oidc_auth.utils.data_fetching.effective_experiment_permission")
    def test_fetch_readable_logged_models_filtered_by_permissions(self, mock_eff_perm, mock_tracking_store):
        """Models are filtered out when the effective experiment permission denies read."""
        with self.app.test_request_context():
            # Readable for exp1, not for exp2 — includes the group/regex-aware resolution
            # that a user-only permission map would have missed.
            def eff(experiment_id, username):
                result = MagicMock()
                result.permission.can_read = experiment_id == "exp1"
                return result

            mock_eff_perm.side_effect = eff

            mock_logged_model1 = MagicMock()
            mock_logged_model1.experiment_id = "exp1"
            mock_logged_model2 = MagicMock()
            mock_logged_model2.experiment_id = "exp2"
            mock_search_result = MagicMock()
            mock_search_result.__iter__ = lambda self: iter([mock_logged_model1, mock_logged_model2])
            mock_search_result.token = None
            mock_tracking_store.return_value.search_logged_models.return_value = mock_search_result

            result = fetch_readable_logged_models(username="test_user")

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].experiment_id, "exp1")

    @patch("mlflow_oidc_auth.utils.data_fetching._get_tracking_store")
    @patch("mlflow_oidc_auth.utils.data_fetching.effective_experiment_permission")
    def test_fetch_readable_logged_models_empty_result(self, mock_eff_perm, mock_tracking_store):
        """Empty search result yields no models and no permission checks."""
        with self.app.test_request_context():
            mock_search_result = MagicMock()
            mock_search_result.__iter__ = lambda self: iter([])
            mock_search_result.token = None
            mock_tracking_store.return_value.search_logged_models.return_value = mock_search_result

            result = fetch_readable_logged_models(username="test_user")

            self.assertEqual(len(result), 0)
            mock_eff_perm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
