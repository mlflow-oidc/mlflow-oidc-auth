"""Permission rows of permanently deleted experiments (#487): the cleanup removes them, the sweep catches the rest."""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INTERNAL_ERROR, RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.models.trash import PermissionSweepResponse
from mlflow_oidc_auth.routers import trash as _trash
from mlflow_oidc_auth.routers.trash import trash_router
from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
from mlflow_oidc_auth.tests.contract import checked

cleanup = checked(_trash.permanently_delete_all_trashed_entities)


def sweep(**kwargs):
    """The sync handler, its body checked against the declared model."""
    result = _trash.sweep_orphaned_experiment_permissions(**kwargs)
    PermissionSweepResponse.model_validate_json(result.body)
    return result


FLUSH = "mlflow_oidc_auth.utils.permissions.flush_permission_cache"


@pytest.fixture
def auth_store(tmp_path):
    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user("alice@example.com", "Alice")
    s.populate_groups(["team"])
    for exp in ("1", "2"):
        s.create_experiment_permission(exp, "alice@example.com", "MANAGE")
        s.create_group_experiment_permission("team", exp, "READ")
        s.create_scorer_permission(exp, "scorer", "alice@example.com", "MANAGE")
        s.create_group_scorer_permission("team", exp, "scorer", "READ")
    for exp in ("1", "2"):
        s.record_detection_schedule_author(exp, None, "alice@example.com", "fp")
    # Patterns are not ids: they must survive any cleanup.
    s.create_experiment_regex_permission("^1$", 1, "READ", "alice@example.com")
    with patch.object(_trash, "store", s):
        yield s
    s.engine.dispose()


def _backend(deleted_ids):
    backend = MagicMock()

    def get_experiment(exp_id):
        exp = MagicMock()
        exp.experiment_id = exp_id
        exp.lifecycle_stage = "deleted"
        exp.last_update_time = 0
        return exp

    backend.get_experiment.side_effect = get_experiment
    backend.search_runs.return_value = []
    return backend


class TestCleanupRemovesRows:
    @pytest.mark.asyncio
    async def test_removes_exactly_the_deleted_experiments_rows(self, auth_store):
        backend = _backend(["1"])
        with patch.object(_trash, "_get_store", return_value=backend), patch(FLUSH) as flush:
            result = await cleanup(admin_username="admin", run_ids=None, experiment_ids="1", older_than=None)
        assert result.status_code == 200
        payload = json.loads(result.body)
        assert payload["deleted_experiments"] == ["1"]
        assert "failed_permission_cleanups" not in payload
        assert auth_store.list_experiment_ids_with_grants() == ["2"]
        assert len(auth_store.list_experiment_permissions_for_experiment("2")) == 1  # the user grant of 2 survives
        assert flush.called
        # regex grants are untouched
        assert len(auth_store.list_experiment_regex_permissions("alice@example.com")) == 1

    @pytest.mark.asyncio
    async def test_a_kept_experiment_keeps_its_rows(self, auth_store):
        backend = _backend(["1"])
        backend._hard_delete_experiment.side_effect = Exception("boom")
        with patch.object(_trash, "_get_store", return_value=backend):
            result = await cleanup(admin_username="admin", run_ids=None, experiment_ids="1", older_than=None)
        assert json.loads(result.body)["failed_experiments"][0]["experiment_id"] == "1"
        assert auth_store.list_experiment_ids_with_grants() == ["1", "2"]

    @pytest.mark.asyncio
    async def test_a_grant_cleanup_failure_is_reported_not_a_500(self, auth_store):
        backend = _backend(["1"])
        with (
            patch.object(_trash, "_get_store", return_value=backend),
            patch.object(auth_store, "delete_experiment_grant_rows", side_effect=Exception("db down: secret")),
        ):
            result = await cleanup(admin_username="admin", run_ids=None, experiment_ids="1", older_than=None)
        assert result.status_code == 200
        payload = json.loads(result.body)
        assert payload["deleted_experiments"] == ["1"]
        assert payload["failed_permission_cleanups"] == [{"experiment_id": "1", "error": "Failed to remove permission rows"}]
        assert "secret" not in result.body.decode()


class TestSnapshotRace:
    @pytest.mark.asyncio
    async def test_cleanup_keeps_a_grant_created_after_the_snapshot(self, auth_store):
        backend = _backend(["1"])
        auth_store.create_user("bob@example.com", "Bob")

        def hard_delete(exp_id):
            # an id reused by a new experiment, whose creator is granted MANAGE
            auth_store.create_experiment_permission("1", "bob@example.com", "MANAGE")

        backend._hard_delete_experiment.side_effect = hard_delete
        with patch.object(_trash, "_get_store", return_value=backend):
            result = await cleanup(admin_username="admin", run_ids=None, experiment_ids="1", older_than=None)
        assert json.loads(result.body)["deleted_experiments"] == ["1"]
        rows = auth_store.list_experiment_permissions_for_experiment("1")
        assert [r.user_id for r in rows] and len(rows) == 1  # only bob's new row remains
        assert auth_store.snapshot_experiment_grant_rows(["1"]).keys() == {"experiment_permissions"}

    @pytest.mark.asyncio
    async def test_cleanup_removes_schedule_author_rows(self, auth_store):
        backend = _backend(["1"])
        with patch.object(_trash, "_get_store", return_value=backend):
            await cleanup(admin_username="admin", run_ids=None, experiment_ids="1", older_than=None)
        assert auth_store.get_detection_schedule_author("1") is None
        assert auth_store.get_detection_schedule_author("2") is not None

    @pytest.mark.asyncio
    async def test_sweep_keeps_a_grant_created_after_the_snapshot(self, auth_store, tracking):
        auth_store.create_user("bob@example.com", "Bob")
        t = tracking({None: {"2"}})
        real = _trash.experiments_definitively_missing

        def lookup(ids):
            result = real(ids)
            if not getattr(lookup, "done", False):
                lookup.done = True
                auth_store.create_experiment_permission("3", "bob@example.com", "MANAGE")
                auth_store.create_scorer_permission("1", "late", "bob@example.com", "MANAGE")
            return result

        with patch.object(_trash, "experiments_definitively_missing", lookup):
            body = json.loads(sweep(admin_username="admin", dry_run=False).body)
        assert body["missing_experiments"] == ["1"]
        assert auth_store.list_experiment_ids_with_grants() == ["1", "2", "3"]  # 1 keeps only the late scorer row
        assert auth_store.snapshot_experiment_grant_rows(["1"]).keys() == {"scorer_permissions"}
        assert auth_store.get_detection_schedule_author("1") is None

    @pytest.mark.asyncio
    async def test_sweep_drops_an_id_that_exists_at_the_second_lookup(self, auth_store, tracking):
        t = tracking({None: set()})
        real = _trash.experiments_definitively_missing
        calls = []

        def lookup(ids):
            calls.append(list(ids))
            if len(calls) == 2:
                t.existing = {None: {"1"}}  # moved or recreated in the meantime
            return real(ids)

        with patch.object(_trash, "experiments_definitively_missing", lookup):
            body = json.loads(sweep(admin_username="admin", dry_run=False).body)
        assert body["missing_experiments"] == ["2"]
        assert auth_store.list_experiment_ids_with_grants() == ["1"]


class _Tracking:
    """Tracking store stand-in: ``existing`` maps workspace -> ids; ``broken`` ids raise a non-404 error."""

    def __init__(self, existing, broken=()):
        self.existing, self.broken, self.workspace = existing, set(broken), None

    def get_experiment(self, experiment_id):
        if experiment_id in self.broken:
            raise MlflowException("store unavailable", error_code=INTERNAL_ERROR)
        if experiment_id in self.existing.get(self.workspace, ()):
            return MagicMock()
        raise MlflowException("nope", error_code=RESOURCE_DOES_NOT_EXIST)


@pytest.fixture
def tracking(monkeypatch):
    def install(existing, broken=(), workspaces=(None,)):
        t = _Tracking(existing, broken)

        @contextmanager
        def in_ws(ws):
            t.workspace = ws
            yield

        monkeypatch.setattr("mlflow_oidc_auth.orphans._lookup_workspaces", lambda: list(workspaces))
        monkeypatch.setattr("mlflow_oidc_auth.orphans._in_workspace", in_ws)
        monkeypatch.setattr("mlflow.server.handlers._get_tracking_store", lambda *a, **k: t)
        return t

    return install


class TestSweep:
    @pytest.mark.asyncio
    async def test_dry_run_is_the_default_and_deletes_nothing(self, auth_store, tracking):
        import inspect

        assert inspect.signature(_trash.sweep_orphaned_experiment_permissions).parameters["dry_run"].default.default is True
        tracking({None: {"2"}})
        body = json.loads(sweep(admin_username="admin", dry_run=True).body)
        assert body["dry_run"] is True and body["missing_experiments"] == ["1"] and body["removed_rows"] == 0
        assert auth_store.list_experiment_ids_with_grants() == ["1", "2"]

    @pytest.mark.asyncio
    async def test_removes_only_the_missing_experiments_rows(self, auth_store, tracking):
        tracking({None: {"2"}})
        with patch(FLUSH) as flush:
            body = json.loads(sweep(admin_username="admin", dry_run=False).body)
        assert body["missing_experiments"] == ["1"] and body["removed_rows"] == 5
        assert auth_store.list_experiment_ids_with_grants() == ["2"]
        assert flush.called

    @pytest.mark.asyncio
    async def test_keeps_rows_of_an_experiment_in_another_workspace(self, auth_store, tracking):
        tracking({"team-a": {"1"}, "team-b": {"2"}}, workspaces=("team-a", "team-b"))
        body = json.loads(sweep(admin_username="admin", dry_run=False).body)
        assert body["missing_experiments"] == [] and body["removed_rows"] == 0
        assert auth_store.list_experiment_ids_with_grants() == ["1", "2"]

    @pytest.mark.asyncio
    async def test_keeps_rows_when_the_lookup_errors(self, auth_store, tracking):
        tracking({}, broken={"1"})
        body = json.loads(sweep(admin_username="admin", dry_run=False).body)
        assert body["missing_experiments"] == ["2"]
        assert body["unresolved_experiments"] == ["1"]
        assert auth_store.list_experiment_ids_with_grants() == ["1"]

    @pytest.mark.asyncio
    async def test_keeps_everything_when_workspaces_cannot_be_listed(self, auth_store, monkeypatch):
        monkeypatch.setattr("mlflow_oidc_auth.orphans._lookup_workspaces", lambda: None)
        body = json.loads(sweep(admin_username="admin", dry_run=False).body)
        assert body["missing_experiments"] == [] and sorted(body["unresolved_experiments"]) == ["1", "2"]
        assert auth_store.list_experiment_ids_with_grants() == ["1", "2"]

    @pytest.mark.asyncio
    async def test_keeps_everything_when_the_tracking_store_is_unavailable(self, auth_store, monkeypatch):
        monkeypatch.setattr("mlflow_oidc_auth.orphans._lookup_workspaces", lambda: [None])

        def boom(*a, **k):
            raise RuntimeError("down")

        monkeypatch.setattr("mlflow.server.handlers._get_tracking_store", boom)
        body = json.loads(sweep(admin_username="admin", dry_run=False).body)
        assert body["missing_experiments"] == []
        assert auth_store.list_experiment_ids_with_grants() == ["1", "2"]

    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self, auth_store):
        app = FastAPI()
        app.include_router(trash_router)
        response = TestClient(app).post("/oidc/trash/permissions/sweep?dry_run=false")
        assert response.status_code == 403
        assert auth_store.list_experiment_ids_with_grants() == ["1", "2"]
