"""
Tests for the trash router.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from mlflow.entities import ViewType

from mlflow_oidc_auth.routers.trash import list_deleted_experiments, list_deleted_runs, restore_experiment, restore_run


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
        mock_fetch_all_experiments.assert_called_once_with(view_type=ViewType.DELETED_ONLY)

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
        mock_fetch_all_experiments.assert_called_once_with(view_type=ViewType.DELETED_ONLY)

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

        # Call the function and verify it raises HTTPException
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            await list_deleted_experiments(admin_username="admin@example.com")

        assert excinfo.value.status_code == 500
        assert excinfo.value.detail == "Failed to retrieve deleted experiments"

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


class TestListDeletedRunsEndpoint:
    """Tests for listing deleted runs."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_list_deleted_runs_success(self, mock_get_store):
        backend_store = MagicMock()
        backend_store._get_deleted_runs.return_value = ["run-1", "run-2"]

        run_deleted = MagicMock()
        run_deleted.info.run_id = "run-1"
        run_deleted.info.experiment_id = "exp-1"
        run_deleted.info.run_name = "name-1"
        run_deleted.info.status = "FINISHED"
        run_deleted.info.start_time = 1
        run_deleted.info.end_time = 2
        run_deleted.info.lifecycle_stage = "deleted"

        run_active = MagicMock()
        run_active.info.run_id = "run-2"
        run_active.info.experiment_id = "exp-2"
        run_active.info.run_name = "name-2"
        run_active.info.status = "FINISHED"
        run_active.info.start_time = 3
        run_active.info.end_time = 4
        run_active.info.lifecycle_stage = "active"

        backend_store.get_run.side_effect = [run_deleted, run_active]
        mock_get_store.return_value = backend_store

        result = await list_deleted_runs(admin_username="admin@example.com", experiment_ids=None, older_than=None)

        backend_store._get_deleted_runs.assert_called_once()
        assert result.status_code == 200
        import json

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == [
            {
                "run_id": "run-1",
                "experiment_id": "exp-1",
                "run_name": "name-1",
                "status": "FINISHED",
                "start_time": 1,
                "end_time": 2,
                "lifecycle_stage": "deleted",
            }
        ]

    @pytest.mark.asyncio
    async def test_list_deleted_runs_invalid_older_than(self):
        result = await list_deleted_runs(admin_username="admin@example.com", experiment_ids=None, older_than="bad")
        assert result.status_code == 400

    def test_list_deleted_runs_integration_admin(self, admin_client: TestClient):
        with patch("mlflow_oidc_auth.routers.trash._get_store") as mock_get_store:
            backend_store = MagicMock()
            backend_store._get_deleted_runs.return_value = ["run-1"]

            run_deleted = MagicMock()
            run_deleted.info.run_id = "run-1"
            run_deleted.info.experiment_id = "exp-1"
            run_deleted.info.run_name = "deleted-run"
            run_deleted.info.status = "FINISHED"
            run_deleted.info.start_time = 10
            run_deleted.info.end_time = 20
            run_deleted.info.lifecycle_stage = "deleted"

            backend_store.get_run.return_value = run_deleted
            mock_get_store.return_value = backend_store

            response = admin_client.get("/oidc/trash/runs")
            assert response.status_code == 200
            assert response.json()["deleted_runs"][0]["run_id"] == "run-1"

    def test_list_deleted_runs_integration_non_admin(self, client: TestClient):
        response = client.get("/oidc/trash/runs")
        assert response.status_code == 403


class TestRestoreExperimentEndpoint:
    """Tests for restoring experiments."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_restore_experiment_success(self, mock_get_store):
        backend_store = MagicMock()
        deleted = MagicMock()
        deleted.lifecycle_stage = "deleted"
        deleted.experiment_id = "123"
        deleted.name = "exp"
        deleted.last_update_time = 1

        restored = MagicMock()
        restored.lifecycle_stage = "active"
        restored.experiment_id = "123"
        restored.name = "exp"
        restored.last_update_time = 2

        backend_store.get_experiment.side_effect = [deleted, restored]
        mock_get_store.return_value = backend_store

        result = await restore_experiment(experiment_id="123", admin_username="admin@example.com")
        backend_store.restore_experiment.assert_called_once_with("123")
        assert result.status_code == 200

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_restore_experiment_not_deleted(self, mock_get_store):
        backend_store = MagicMock()
        active = MagicMock()
        active.lifecycle_stage = "active"
        backend_store.get_experiment.return_value = active
        mock_get_store.return_value = backend_store

        result = await restore_experiment(experiment_id="123", admin_username="admin@example.com")
        assert result.status_code == 400

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_restore_experiment_not_found(self, mock_get_store):
        backend_store = MagicMock()
        backend_store.get_experiment.side_effect = Exception("not found")
        mock_get_store.return_value = backend_store

        result = await restore_experiment(experiment_id="missing", admin_username="admin@example.com")
        assert result.status_code == 404


class TestRestoreRunEndpoint:
    """Tests for restoring runs."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_restore_run_success(self, mock_get_store):
        backend_store = MagicMock()
        deleted = MagicMock()
        deleted.info.lifecycle_stage = "deleted"
        deleted.info.run_id = "run-1"
        deleted.info.experiment_id = "exp-1"
        deleted.info.run_name = "r"
        deleted.info.status = "FINISHED"

        restored = MagicMock()
        restored.info.lifecycle_stage = "active"
        restored.info.run_id = "run-1"
        restored.info.experiment_id = "exp-1"
        restored.info.run_name = "r"
        restored.info.status = "FINISHED"

        backend_store.get_run.side_effect = [deleted, restored]
        mock_get_store.return_value = backend_store

        result = await restore_run(run_id="run-1", admin_username="admin@example.com")
        backend_store.restore_run.assert_called_once_with("run-1")
        assert result.status_code == 200

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_restore_run_not_deleted(self, mock_get_store):
        backend_store = MagicMock()
        active = MagicMock()
        active.info.lifecycle_stage = "active"
        backend_store.get_run.return_value = active
        mock_get_store.return_value = backend_store

        result = await restore_run(run_id="run-1", admin_username="admin@example.com")
        assert result.status_code == 400

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_restore_run_not_found(self, mock_get_store):
        backend_store = MagicMock()
        backend_store.get_run.side_effect = Exception("missing")
        mock_get_store.return_value = backend_store

        result = await restore_run(run_id="missing", admin_username="admin@example.com")
        assert result.status_code == 404
