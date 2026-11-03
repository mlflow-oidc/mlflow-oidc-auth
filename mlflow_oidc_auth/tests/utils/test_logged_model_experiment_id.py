"""Tests for get_logged_model_experiment_id: a logged model's experiment id without loading the model.

Logged-model permission checks used ``get_logged_model(model_id).experiment_id``. On MLflow's
SQL store, ``get_logged_model`` also loads every tag, param and metric data point of the
model, so a model that collects metrics at every training step made each check slower as the
training went on. These tests run against a real MLflow SQL tracking store on SQLite, because
the claims are about the statements it issues and the errors it raises.
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from mlflow.entities import Metric
from mlflow.environment_variables import MLFLOW_ENABLE_WORKSPACES
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode
from mlflow.store.tracking.dbmodels.models import SqlLoggedModel
from mlflow.store.tracking.sqlalchemy_store import SqlAlchemyStore
from mlflow.tracking._tracking_service import utils as tracking_utils
from mlflow.utils.workspace_context import WorkspaceContext
from sqlalchemy import event

from mlflow_oidc_auth.utils import data_fetching, get_logged_model_experiment_id

_IGNORED_PREFIXES = ("PRAGMA", "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE")


def _new_model(store, experiment_id, *, metric_points=0):
    run_id = store.create_run(experiment_id, user_id="alice", start_time=int(time.time() * 1000), tags=[], run_name="r").info.run_id
    model = store.create_logged_model(experiment_id=experiment_id, name="m", source_run_id=run_id)
    metrics = [Metric(f"eval/key_{i % 20}", float(i), 0, i // 20, model_id=model.model_id) for i in range(metric_points)]
    for start in range(0, len(metrics), 1000):
        store.log_batch(run_id, metrics=metrics[start : start + 1000], params=[], tags=[])
    return model.model_id


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
    def test_returns_the_same_experiment_id_as_get_logged_model(self, tracking_store):
        """The value, and its type, must be what the checks used to read from ``get_logged_model``."""
        tracking_store.create_experiment("decoy")
        experiment_id = tracking_store.create_experiment("owner")
        model_id = _new_model(tracking_store, experiment_id, metric_points=3)

        result = get_logged_model_experiment_id(tracking_store, model_id)

        assert result == tracking_store.get_logged_model(model_id).experiment_id == experiment_id
        assert isinstance(result, str)

    @pytest.mark.parametrize("metric_points", [0, 50, 2000])
    def test_reads_only_the_model_row(self, tracking_store, statements, metric_points):
        """One statement, whatever the model holds. ``get_logged_model`` issues 4 and builds every row."""
        model_id = _new_model(tracking_store, tracking_store.create_experiment(f"points-{metric_points}"), metric_points=metric_points)
        statements.clear()

        get_logged_model_experiment_id(tracking_store, model_id)

        assert len(statements) == 1, statements

    def test_does_not_call_get_logged_model(self, tracking_store):
        model_id = _new_model(tracking_store, tracking_store.create_experiment("no-get-logged-model"))

        with patch.object(tracking_store, "get_logged_model", wraps=tracking_store.get_logged_model) as spy:
            get_logged_model_experiment_id(tracking_store, model_id)

        spy.assert_not_called()

    def test_a_missing_model_raises_as_get_logged_model_does(self, tracking_store):
        """The caller must still see RESOURCE_DOES_NOT_EXIST (a 404, or a denial), never a default."""
        with pytest.raises(MlflowException) as from_get:
            tracking_store.get_logged_model("m-" + "0" * 32)
        with pytest.raises(MlflowException) as from_helper:
            get_logged_model_experiment_id(tracking_store, "m-" + "0" * 32)

        assert _is_not_found(from_get.value)
        assert _is_not_found(from_helper.value)
        assert from_helper.value.message == from_get.value.message

    def test_a_deleted_model_is_not_found_as_with_get_logged_model(self, tracking_store):
        """``get_logged_model`` hides deleted models, and so must the helper."""
        model_id = _new_model(tracking_store, tracking_store.create_experiment("deleted-model"))
        tracking_store.delete_logged_model(model_id)

        with pytest.raises(MlflowException) as from_get:
            tracking_store.get_logged_model(model_id)
        with pytest.raises(MlflowException) as from_helper:
            get_logged_model_experiment_id(tracking_store, model_id)

        assert _is_not_found(from_get.value)
        assert _is_not_found(from_helper.value)

    def test_a_row_with_no_lifecycle_stage_is_hidden_as_with_get_logged_model(self, tracking_store):
        """SQL ``lifecycle_stage != 'deleted'`` also excludes NULL; the helper must apply it in SQL, not in Python."""
        model_id = _new_model(tracking_store, tracking_store.create_experiment("null-lifecycle"))
        with tracking_store.ManagedSessionMaker() as session:
            session.query(SqlLoggedModel).filter(SqlLoggedModel.model_id == model_id).update({SqlLoggedModel.lifecycle_stage: None})

        with pytest.raises(MlflowException) as from_get:
            tracking_store.get_logged_model(model_id)
        with pytest.raises(MlflowException) as from_helper:
            get_logged_model_experiment_id(tracking_store, model_id)

        assert _is_not_found(from_get.value)
        assert _is_not_found(from_helper.value)

    def test_a_subclass_that_overrides_get_logged_model_keeps_its_override(self, tracking_store):
        """A store that changes ``get_logged_model`` may change what a model resolves to; honour it."""

        class CustomStore(SqlAlchemyStore):
            def get_logged_model(self, model_id, allow_deleted=False):
                return MagicMock(experiment_id="from-override")

        custom = CustomStore.__new__(CustomStore)

        assert get_logged_model_experiment_id(custom, "any-model") == "from-override"


class TestPrivateLookup:
    """``_get_query`` is private MLflow API; a change must slow the checks, not break them."""

    def test_is_available_on_the_installed_mlflow(self):
        """Fails when MLflow changes the hook: the checks then run at ``get_logged_model`` speed again."""
        assert data_fetching._LOGGED_MODEL_ROW_LOOKUP is True

    def test_a_changed_signature_is_detected(self):
        def _get_query(self, session, entity):
            return None

        with patch.object(SqlAlchemyStore, "_get_query", _get_query):
            assert data_fetching._has_logged_model_row_lookup() is False

    def test_without_it_the_sql_store_falls_back_to_get_logged_model(self, tracking_store):
        experiment_id = tracking_store.create_experiment("no-private-lookup")
        model_id = _new_model(tracking_store, experiment_id)

        with (
            patch.object(data_fetching, "_LOGGED_MODEL_ROW_LOOKUP", False),
            patch.object(tracking_store, "get_logged_model", wraps=tracking_store.get_logged_model) as spy,
        ):
            assert get_logged_model_experiment_id(tracking_store, model_id) == experiment_id

        spy.assert_called_once_with(model_id)


class TestOtherStores:
    def test_falls_back_to_get_logged_model(self):
        store = MagicMock()
        store.get_logged_model.return_value.experiment_id = "42"

        assert get_logged_model_experiment_id(store, "m-1") == "42"
        store.get_logged_model.assert_called_once_with("m-1")

    def test_propagates_get_logged_model_errors(self):
        store = MagicMock()
        store.get_logged_model.side_effect = MlflowException("gone", RESOURCE_DOES_NOT_EXIST)

        with pytest.raises(MlflowException) as raised:
            get_logged_model_experiment_id(store, "m-1")

        assert _is_not_found(raised.value)


class TestWorkspaceAwareStore:
    """With workspaces on, a model in another workspace must stay invisible, as with ``get_logged_model``."""

    @pytest.fixture
    def workspace_store(self, tmp_path, monkeypatch):
        monkeypatch.setenv(MLFLOW_ENABLE_WORKSPACES.name, "true")
        store = tracking_utils._get_sqlalchemy_store(f"sqlite:///{tmp_path / 'mlflow.db'}", (tmp_path / "artifacts").as_uri())
        yield store
        store._dispose_engine()

    def _model_in(self, store, workspace):
        with WorkspaceContext(workspace):
            experiment_id = store.create_experiment(f"exp-{workspace}")
            return experiment_id, _new_model(store, experiment_id)

    def test_resolves_a_model_in_the_active_workspace_in_one_statement(self, workspace_store):
        experiment_id, model_id = self._model_in(workspace_store, "team-a")
        issued = []

        def _record(conn, cursor, statement, parameters, context, executemany):
            if not statement.lstrip().upper().startswith(_IGNORED_PREFIXES):
                issued.append(statement)

        event.listen(workspace_store.engine, "before_cursor_execute", _record)
        try:
            with WorkspaceContext("team-a"):
                assert get_logged_model_experiment_id(workspace_store, model_id) == experiment_id
        finally:
            event.remove(workspace_store.engine, "before_cursor_execute", _record)

        assert len(issued) == 1, issued

    def test_a_model_in_another_workspace_is_not_found(self, workspace_store):
        _, other_model = self._model_in(workspace_store, "team-a")
        self._model_in(workspace_store, "team-b")

        with WorkspaceContext("team-b"):
            with pytest.raises(MlflowException) as from_get:
                workspace_store.get_logged_model(other_model)
            with pytest.raises(MlflowException) as from_helper:
                get_logged_model_experiment_id(workspace_store, other_model)

        assert _is_not_found(from_get.value)
        assert _is_not_found(from_helper.value)
