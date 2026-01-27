"""
Tests for the trash router.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from mlflow.entities import ViewType

from mlflow_oidc_auth.routers.trash import list_deleted_experiments, list_deleted_runs, permanently_delete_all_trashed_entities, restore_experiment, restore_run


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


class TestAdditionalTrashBehaviour:
    """Extra tests to improve coverage for edge cases and cleanup logic."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.fetch_all_experiments")
    async def test_list_deleted_experiments_handles_none_tags(self, mock_fetch_all_experiments):
        mock_deleted_experiment = MagicMock()
        mock_deleted_experiment.experiment_id = "321"
        mock_deleted_experiment.name = "Deleted No Tags"
        mock_deleted_experiment.lifecycle_stage = "deleted"
        mock_deleted_experiment.artifact_location = "/tmp/artifacts/321"
        mock_deleted_experiment.tags = None
        mock_deleted_experiment.creation_time = 10
        mock_deleted_experiment.last_update_time = 20

        mock_fetch_all_experiments.return_value = [mock_deleted_experiment]

        result = await list_deleted_experiments(admin_username="admin@example.com")
        assert result.status_code == 200
        import json

        payload = json.loads(result.body)
        assert payload["deleted_experiments"][0]["tags"] == {}

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.fetch_all_experiments")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_list_deleted_runs_fallback_and_empty(self, mock_get_store, mock_fetch_all_experiments):
        # Backend lacks _get_deleted_runs and search_runs raises -> fallback yields empty runs
        backend_store = MagicMock()
        if hasattr(backend_store, "_get_deleted_runs"):
            delattr(backend_store, "_get_deleted_runs")
        backend_store.search_runs.side_effect = Exception("search failed")
        mock_get_store.return_value = backend_store

        # Make fetch_all_experiments return one experiment id
        exp = MagicMock()
        exp.experiment_id = "exp-1"
        mock_fetch_all_experiments.return_value = [exp]

        result = await list_deleted_runs(admin_username="admin@example.com", experiment_ids=None, older_than=None)
        assert result.status_code == 200
        import json

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == []

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_list_deleted_runs_skips_unfetchable_run(self, mock_get_store):
        backend_store = MagicMock()
        backend_store._get_deleted_runs.return_value = ["r-1"]
        backend_store.get_run.side_effect = Exception("unfetchable")
        mock_get_store.return_value = backend_store

        result = await list_deleted_runs(admin_username="admin@example.com", experiment_ids=None, older_than=None)
        assert result.status_code == 200
        import json

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == []

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_backend_without_hard_delete_run(self, mock_get_store):
        backend_store = MagicMock()
        # Remove _hard_delete_run capability
        if hasattr(backend_store, "_hard_delete_run"):
            delattr(backend_store, "_hard_delete_run")
        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(admin_username="admin@example.com", older_than=None)
        assert result.status_code == 400
        import json

        payload = json.loads(result.body)
        assert "Backend store does not support permanent deletion of runs" in payload["error"]

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_experiment_not_found_returns_404(self, mock_get_store):
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        backend_store._hard_delete_experiment = MagicMock()
        backend_store.get_experiment.side_effect = Exception("missing")
        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(admin_username="admin@example.com", run_ids=None, experiment_ids="nope", older_than=None)
        assert result.status_code == 404
        import json

        payload = json.loads(result.body)
        assert "Experiment nope not found" in payload["error"]

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_experiment_active_returns_400(self, mock_get_store):
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        backend_store._hard_delete_experiment = MagicMock()

        active = MagicMock()
        active.lifecycle_stage = "active"
        active.experiment_id = "a1"
        backend_store.get_experiment.return_value = active
        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(admin_username="admin@example.com", run_ids=None, experiment_ids="a1", older_than=None)
        assert result.status_code == 400
        import json

        payload = json.loads(result.body)
        assert "are not in deleted lifecycle stage" in payload["error"]

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_delete_runs_and_experiments_happy_path(self, mock_get_store, mock_get_artifact_repo):
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        backend_store._hard_delete_experiment = MagicMock()

        # Setup run to be deleted
        run = MagicMock()
        run.info.run_id = "run-1"
        run.info.lifecycle_stage = "deleted"
        run.info.artifact_uri = "invalid://"
        run.info.experiment_id = "exp-1"
        backend_store.get_run.return_value = run

        # _get_deleted_runs returns our run id
        backend_store._get_deleted_runs.return_value = ["run-1"]

        # Experiment to delete
        exp = MagicMock()
        exp.experiment_id = "exp-1"
        exp.lifecycle_stage = "deleted"
        exp.last_update_time = 0

        backend_store.get_experiment.return_value = exp

        # Make artifact repo deletion raise InvalidUrlException to exercise that branch
        from mlflow.exceptions import InvalidUrlException

        mock_repo = MagicMock()
        mock_repo.delete_artifacts.side_effect = InvalidUrlException("bad url")
        mock_get_artifact_repo.return_value = mock_repo

        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(admin_username="admin@example.com", run_ids="run-1", experiment_ids="exp-1", older_than=None)
        assert result.status_code == 200
        import json

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == ["run-1"]
        assert payload["deleted_experiments"] == ["exp-1"]

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_run_not_deleted_and_hard_delete_experiment_failure(self, mock_get_store):
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()

        # Run exists but is active
        run = MagicMock()
        run.info.run_id = "run-2"
        run.info.lifecycle_stage = "active"
        backend_store.get_run.return_value = run

        # Experiment deletion will raise
        exp = MagicMock()
        exp.experiment_id = "e2"
        exp.lifecycle_stage = "deleted"
        backend_store.get_experiment.return_value = exp
        backend_store._hard_delete_experiment.side_effect = Exception("boom")

        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(admin_username="admin@example.com", run_ids="run-2", experiment_ids="e2", older_than=None)
        assert result.status_code == 200
        import json

        payload = json.loads(result.body)
        # run should not be deleted and should appear in failed_runs
        assert any(f["run_id"] == "run-2" for f in payload.get("failed_runs", []))
        # experiment deletion should have failed
        assert any(f["experiment_id"] == "e2" for f in payload.get("failed_experiments", []))

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_list_deleted_runs_filters_by_experiment(self, mock_get_store):
        backend_store = MagicMock()
        backend_store._get_deleted_runs.return_value = ["r1", "r2"]

        run1 = MagicMock()
        run1.info.run_id = "r1"
        run1.info.experiment_id = "exp-1"
        run1.info.lifecycle_stage = "deleted"
        run1.info.run_name = "n1"
        run1.info.status = "FINISHED"
        run1.info.start_time = 1
        run1.info.end_time = 2

        run2 = MagicMock()
        run2.info.run_id = "r2"
        run2.info.experiment_id = "exp-2"
        run2.info.lifecycle_stage = "deleted"
        run2.info.run_name = "n2"
        run2.info.status = "FINISHED"
        run2.info.start_time = 3
        run2.info.end_time = 4

        backend_store.get_run.side_effect = [run1, run2]
        mock_get_store.return_value = backend_store

        result = await list_deleted_runs(admin_username="admin@example.com", experiment_ids="exp-1", older_than=None)
        assert result.status_code == 200
        import json

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == [
            {"run_id": "r1", "experiment_id": "exp-1", "run_name": "n1", "status": "FINISHED", "start_time": 1, "end_time": 2, "lifecycle_stage": "deleted"}
        ]

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_list_deleted_runs_backend_raises_returns_500(self, mock_get_store):
        backend_store = MagicMock()
        backend_store._get_deleted_runs.side_effect = Exception("boom")
        mock_get_store.return_value = backend_store

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            await list_deleted_runs(admin_username="admin@example.com", experiment_ids=None, older_than=None)

        assert excinfo.value.status_code == 500
        assert excinfo.value.detail == "Failed to retrieve deleted runs"

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_fetch_experiments_and_runs(self, mock_get_store, mock_get_artifact_repo):
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        backend_store._hard_delete_experiment = MagicMock()

        # Implement a simple Page class used by backend search methods
        class Page(list):
            def __init__(self, items, token=None):
                super().__init__(items)
                self.token = token

            def __add__(self, other):
                return Page(list(self) + list(other), token=None)

        # Experiment returned by search_experiments
        exp = MagicMock()
        exp.experiment_id = "e1"
        exp.lifecycle_stage = "deleted"
        exp.last_update_time = 0

        # Run returned by search_runs
        run = MagicMock()
        run.info.run_id = "r1"
        run.info.lifecycle_stage = "deleted"
        run.info.artifact_uri = "invalid://"
        run.info.experiment_id = "e1"
        run.info.run_name = "rname"
        run.info.status = "FINISHED"
        run.info.start_time = 1
        run.info.end_time = 2

        backend_store.search_experiments.return_value = Page([exp], token=None)
        backend_store.search_runs.return_value = Page([run], token=None)
        backend_store._get_deleted_runs.return_value = ["r1"]
        backend_store.get_run.return_value = run

        # artifact repo raising InvalidUrl triggers warning branch but doesn't fail
        from mlflow.exceptions import InvalidUrlException

        mock_repo = MagicMock()
        mock_repo.delete_artifacts.side_effect = InvalidUrlException("bad url")
        mock_get_artifact_repo.return_value = mock_repo

        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(admin_username="admin@example.com", older_than=None, run_ids=None, experiment_ids=None)
        assert result.status_code == 200
        import json

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == ["r1"]
        assert payload["deleted_experiments"] == ["e1"]

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_list_deleted_runs_paged_search_runs(self, mock_get_store):
        backend_store = MagicMock()

        # Implement a Page that supports token and addition
        class Page(list):
            def __init__(self, items, token=None):
                super().__init__(items)
                self.token = token

            def __add__(self, other):
                return Page(list(self) + list(other), token=None)

        # two runs across pages
        run1 = MagicMock()
        run1.info.run_id = "r1"
        run1.info.experiment_id = "exp-1"
        run1.info.lifecycle_stage = "deleted"
        run1.info.run_name = "n1"
        run1.info.status = "FINISHED"
        run1.info.start_time = 1
        run1.info.end_time = 2

        run2 = MagicMock()
        run2.info.run_id = "r2"
        run2.info.experiment_id = "exp-2"
        run2.info.lifecycle_stage = "deleted"
        run2.info.run_name = "n2"
        run2.info.status = "FINISHED"
        run2.info.start_time = 3
        run2.info.end_time = 4

        def search_runs(experiment_ids, filter_string, run_view_type, page_token=None):
            if page_token is None:
                return Page([run1], token="t")
            else:
                return Page([run2], token=None)

        backend_store.search_runs.side_effect = search_runs
        # Ensure backend_store has no _get_deleted_runs attribute so fallback path is used
        if hasattr(backend_store, "_get_deleted_runs"):
            delattr(backend_store, "_get_deleted_runs")
        # fetch_all_experiments used when experiment_ids not provided
        with patch("mlflow_oidc_auth.routers.trash.fetch_all_experiments") as mock_fetch_all_experiments:
            exp = MagicMock()
            exp.experiment_id = "exp-1"
            mock_fetch_all_experiments.return_value = [exp]

            backend_store.get_run.side_effect = [run1, run2]
            mock_get_store.return_value = backend_store

            result = await list_deleted_runs(admin_username="admin@example.com", experiment_ids=None, older_than=None)
            assert result.status_code == 200
            import json

            payload = json.loads(result.body)
            assert len(payload["deleted_runs"]) == 2

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_run_not_old_returns_failed_run(self, mock_get_store):
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        # no deleted runs older than
        backend_store._get_deleted_runs.return_value = []

        # run exists and is deleted
        run = MagicMock()
        run.info.run_id = "r1"
        run.info.lifecycle_stage = "deleted"
        run.info.artifact_uri = "invalid://"
        run.info.experiment_id = "e1"
        run.info.run_name = "r"
        run.info.status = "FINISHED"
        run.info.start_time = 1
        run.info.end_time = 2

        backend_store.get_run.return_value = run
        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(admin_username="admin@example.com", older_than="1d", run_ids="r1", experiment_ids=None)
        assert result.status_code == 200
        import json

        payload = json.loads(result.body)
        assert any(f["run_id"] == "r1" for f in payload.get("failed_runs", []))

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_experiment_age_check_non_old(self, mock_get_store):
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        backend_store._hard_delete_experiment = MagicMock()

        # experiment provided and last_update_time recent
        active_exp = MagicMock()
        active_exp.experiment_id = "eX"
        active_exp.lifecycle_stage = "deleted"
        # set last_update_time to current to be "non old"
        from mlflow.utils.time import get_current_time_millis

        active_exp.last_update_time = get_current_time_millis()

        backend_store.get_experiment.return_value = active_exp
        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(admin_username="admin@example.com", older_than="1d", run_ids=None, experiment_ids="eX")
        assert result.status_code == 400
        import json

        payload = json.loads(result.body)
        assert "not older than" in payload["error"]

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_fetch_experiments_pages_and_runs(self, mock_get_store, mock_get_artifact_repo):
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        backend_store._hard_delete_experiment = MagicMock()

        class Page(list):
            def __init__(self, items, token=None):
                super().__init__(items)
                self.token = token

            def __add__(self, other):
                return Page(list(self) + list(other), token=None)

        exp1 = MagicMock()
        exp1.experiment_id = "e1"
        exp2 = MagicMock()
        exp2.experiment_id = "e2"

        run1 = MagicMock()
        run1.info.run_id = "r1"
        run1.info.lifecycle_stage = "deleted"
        run1.info.artifact_uri = "invalid://"
        run1.info.experiment_id = "e1"
        run1.info.run_name = "r"
        run1.info.status = "FINISHED"
        run1.info.start_time = 1
        run1.info.end_time = 2
        run2 = MagicMock()
        run2.info.run_id = "r2"
        run2.info.lifecycle_stage = "deleted"
        run2.info.artifact_uri = "invalid://"
        run2.info.experiment_id = "e2"
        run2.info.run_name = "r"
        run2.info.status = "FINISHED"
        run2.info.start_time = 1
        run2.info.end_time = 2

        # make search_experiments return two pages
        def search_experiments(view_type, filter_string, page_token=None):
            if page_token is None:
                return Page([exp1], token="t")
            return Page([exp2], token=None)

        # make search_runs return page per experiments group
        def search_runs(experiment_ids, filter_string, run_view_type, page_token=None):
            if experiment_ids == ["e1"]:
                return Page([run1], token=None)
            if experiment_ids == ["e2"]:
                return Page([run2], token=None)
            return Page([], token=None)

        backend_store.search_experiments.side_effect = search_experiments
        backend_store.search_runs.side_effect = search_runs
        backend_store._get_deleted_runs.return_value = []
        backend_store.get_run.side_effect = [run1, run2]

        from mlflow.exceptions import InvalidUrlException

        mock_repo = MagicMock()
        mock_repo.delete_artifacts.side_effect = InvalidUrlException("bad url")
        mock_get_artifact_repo.return_value = mock_repo

        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(admin_username="admin@example.com", older_than=None, run_ids=None, experiment_ids=None)
        assert result.status_code == 200
        import json

        payload = json.loads(result.body)
        assert set(payload["deleted_experiments"]) == {"e1", "e2"}

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_deleted_runs_fetch_failure_is_handled(self, mock_get_store):
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        # _get_deleted_runs raises
        backend_store._get_deleted_runs.side_effect = Exception("boom-fetch")
        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(admin_username="admin@example.com", older_than=None, run_ids=None, experiment_ids=None)
        assert result.status_code == 200
        import json

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == []
        assert payload["deleted_experiments"] == []

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_older_than_invalid_returns_400(self, mock_get_store):
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(admin_username="admin@example.com", older_than="bad", run_ids=None, experiment_ids=None)
        assert result.status_code == 400

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_list_deleted_runs_json_serialization_error_raises_http_exception(self, mock_get_store):
        backend_store = MagicMock()
        backend_store._get_deleted_runs.return_value = ["r1"]

        run = MagicMock()
        run.info.run_id = "r1"
        run.info.experiment_id = "exp-1"
        run.info.lifecycle_stage = "deleted"
        # Non-serializable field
        run.info.run_name = MagicMock()
        run.info.status = MagicMock()
        run.info.start_time = MagicMock()
        run.info.end_time = MagicMock()

        backend_store.get_run.return_value = run
        mock_get_store.return_value = backend_store

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            await list_deleted_runs(admin_username="admin@example.com", experiment_ids=None, older_than=None)

        assert excinfo.value.status_code == 500
        assert excinfo.value.detail == "Failed to retrieve deleted runs"

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_artifact_delete_exception_is_handled(self, mock_get_store, mock_get_artifact_repo):
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        backend_store._hard_delete_experiment = MagicMock()
        backend_store._get_deleted_runs.return_value = ["r1"]

        run = MagicMock()
        run.info.run_id = "r1"
        run.info.lifecycle_stage = "deleted"
        run.info.artifact_uri = "some://"
        run.info.experiment_id = "e1"

        backend_store.get_run.return_value = run
        mock_get_store.return_value = backend_store

        mock_repo = MagicMock()
        mock_repo.delete_artifacts.side_effect = Exception("boom-artifact")
        mock_get_artifact_repo.return_value = mock_repo

        result = await permanently_delete_all_trashed_entities(admin_username="admin@example.com", run_ids="r1", experiment_ids=None, older_than=None)
        assert result.status_code == 200
        import json

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == ["r1"]

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_hard_delete_run_failure_records_failed_run(self, mock_get_store, mock_get_artifact_repo):
        backend_store = MagicMock()
        # hard delete run will fail
        backend_store._hard_delete_run.side_effect = Exception("boom-delete")
        backend_store._get_deleted_runs.return_value = ["r1"]

        run = MagicMock()
        run.info.run_id = "r1"
        run.info.lifecycle_stage = "deleted"
        run.info.artifact_uri = "some://"
        run.info.experiment_id = "e1"

        backend_store.get_run.return_value = run
        mock_get_store.return_value = backend_store

        mock_repo = MagicMock()
        mock_repo.delete_artifacts.return_value = None
        mock_get_artifact_repo.return_value = mock_repo

        result = await permanently_delete_all_trashed_entities(admin_username="admin@example.com", run_ids="r1", experiment_ids=None, older_than=None)
        assert result.status_code == 200
        import json

        payload = json.loads(result.body)
        assert any(f["run_id"] == "r1" and "boom-delete" in f["error"] for f in payload.get("failed_runs", []))

    def test_parse_time_delta_more_cases(self):
        from mlflow.exceptions import MlflowException

        from mlflow_oidc_auth.routers.trash import _parse_time_delta

        assert _parse_time_delta("1.5h") == int(1.5 * 3600 * 1000)
        assert _parse_time_delta("2d8h5m20s") == int((2 * 24 * 3600 + 8 * 3600 + 5 * 60 + 20) * 1000)

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_skips_experiments_when_not_supported(self, mock_get_store):
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        # remove _hard_delete_experiment if present
        if hasattr(backend_store, "_hard_delete_experiment"):
            delattr(backend_store, "_hard_delete_experiment")
        # No runs or experiments to delete
        backend_store._get_deleted_runs.return_value = []
        mock_get_store.return_value = backend_store

        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = await permanently_delete_all_trashed_entities(admin_username="admin@example.com", older_than=None, run_ids=None, experiment_ids=None)
            assert result.status_code == 200
            import json

            payload = json.loads(result.body)
            assert payload["deleted_runs"] == []
            assert payload["deleted_experiments"] == []
            # Ensure we warned about experiments not supported
            assert any("does not allow hard-deleting experiments" in str(x.message) for x in w)

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_top_level_exception_raises_http_exception(self, mock_get_store):
        mock_get_store.side_effect = Exception("boom")
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            await permanently_delete_all_trashed_entities(admin_username="admin@example.com", older_than=None, run_ids=None, experiment_ids=None)

        assert excinfo.value.status_code == 500
        assert excinfo.value.detail == "Cleanup operation failed"

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_restore_experiment_fails_raises_500(self, mock_get_store):
        backend_store = MagicMock()
        deleted = MagicMock()
        deleted.lifecycle_stage = "deleted"
        deleted.experiment_id = "999"
        deleted.name = "exp"
        deleted.last_update_time = 1

        backend_store.get_experiment.return_value = deleted
        backend_store.restore_experiment.side_effect = Exception("boom")
        mock_get_store.return_value = backend_store

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            await restore_experiment(experiment_id="999", admin_username="admin@example.com")

        assert excinfo.value.status_code == 500
        assert excinfo.value.detail == "Failed to restore experiment"

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_restore_run_fails_raises_500(self, mock_get_store):
        backend_store = MagicMock()
        deleted = MagicMock()
        deleted.info.lifecycle_stage = "deleted"
        deleted.info.run_id = "run-9"
        deleted.info.experiment_id = "exp-9"
        deleted.info.run_name = "r"
        deleted.info.status = "FINISHED"

        backend_store.get_run.return_value = deleted
        backend_store.restore_run.side_effect = Exception("boom")
        mock_get_store.return_value = backend_store

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            await restore_run(run_id="run-9", admin_username="admin@example.com")

        assert excinfo.value.status_code == 500
        assert excinfo.value.detail == "Failed to restore run"

    def test_parse_time_delta_valid_and_invalid(self):
        from mlflow.exceptions import MlflowException

        from mlflow_oidc_auth.routers.trash import _parse_time_delta, _split_csv

        # valid
        assert _parse_time_delta("1s") == 1000
        # invalid
        with pytest.raises(MlflowException):
            _parse_time_delta("bad")

        # _split_csv
        assert _split_csv(None) == []
        assert _split_csv("a, b, ,c") == ["a", "b", "c"]
