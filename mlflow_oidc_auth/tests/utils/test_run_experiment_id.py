"""Tests for get_run_experiment_id: a run's experiment id without loading the run.

Run-scoped permission checks used ``get_run(run_id).info.experiment_id``. On MLflow's SQL
store, ``get_run`` also loads every latest metric, param and tag, so for a run with
thousands of metric keys every check cost as much as a ``runs/get``. These tests run
against a real MLflow SQL tracking store on SQLite, because the claims are about the
statements it issues and the errors it raises.
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from mlflow.entities import Metric, Param, RunTag
from mlflow.environment_variables import MLFLOW_ENABLE_WORKSPACES
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode
from mlflow.store.tracking.sqlalchemy_store import SqlAlchemyStore
from mlflow.tracking._tracking_service import utils as tracking_utils
from mlflow.utils.workspace_context import WorkspaceContext
from sqlalchemy import event

from mlflow_oidc_auth.utils import data_fetching, get_run_experiment_id

_IGNORED_PREFIXES = ("PRAGMA", "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE")


def _new_run(store, experiment_id, *, metric_keys=0, params=0, tags=0):
    run_id = store.create_run(experiment_id, user_id="alice", start_time=int(time.time() * 1000), tags=[], run_name="r").info.run_id
    metrics = [Metric(f"key_{i}", float(i), 0, 0) for i in range(metric_keys)]
    for start in range(0, len(metrics), 1000):
        store.log_batch(run_id, metrics=metrics[start : start + 1000], params=[], tags=[])
    store.log_batch(run_id, metrics=[], params=[Param(f"p{i}", "v") for i in range(params)], tags=[RunTag(f"t{i}", "v") for i in range(tags)])
    return run_id


@pytest.fixture(scope="module")
def tracking_store(tmp_path_factory):
    """A real MLflow SQL tracking store on SQLite, shared by the module (migrations take seconds)."""
    root = tmp_path_factory.mktemp("tracking")
    store = SqlAlchemyStore(f"sqlite:///{root / 'mlflow.db'}", (root / "artifacts").as_uri())
    yield store
    store._dispose_engine()


@pytest.fixture
def statements(tracking_store):
    """The application statements issued on the tracking store's engine while the test runs."""
    issued = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        if not statement.lstrip().upper().startswith(_IGNORED_PREFIXES):
            issued.append(statement)

    event.listen(tracking_store.engine, "before_cursor_execute", _record)
    yield issued
    event.remove(tracking_store.engine, "before_cursor_execute", _record)


def _is_not_found(error: MlflowException) -> bool:
    return error.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST)


class TestSqlStore:
    def test_returns_the_same_experiment_id_as_get_run(self, tracking_store):
        """The value, and its type, must be what the checks used to read from ``get_run``."""
        tracking_store.create_experiment("decoy")
        experiment_id = tracking_store.create_experiment("owner")
        run_id = _new_run(tracking_store, experiment_id, metric_keys=3)

        result = get_run_experiment_id(tracking_store, run_id)

        assert result == tracking_store.get_run(run_id).info.experiment_id == experiment_id
        assert isinstance(result, str)

    @pytest.mark.parametrize("metric_keys", [0, 50, 2000])
    def test_reads_only_the_run_row(self, tracking_store, statements, metric_keys):
        """One statement, whatever the run holds. ``get_run`` issues 7 and builds every row."""
        experiment_id = tracking_store.create_experiment(f"keys-{metric_keys}")
        run_id = _new_run(tracking_store, experiment_id, metric_keys=metric_keys, params=20, tags=5)
        statements.clear()

        get_run_experiment_id(tracking_store, run_id)

        assert len(statements) == 1, statements

    def test_does_not_call_get_run(self, tracking_store):
        run_id = _new_run(tracking_store, tracking_store.create_experiment("no-get-run"))

        with patch.object(tracking_store, "get_run", wraps=tracking_store.get_run) as spy:
            get_run_experiment_id(tracking_store, run_id)

        spy.assert_not_called()

    def test_a_missing_run_raises_as_get_run_does(self, tracking_store):
        """The caller must still see RESOURCE_DOES_NOT_EXIST (a 404), never a default."""
        with pytest.raises(MlflowException) as from_get_run:
            tracking_store.get_run("0" * 32)
        with pytest.raises(MlflowException) as from_helper:
            get_run_experiment_id(tracking_store, "0" * 32)

        assert _is_not_found(from_get_run.value)
        assert _is_not_found(from_helper.value)

    @pytest.mark.parametrize("pattern", ["%", "_" * 32, "", "' OR 1=1 --"])
    def test_a_run_id_is_matched_exactly_never_as_a_pattern(self, tracking_store, pattern):
        """Wildcards and quotes in a run id match no run, as with ``get_run``: the lookup is equality."""
        experiment_id = tracking_store.create_experiment(f"exact-match-{len(pattern)}-{pattern[:1]!r}")
        run_id = _new_run(tracking_store, experiment_id)

        for run_id_or_pattern in (pattern, run_id[:8] + "%"):
            with pytest.raises(MlflowException) as from_get_run:
                tracking_store.get_run(run_id_or_pattern)
            with pytest.raises(MlflowException) as from_helper:
                get_run_experiment_id(tracking_store, run_id_or_pattern)
            assert _is_not_found(from_get_run.value)
            assert _is_not_found(from_helper.value)

    def test_a_deleted_run_still_resolves_as_with_get_run(self, tracking_store):
        """``get_run`` returns soft-deleted runs; the checks must see the same run."""
        experiment_id = tracking_store.create_experiment("deleted-run")
        run_id = _new_run(tracking_store, experiment_id)
        tracking_store.delete_run(run_id)

        assert get_run_experiment_id(tracking_store, run_id) == tracking_store.get_run(run_id).info.experiment_id == experiment_id

    def test_a_subclass_that_overrides_get_run_keeps_its_override(self, tracking_store):
        """A store that changes ``get_run`` may change what a run resolves to; honour it."""

        class CustomStore(SqlAlchemyStore):
            def get_run(self, run_id):
                return MagicMock(info=MagicMock(experiment_id="from-override"))

        custom = CustomStore.__new__(CustomStore)

        assert get_run_experiment_id(custom, "any-run") == "from-override"


class TestPrivateLookup:
    """``SqlAlchemyStore._get_run`` is private MLflow API; a change must slow the checks, not break them."""

    def test_is_available_on_the_installed_mlflow(self):
        """Fails when MLflow changes ``_get_run``: the checks then run at ``get_run`` speed again."""
        assert data_fetching._RUN_ROW_LOOKUP is True

    def test_a_changed_signature_is_detected(self):
        def _get_run(self, session, run_id, eager=False):
            return None

        with patch.object(SqlAlchemyStore, "_get_run", _get_run):
            assert data_fetching._has_run_row_lookup() is False

    def test_without_it_the_sql_store_falls_back_to_get_run(self, tracking_store):
        experiment_id = tracking_store.create_experiment("no-private-lookup")
        run_id = _new_run(tracking_store, experiment_id)

        with (
            patch.object(data_fetching, "_RUN_ROW_LOOKUP", False),
            patch.object(tracking_store, "get_run", wraps=tracking_store.get_run) as spy,
        ):
            assert get_run_experiment_id(tracking_store, run_id) == experiment_id

        spy.assert_called_once_with(run_id)


class TestOtherStores:
    def test_falls_back_to_get_run(self):
        store = MagicMock()
        store.get_run.return_value.info.experiment_id = "42"

        assert get_run_experiment_id(store, "run-1") == "42"
        store.get_run.assert_called_once_with("run-1")

    def test_propagates_get_run_errors(self):
        store = MagicMock()
        store.get_run.side_effect = MlflowException("gone", RESOURCE_DOES_NOT_EXIST)

        with pytest.raises(MlflowException) as raised:
            get_run_experiment_id(store, "run-1")

        assert _is_not_found(raised.value)


class TestWorkspaceAwareStore:
    """With workspaces on, a run in another workspace must stay invisible, as with ``get_run``."""

    @pytest.fixture
    def workspace_store(self, tmp_path, monkeypatch):
        monkeypatch.setenv(MLFLOW_ENABLE_WORKSPACES.name, "true")
        store = tracking_utils._get_sqlalchemy_store(f"sqlite:///{tmp_path / 'mlflow.db'}", (tmp_path / "artifacts").as_uri())
        yield store
        store._dispose_engine()

    def _run_in(self, store, workspace):
        with WorkspaceContext(workspace):
            experiment_id = store.create_experiment(f"exp-{workspace}")
            return experiment_id, _new_run(store, experiment_id)

    def test_resolves_a_run_in_the_active_workspace_in_one_statement(self, workspace_store):
        experiment_id, run_id = self._run_in(workspace_store, "team-a")
        issued = []

        def _record(conn, cursor, statement, parameters, context, executemany):
            if not statement.lstrip().upper().startswith(_IGNORED_PREFIXES):
                issued.append(statement)

        event.listen(workspace_store.engine, "before_cursor_execute", _record)
        try:
            with WorkspaceContext("team-a"):
                assert get_run_experiment_id(workspace_store, run_id) == experiment_id
        finally:
            event.remove(workspace_store.engine, "before_cursor_execute", _record)

        assert len(issued) == 1, issued

    def test_a_run_in_another_workspace_is_not_found(self, workspace_store):
        _, other_run = self._run_in(workspace_store, "team-a")
        self._run_in(workspace_store, "team-b")

        with WorkspaceContext("team-b"):
            with pytest.raises(MlflowException) as from_get_run:
                workspace_store.get_run(other_run)
            with pytest.raises(MlflowException) as from_helper:
                get_run_experiment_id(workspace_store, other_run)

        assert _is_not_found(from_get_run.value)
        assert _is_not_found(from_helper.value)
