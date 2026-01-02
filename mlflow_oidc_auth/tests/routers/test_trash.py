"""
Tests for the trash router.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from mlflow_oidc_auth.routers.trash import trash_router, list_deleted_experiments


class TestListDeletedExperimentsEndpoint:
    """Test the list deleted experiments endpoint functionality."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.fetch_all_experiments")
    async def test_list_deleted_experiments_success(self, mock_fetch_all_experiments):
        """Test successfully listing deleted experiments as admin."""
        # Mock deleted experiments
        mock_deleted_experiment = MagicMock()
        mock_deleted_experiment.experiment_id = "123"
        mock_deleted_experiment.name = "Deleted Experiment"
        mock_deleted_experiment.lifecycle_stage = "deleted"
        mock_deleted_experiment.artifact_location = "/tmp/artifacts/123"
        mock_deleted_experiment.tags = {"tag1": "value1"}
        mock_deleted_experiment.creation_time = 1000000
        mock_deleted_experiment.last_update_time = 2000000

        mock_fetch_all_experiments.return_value = [mock_deleted_experiment]

        # Call the function
        result = await list_deleted_experiments(admin_username="admin@example.com")

        # Verify call
        mock_fetch_all_experiments.assert_called_once_with(view_type=2)

        # Verify response
        assert result.status_code == 200
        # Access the JSON content from the JSONResponse
        import json

        response_data = json.loads(result.body)
        assert "deleted_experiments" in response_data
        assert len(response_data["deleted_experiments"]) == 1
        assert response_data["deleted_experiments"][0]["experiment_id"] == "123"
        assert response_data["deleted_experiments"][0]["name"] == "Deleted Experiment"

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.fetch_all_experiments")
    async def test_list_deleted_experiments_empty(self, mock_fetch_all_experiments):
        """Test listing deleted experiments when none exist."""
        mock_fetch_all_experiments.return_value = []

        # Call the function
        result = await list_deleted_experiments(admin_username="admin@example.com")

        # Verify call
        mock_fetch_all_experiments.assert_called_once_with(view_type=2)

        # Verify response
        assert result.status_code == 200
        import json

        response_data = json.loads(result.body)
        assert "deleted_experiments" in response_data
        assert len(response_data["deleted_experiments"]) == 0

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.fetch_all_experiments")
    async def test_list_deleted_experiments_error(self, mock_fetch_all_experiments):
        """Test error handling when fetching deleted experiments fails."""
        mock_fetch_all_experiments.side_effect = Exception("MLflow error")

        # Call the function
        result = await list_deleted_experiments(admin_username="admin@example.com")

        # Verify response
        assert result.status_code == 500
        import json

        response_data = json.loads(result.body)
        assert "error" in response_data

    def test_list_deleted_experiments_integration_admin(self, admin_client: TestClient):
        """Test the endpoint through FastAPI test client as admin."""
        # Mock the fetch function
        with patch("mlflow_oidc_auth.routers.trash.fetch_all_experiments") as mock_fetch:
            mock_experiment = MagicMock()
            mock_experiment.experiment_id = "123"
            mock_experiment.name = "Deleted Experiment"
            mock_experiment.lifecycle_stage = "deleted"
            mock_experiment.artifact_location = "/tmp/artifacts/123"
            mock_experiment.tags = {"tag1": "value1"}
            mock_experiment.creation_time = 1000000
            mock_experiment.last_update_time = 2000000
            mock_fetch.return_value = [mock_experiment]

            response = admin_client.get("/oidc/trash/experiments")

            assert response.status_code == 200
            data = response.json()
            assert "deleted_experiments" in data
            assert len(data["deleted_experiments"]) == 1
            assert data["deleted_experiments"][0]["experiment_id"] == "123"
            assert data["deleted_experiments"][0]["name"] == "Deleted Experiment"
            assert data["deleted_experiments"][0]["lifecycle_stage"] == "deleted"

    def test_list_deleted_experiments_integration_non_admin(self, client: TestClient):
        """Test the endpoint through FastAPI test client as non-admin (should be forbidden)."""
        response = client.get("/oidc/trash/experiments")

        # Should be forbidden for non-admin users
        assert response.status_code == 403
