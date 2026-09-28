"""
Tests for the trash router.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from mlflow.entities import ViewType

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.routers.trash import (
    _parse_time_delta,
    list_deleted_experiments,
    list_deleted_runs,
    permanently_delete_all_trashed_entities,
    restore_experiment,
    restore_run,
)


class TestParseTimeDelta:
    """Regression coverage for _parse_time_delta (#154).

    #154 reported "Unsupported type for timedelta seconds component". The regex named
    groups (days/hours/minutes/seconds) map directly to timedelta kwargs and values are
    cast to float, so every component — the seconds one in particular — parses correctly.
    These tests lock that so the seconds component can't regress silently.
    """

    @pytest.mark.parametrize(
        "text,expected_ms",
        [
            ("20s", 20_000),  # the seconds component alone — the exact #154 case
            ("2m4s", 124_000),
            ("8h", 28_800_000),
            ("1d", 86_400_000),
            ("2d8h5m20s", 201_920_000),  # all four components together
            ("0.5h", 1_800_000),  # fractional value
            ("1.5s", 1_500),  # fractional seconds
        ],
    )
    def test_valid_formats_parse_to_milliseconds(self, text, expected_ms):
        assert _parse_time_delta(text) == expected_ms

    def test_seconds_component_is_supported(self):
        """The literal #154 bug: a string whose only component is seconds must not raise."""
        assert _parse_time_delta("45s") == 45_000

    @pytest.mark.parametrize("bad", ["bad", "10x", "1h2z", "d"])
    def test_invalid_formats_raise_mlflow_exception(self, bad):
        with pytest.raises(MlflowException):
            _parse_time_delta(bad)


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

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            run_ids=None,
            experiment_ids="nope",
            older_than=None,
        )
        assert result.status_code == 404

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

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            run_ids=None,
            experiment_ids="a1",
            older_than=None,
        )
        assert result.status_code == 400

        payload = json.loads(result.body)
        assert "are not in deleted lifecycle stage" in payload["error"]

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_delete_runs_and_experiments_happy_path(self, mock_get_store, mock_get_artifact_repo):
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        backend_store._hard_delete_experiment = MagicMock()
        # No runs remain anywhere: the "get runs from target experiments" fetch and the
        # pre-hard-delete "does this experiment still own a run" check both see this.
        backend_store.search_runs.return_value = []

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

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            run_ids="run-1",
            experiment_ids="exp-1",
            older_than=None,
        )
        assert result.status_code == 200

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == ["run-1"]
        assert payload["deleted_experiments"] == ["exp-1"]

    @pytest.mark.asyncio
    @pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
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

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            run_ids="run-2",
            experiment_ids="e2",
            older_than=None,
        )
        assert result.status_code == 200

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

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == [
            {
                "run_id": "r1",
                "experiment_id": "exp-1",
                "run_name": "n1",
                "status": "FINISHED",
                "start_time": 1,
                "end_time": 2,
                "lifecycle_stage": "deleted",
            }
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

        def search_runs(experiment_ids, filter_string, run_view_type, max_results=None, page_token=None):
            # The pre-hard-delete "does this experiment still own a run" check queries with
            # ViewType.ALL after r1 has already been hard-deleted, so none remain by then.
            if run_view_type == ViewType.ALL:
                return Page([], token=None)
            return Page([run], token=None)

        backend_store.search_experiments.return_value = Page([exp], token=None)
        backend_store.search_runs.side_effect = search_runs
        backend_store._get_deleted_runs.return_value = ["r1"]
        backend_store.get_run.return_value = run

        # artifact repo raising InvalidUrl triggers warning branch but doesn't fail
        from mlflow.exceptions import InvalidUrlException

        mock_repo = MagicMock()
        mock_repo.delete_artifacts.side_effect = InvalidUrlException("bad url")
        mock_get_artifact_repo.return_value = mock_repo

        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            older_than=None,
            run_ids=None,
            experiment_ids=None,
        )
        assert result.status_code == 200

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

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            older_than="1d",
            run_ids="r1",
            experiment_ids=None,
        )
        assert result.status_code == 200

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

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            older_than="1d",
            run_ids=None,
            experiment_ids="eX",
        )
        assert result.status_code == 400

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
        def search_runs(experiment_ids, filter_string, run_view_type, max_results=None, page_token=None):
            # The pre-hard-delete "does this experiment still own a run" check queries with
            # ViewType.ALL after the run has already been hard-deleted, so none remain by then.
            if run_view_type == ViewType.ALL:
                return Page([], token=None)
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

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            older_than=None,
            run_ids=None,
            experiment_ids=None,
        )
        assert result.status_code == 200

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

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            older_than=None,
            run_ids=None,
            experiment_ids=None,
        )
        assert result.status_code == 200

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == []
        assert payload["deleted_experiments"] == []

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_older_than_invalid_returns_400(self, mock_get_store):
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            older_than="bad",
            run_ids=None,
            experiment_ids=None,
        )
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
    async def test_cleanup_artifact_delete_exception_keeps_run(self, mock_get_store, mock_get_artifact_repo):
        """A real artifact-deletion failure must fail safe: the run's metadata is kept (not
        hard-deleted) and the failure is reported, so artifacts that may still exist are not
        orphaned by removing the only record that points at them (#239)."""
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

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            run_ids="r1",
            experiment_ids=None,
            older_than=None,
        )
        assert result.status_code == 200

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == []
        assert any(f["run_id"] == "r1" and f["error"] == "Failed to delete artifacts" for f in payload.get("failed_runs", []))
        # The exception text stays in the server log; it never reaches the client.
        assert "boom-artifact" not in result.body.decode()
        backend_store._hard_delete_run.assert_not_called()

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

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            run_ids="r1",
            experiment_ids=None,
            older_than=None,
        )
        assert result.status_code == 200

        payload = json.loads(result.body)
        assert any(f["run_id"] == "r1" and f["error"] == "Failed to delete run" for f in payload.get("failed_runs", []))
        assert "boom-delete" not in result.body.decode()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_hard_delete_experiment_failure_reports_generic_error(self, mock_get_store):
        """A failed experiment hard delete is reported without the store's exception text."""
        backend_store = MagicMock()
        exp = MagicMock()
        exp.experiment_id = "e2"
        exp.lifecycle_stage = "deleted"
        backend_store.get_experiment.return_value = exp
        backend_store.search_runs.return_value = []
        backend_store._hard_delete_experiment.side_effect = Exception("postgresql://svc:hunter2@db/mlflow refused")
        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            run_ids=None,
            experiment_ids="e2",
            older_than=None,
        )
        assert result.status_code == 200
        payload = json.loads(result.body)
        assert payload["failed_experiments"] == [{"experiment_id": "e2", "error": "Failed to delete experiment"}]
        assert "hunter2" not in result.body.decode()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_missing_run_reports_generic_not_found(self, mock_get_store, mock_get_artifact_repo):
        """A run the store cannot find is reported as not found, without the store's message."""
        backend_store = MagicMock()
        backend_store.get_run.side_effect = MlflowException("Run 'r1' not found in /var/secret/store.db", error_code=RESOURCE_DOES_NOT_EXIST)
        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            run_ids="r1",
            experiment_ids=None,
            older_than=None,
        )
        assert result.status_code == 200
        payload = json.loads(result.body)
        assert payload["failed_runs"] == [{"run_id": "r1", "error": "Run not found"}]
        assert "/var/secret/store.db" not in result.body.decode()
        backend_store._hard_delete_run.assert_not_called()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_resolves_proxied_mlflow_artifacts_uri(self, mock_get_store, mock_get_artifact_repo, monkeypatch):
        """A run's proxied `mlflow-artifacts:` artifact URI must resolve against this server's
        `--artifacts-destination` root, not the process-global tracking URI (which on a server
        is the backend-store DB URI) (#239)."""
        import posixpath

        from mlflow.server import ARTIFACTS_DESTINATION_ENV_VAR

        monkeypatch.setenv(ARTIFACTS_DESTINATION_ENV_VAR, "s3://bucket/dest")

        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        backend_store._hard_delete_experiment = MagicMock()
        backend_store._get_deleted_runs.return_value = ["r1"]

        run = MagicMock()
        run.info.run_id = "r1"
        run.info.lifecycle_stage = "deleted"
        run.info.artifact_uri = "mlflow-artifacts:/exp-1/r1/artifacts"
        run.info.experiment_id = "e1"

        backend_store.get_run.return_value = run
        mock_get_store.return_value = backend_store

        mock_repo = MagicMock()
        mock_get_artifact_repo.return_value = mock_repo

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            run_ids="r1",
            experiment_ids=None,
            older_than=None,
        )
        assert result.status_code == 200

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == ["r1"]

        expected_uri = posixpath.join("s3://bucket/dest", "exp-1/r1/artifacts")
        mock_get_artifact_repo.assert_called_once_with(expected_uri)
        mock_repo.delete_artifacts.assert_called_once()
        backend_store._hard_delete_run.assert_called_once_with("r1")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_proxied_uri_without_artifacts_destination_keeps_run(self, mock_get_store, mock_get_artifact_repo, monkeypatch):
        """When this server has no `--artifacts-destination` configured, a proxied
        `mlflow-artifacts:` URI cannot be resolved to a real storage location. Fail safe: keep
        the run and report the failure instead of hard-deleting metadata for artifacts that may
        still exist (#239)."""
        from mlflow.server import ARTIFACTS_DESTINATION_ENV_VAR

        monkeypatch.delenv(ARTIFACTS_DESTINATION_ENV_VAR, raising=False)

        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        backend_store._get_deleted_runs.return_value = ["r1"]

        run = MagicMock()
        run.info.run_id = "r1"
        run.info.lifecycle_stage = "deleted"
        run.info.artifact_uri = "mlflow-artifacts:/exp-1/r1/artifacts"
        run.info.experiment_id = "e1"

        backend_store.get_run.return_value = run
        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            run_ids="r1",
            experiment_ids=None,
            older_than=None,
        )
        assert result.status_code == 200

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == []
        assert any(f["run_id"] == "r1" for f in payload.get("failed_runs", []))
        mock_get_artifact_repo.assert_not_called()
        backend_store._hard_delete_run.assert_not_called()

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
            result = await permanently_delete_all_trashed_entities(
                admin_username="admin@example.com",
                older_than=None,
                run_ids=None,
                experiment_ids=None,
            )
            assert result.status_code == 200

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
            await permanently_delete_all_trashed_entities(
                admin_username="admin@example.com",
                older_than=None,
                run_ids=None,
                experiment_ids=None,
            )

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

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_keeps_experiment_when_its_run_was_kept(self, mock_get_store, mock_get_artifact_repo):
        """An experiment must not be hard-deleted while one of its runs was kept because its
        artifact deletion failed - MLflow's SqlRun/SqlExperiment relationship cascades on
        delete, so hard-deleting the experiment would delete the kept run's metadata too
        (#239, review round 1). The pre-hard-delete existence check (round 2) sees the kept
        run via the default MagicMock `search_runs` (truthy), so it does not need to be
        configured explicitly here."""
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        backend_store._hard_delete_experiment = MagicMock()
        backend_store._get_deleted_runs.return_value = ["r1"]

        run = MagicMock()
        run.info.run_id = "r1"
        run.info.lifecycle_stage = "deleted"
        run.info.artifact_uri = "some://"
        run.info.experiment_id = "exp-1"

        exp = MagicMock()
        exp.experiment_id = "exp-1"
        exp.lifecycle_stage = "deleted"
        exp.last_update_time = 0

        backend_store.get_run.return_value = run
        backend_store.get_experiment.return_value = exp
        mock_get_store.return_value = backend_store

        mock_repo = MagicMock()
        mock_repo.delete_artifacts.side_effect = Exception("boom-artifact")
        mock_get_artifact_repo.return_value = mock_repo

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            run_ids="r1",
            experiment_ids="exp-1",
            older_than=None,
        )
        assert result.status_code == 200

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == []
        assert payload["deleted_experiments"] == []
        assert any(f["run_id"] == "r1" for f in payload.get("failed_runs", []))

        failed_exp = next((f for f in payload.get("failed_experiments", []) if f["experiment_id"] == "exp-1"), None)
        assert failed_exp is not None
        assert "remain" in failed_exp["error"].lower()
        backend_store._hard_delete_experiment.assert_not_called()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_deletes_experiment_when_its_kept_run_is_in_a_different_experiment(self, mock_get_store, mock_get_artifact_repo):
        """Only the experiment that actually owns a kept run is skipped - an unrelated
        experiment targeted in the same request still gets hard-deleted normally."""
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        backend_store._hard_delete_experiment = MagicMock()
        backend_store._get_deleted_runs.return_value = ["r1"]
        # exp-unrelated owns no runs at all, so the pre-hard-delete existence check must see
        # none remaining for it (the kept run r1 belongs to exp-owner, never queried here).
        backend_store.search_runs.return_value = []

        run = MagicMock()
        run.info.run_id = "r1"
        run.info.lifecycle_stage = "deleted"
        run.info.artifact_uri = "some://"
        run.info.experiment_id = "exp-owner"

        exp_unrelated = MagicMock()
        exp_unrelated.experiment_id = "exp-unrelated"
        exp_unrelated.lifecycle_stage = "deleted"
        exp_unrelated.last_update_time = 0

        backend_store.get_run.return_value = run
        backend_store.get_experiment.return_value = exp_unrelated
        mock_get_store.return_value = backend_store

        mock_repo = MagicMock()
        mock_repo.delete_artifacts.side_effect = Exception("boom-artifact")
        mock_get_artifact_repo.return_value = mock_repo

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            run_ids="r1",
            experiment_ids="exp-unrelated",
            older_than=None,
        )
        assert result.status_code == 200

        payload = json.loads(result.body)
        assert payload["deleted_experiments"] == ["exp-unrelated"]
        backend_store._hard_delete_experiment.assert_called_once_with("exp-unrelated")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_keeps_experiment_when_a_run_is_kept_for_age_not_artifact_failure(self, mock_get_store, mock_get_artifact_repo):
        """The pre-hard-delete existence check must catch every reason a run can be kept, not
        just an artifact-deletion failure. Here the experiment (and one of its two runs) is old
        enough to delete, but the other run is not - deleting the experiment must not
        cascade-delete that too-recent run's metadata (#239, review round 2)."""
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        backend_store._hard_delete_experiment = MagicMock()
        # Only the old run qualifies under --older-than.
        backend_store._get_deleted_runs.return_value = ["r-old"]

        run_old = MagicMock()
        run_old.info.run_id = "r-old"
        run_old.info.lifecycle_stage = "deleted"
        run_old.info.artifact_uri = "s3://bucket/e/r-old/artifacts"
        run_old.info.experiment_id = "exp-1"

        run_new = MagicMock()
        run_new.info.run_id = "r-new"
        run_new.info.lifecycle_stage = "deleted"
        run_new.info.artifact_uri = "s3://bucket/e/r-new/artifacts"
        run_new.info.experiment_id = "exp-1"

        def get_run(run_id):
            return {"r-old": run_old, "r-new": run_new}[run_id]

        backend_store.get_run.side_effect = get_run

        exp = MagicMock()
        exp.experiment_id = "exp-1"
        exp.lifecycle_stage = "deleted"
        exp.last_update_time = 0
        backend_store.get_experiment.return_value = exp

        # "Get runs from target experiments" surfaces both runs of exp-1 (DELETED_ONLY); the
        # pre-hard-delete existence check (ViewType.ALL) still finds r-new, which was kept.
        from mlflow.store.entities import PagedList

        def search_runs(experiment_ids, filter_string, run_view_type, max_results=None, page_token=None):
            if run_view_type == ViewType.ALL:
                return PagedList([run_new], token=None)
            return PagedList([run_old, run_new], token=None)

        backend_store.search_runs.side_effect = search_runs

        mock_repo = MagicMock()
        mock_get_artifact_repo.return_value = mock_repo
        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            # Mirrors the reported reproduction: the caller names the old run explicitly, but
            # naming experiment_ids also pulls in every other run of that experiment (r-new)
            # via the "get runs from target experiments" step below.
            run_ids="r-old",
            experiment_ids="exp-1",
            older_than="1d",
        )
        assert result.status_code == 200

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == ["r-old"]
        assert payload["deleted_experiments"] == []
        assert any(f["run_id"] == "r-new" and "not older than" in f["error"] for f in payload.get("failed_runs", []))

        failed_exp = next((f for f in payload.get("failed_experiments", []) if f["experiment_id"] == "exp-1"), None)
        assert failed_exp is not None
        assert "remain" in failed_exp["error"].lower()
        backend_store._hard_delete_experiment.assert_not_called()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_keeps_experiment_when_existence_check_fails(self, mock_get_store, mock_get_artifact_repo):
        """If the pre-hard-delete existence check itself cannot be answered, fail safe: skip the
        experiment rather than risk cascading a hard delete onto a run that was never checked
        (#239, review round 2)."""
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        backend_store._hard_delete_experiment = MagicMock()
        backend_store._get_deleted_runs.return_value = []

        exp = MagicMock()
        exp.experiment_id = "exp-1"
        exp.lifecycle_stage = "deleted"
        exp.last_update_time = 0
        backend_store.get_experiment.return_value = exp

        backend_store.search_runs.side_effect = Exception("db unavailable")
        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            run_ids=None,
            experiment_ids="exp-1",
            older_than=None,
        )
        assert result.status_code == 200

        payload = json.loads(result.body)
        assert payload["deleted_experiments"] == []
        failed_exp = next((f for f in payload.get("failed_experiments", []) if f["experiment_id"] == "exp-1"), None)
        assert failed_exp is not None
        assert failed_exp["error"] == "Could not verify no runs remain"
        assert "db unavailable" not in result.body.decode()
        backend_store._hard_delete_experiment.assert_not_called()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_cleanup_with_only_run_ids_does_not_sweep_other_experiments(self, mock_get_store, mock_get_artifact_repo):
        """When the request gives run_ids but no experiment_ids (the UI's "delete selected
        runs"), only those runs are touched - no other trashed experiment (or its runs) may be
        hard-deleted as a side effect (#239, review round 2)."""
        backend_store = MagicMock()
        backend_store._hard_delete_run = MagicMock()
        backend_store._hard_delete_experiment = MagicMock()

        run_a = MagicMock()
        run_a.info.run_id = "ra"
        run_a.info.lifecycle_stage = "deleted"
        run_a.info.artifact_uri = "s3://bucket/ea/ra/artifacts"
        run_a.info.experiment_id = "ea"
        backend_store.get_run.return_value = run_a

        mock_repo = MagicMock()
        mock_get_artifact_repo.return_value = mock_repo
        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            run_ids="ra",
            experiment_ids=None,
            older_than=None,
        )
        assert result.status_code == 200

        payload = json.loads(result.body)
        assert payload["deleted_runs"] == ["ra"]
        assert payload["deleted_experiments"] == []
        # Only the selected run's own experiment lookups happen - search_experiments (used only
        # to sweep "all deleted experiments") is never called.
        backend_store.search_experiments.assert_not_called()
        backend_store._hard_delete_experiment.assert_not_called()


class TestResolveRunArtifactRepository:
    """Unit coverage for _resolve_run_artifact_repository (#239)."""

    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    def test_non_proxied_uri_passes_through_unchanged(self, mock_get_artifact_repo):
        from mlflow_oidc_auth.routers.trash import _resolve_run_artifact_repository

        mock_get_artifact_repo.return_value = "repo"
        result = _resolve_run_artifact_repository("s3://bucket/exp/run/artifacts")

        mock_get_artifact_repo.assert_called_once_with("s3://bucket/exp/run/artifacts")
        assert result == "repo"

    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    def test_proxied_uri_resolves_against_artifacts_destination(self, mock_get_artifact_repo, monkeypatch):
        import posixpath

        from mlflow.server import ARTIFACTS_DESTINATION_ENV_VAR

        from mlflow_oidc_auth.routers.trash import _resolve_run_artifact_repository

        monkeypatch.setenv(ARTIFACTS_DESTINATION_ENV_VAR, "s3://bucket/dest")
        mock_get_artifact_repo.return_value = "repo"

        result = _resolve_run_artifact_repository("mlflow-artifacts:/exp-1/run-1/artifacts")

        mock_get_artifact_repo.assert_called_once_with(posixpath.join("s3://bucket/dest", "exp-1/run-1/artifacts"))
        assert result == "repo"

    def test_proxied_uri_without_destination_raises(self, monkeypatch):
        from mlflow.exceptions import MlflowException
        from mlflow.server import ARTIFACTS_DESTINATION_ENV_VAR

        from mlflow_oidc_auth.routers.trash import _resolve_run_artifact_repository

        monkeypatch.delenv(ARTIFACTS_DESTINATION_ENV_VAR, raising=False)

        with pytest.raises(MlflowException):
            _resolve_run_artifact_repository("mlflow-artifacts:/exp-1/run-1/artifacts")

    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    def test_proxied_uri_with_no_path_raises_instead_of_resolving_to_destination_root(self, mock_get_artifact_repo, monkeypatch):
        """A `mlflow-artifacts:` URI with no path of its own (e.g. "mlflow-artifacts:/") must
        not silently resolve to the whole --artifacts-destination root - that would treat every
        other run's artifacts under it as this run's own and delete them all (#239, review
        round 2)."""
        from mlflow.exceptions import MlflowException
        from mlflow.server import ARTIFACTS_DESTINATION_ENV_VAR

        from mlflow_oidc_auth.routers.trash import _resolve_run_artifact_repository

        monkeypatch.setenv(ARTIFACTS_DESTINATION_ENV_VAR, "s3://bucket/dest")

        for empty_path_uri in ("mlflow-artifacts:/", "mlflow-artifacts://host", "mlflow-artifacts:///"):
            with pytest.raises(MlflowException):
                _resolve_run_artifact_repository(empty_path_uri)

        mock_get_artifact_repo.assert_not_called()


class TestCleanupRunAgeWithinTargetedExperiment:
    """``older_than`` still applies to every run of an experiment being emptied."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.trash.get_artifact_repository")
    @patch("mlflow_oidc_auth.routers.trash._get_store")
    async def test_recently_deleted_run_in_old_experiment_is_kept(self, mock_get_store, mock_get_artifact_repo):
        backend_store = MagicMock()
        backend_store._get_deleted_runs.return_value = ["old-run"]

        experiment = MagicMock()
        experiment.experiment_id = "e1"
        experiment.lifecycle_stage = "deleted"
        experiment.last_update_time = 0
        backend_store.get_experiment.return_value = experiment

        def make_run(run_id):
            run = MagicMock()
            run.info.run_id = run_id
            run.info.lifecycle_stage = "deleted"
            run.info.artifact_uri = f"s3://bucket/e1/{run_id}/artifacts"
            run.info.experiment_id = "e1"
            return run

        runs = {run_id: make_run(run_id) for run_id in ("old-run", "new-run")}
        backend_store.get_run.side_effect = lambda run_id: runs[run_id]

        class Page(list):
            token = None

        def search_runs(**kwargs):
            if kwargs.get("run_view_type") == ViewType.ALL:
                return Page([runs["new-run"]])
            return Page(list(runs.values()))

        backend_store.search_runs.side_effect = search_runs
        mock_get_store.return_value = backend_store

        result = await permanently_delete_all_trashed_entities(
            admin_username="admin@example.com",
            older_than="1d",
            run_ids=None,
            experiment_ids="e1",
        )

        assert result.status_code == 200
        payload = json.loads(result.body)
        assert payload["deleted_runs"] == ["old-run"]
        assert [f["run_id"] for f in payload["failed_runs"]] == ["new-run"]
        assert "not older than" in payload["failed_runs"][0]["error"]
        assert [f["experiment_id"] for f in payload["failed_experiments"]] == ["e1"]
        backend_store._hard_delete_run.assert_called_once_with("old-run")
        backend_store._hard_delete_experiment.assert_not_called()
