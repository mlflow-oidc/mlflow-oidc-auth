"""Query-count regression tests for run-scoped permission checks.

A run inherits its permission from its experiment, so a run-scoped check needs one value:
the run's experiment id. The checks read it from ``get_run``, which on MLflow's SQL store
also loads every latest metric, param and tag of the run: 7 statements, and an entity for
every row. A client that reads ``metrics/get-history`` once per metric key then paid
O(keys) per call and O(keys^2) per run, and every ``log-batch`` reloaded the whole run.

These tests count the statements a check issues on a real MLflow SQL tracking store
(SQLite), for runs of different sizes. The count must be one per run, whatever the run
holds. The experiment permission lookup is patched out: it is cached, and
``test_query_counts.py`` measures it.
"""

import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask
from mlflow.entities import Metric, Param, RunTag
from mlflow.store.tracking.sqlalchemy_store import SqlAlchemyStore
from sqlalchemy import event

from mlflow_oidc_auth.permissions import EDIT, NO_PERMISSIONS, READ

_IGNORED_PREFIXES = ("PRAGMA", "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE")
_app = Flask(__name__)


@pytest.fixture(scope="module")
def tracking_store(tmp_path_factory):
    """A real MLflow SQL tracking store on SQLite, shared by the module (migrations take seconds)."""
    root = tmp_path_factory.mktemp("tracking")
    store = SqlAlchemyStore(f"sqlite:///{root / 'mlflow.db'}", (root / "artifacts").as_uri())
    yield store
    store._dispose_engine()


@pytest.fixture
def tracking_statements(tracking_store):
    """Counts the application statements issued on the tracking store's engine."""
    issued = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        if not statement.lstrip().upper().startswith(_IGNORED_PREFIXES):
            issued.append(statement)

    event.listen(tracking_store.engine, "before_cursor_execute", _record)
    yield issued
    event.remove(tracking_store.engine, "before_cursor_execute", _record)


def _new_run(store, experiment_id, metric_keys):
    run_id = store.create_run(experiment_id, user_id="alice", start_time=int(time.time() * 1000), tags=[], run_name="r").info.run_id
    metrics = [Metric(f"logs/board/key_{i}", float(i), 0, 0) for i in range(metric_keys)]
    for start in range(0, len(metrics), 1000):
        store.log_batch(run_id, metrics=metrics[start : start + 1000], params=[], tags=[])
    store.log_batch(run_id, metrics=[], params=[Param(f"p{i}", "v") for i in range(20)], tags=[RunTag(f"t{i}", "v") for i in range(5)])
    return run_id


def _granting(permission_by_experiment):
    """An ``effective_experiment_permission`` stand-in: the given level per experiment id."""
    return lambda experiment_id, username: SimpleNamespace(permission=permission_by_experiment.get(experiment_id, NO_PERMISSIONS))


@pytest.fixture
def validators(tracking_store):
    """Every module under test resolves runs on the real store; one experiment is EDIT."""
    experiment_id = tracking_store.create_experiment(f"editable-{time.time_ns()}")
    permission = _granting({experiment_id: EDIT})
    targets = ("mlflow_oidc_auth.validators.run", "mlflow_oidc_auth.validators.stuff", "mlflow_oidc_auth.graphql.middleware")
    patches = [patch(f"{t}._get_tracking_store", return_value=tracking_store) for t in targets]
    patches += [patch(f"{t}.effective_experiment_permission", side_effect=permission) for t in targets]
    for p in patches:
        p.start()
    yield experiment_id
    for p in reversed(patches):
        p.stop()


class TestRunChecksAreConstantInRunSize:
    """The check must not scale with how many metrics, params or tags the run holds."""

    @pytest.mark.parametrize("metric_keys", [1, 100, 2000])
    def test_get_history_check_is_one_statement(self, tracking_store, tracking_statements, validators, metric_keys):
        """GET metrics/get-history, one call per key. Was 7 statements plus every latest metric."""
        from mlflow_oidc_auth.validators.run import validate_can_read_run

        run_id = _new_run(tracking_store, validators, metric_keys)
        with _app.test_request_context("/api/2.0/mlflow/metrics/get-history", query_string={"run_id": run_id, "metric_key": "logs/board/key_0"}):
            tracking_statements.clear()
            assert validate_can_read_run("alice") is True

        assert len(tracking_statements) == 1, tracking_statements

    @pytest.mark.parametrize("metric_keys", [1, 100, 2000])
    def test_log_batch_check_is_one_statement(self, tracking_store, tracking_statements, validators, metric_keys):
        """POST runs/log-batch, once per training step. Was 7 statements plus every latest metric."""
        from mlflow_oidc_auth.validators.run import validate_can_log_metrics

        run_id = _new_run(tracking_store, validators, metric_keys)
        body = {"run_id": run_id, "metrics": [{"key": "logs/board/key_0", "value": 1.0, "timestamp": 0, "step": 1}]}
        with _app.test_request_context("/api/2.0/mlflow/runs/log-batch", method="POST", json=body):
            tracking_statements.clear()
            assert validate_can_log_metrics("alice") is True

        assert len(tracking_statements) == 1, tracking_statements

    def test_bulk_history_checks_are_one_statement_per_run(self, tracking_store, tracking_statements, validators):
        """GetMetricHistoryBulk and its interval variant name up to 100 runs per call."""
        from mlflow_oidc_auth.validators.run import validate_can_read_metric_history_bulk_interval
        from mlflow_oidc_auth.validators.stuff import validate_can_read_metric_history_bulk

        run_ids = [_new_run(tracking_store, validators, metric_keys) for metric_keys in (1, 100, 2000)]

        tracking_statements.clear()
        assert validate_can_read_metric_history_bulk("alice", run_ids=run_ids) is True
        assert len(tracking_statements) == len(run_ids), tracking_statements

        with _app.test_request_context("/ajax-api/2.0/mlflow/metrics/get-history-bulk-interval", query_string=[("run_ids", r) for r in run_ids]):
            tracking_statements.clear()
            assert validate_can_read_metric_history_bulk_interval("alice") is True
        assert len(tracking_statements) == len(run_ids), tracking_statements

    def test_graphql_run_check_is_one_statement(self, tracking_store, tracking_statements, validators):
        from mlflow_oidc_auth.graphql.middleware import _can_read_run

        run_id = _new_run(tracking_store, validators, 2000)
        tracking_statements.clear()

        assert _can_read_run(run_id, "alice") is True
        assert len(tracking_statements) == 1, tracking_statements


class TestRunChecksResolveTheRightExperiment:
    """Real-DB authorization tests, not query-count tests.

    A mock-chain test hands the check whatever experiment id the mock returns, so a
    lookup that reads the wrong column or the wrong run would still pass. These run the
    lookup on the real store: a grant on one experiment must not open a run in another.
    """

    def test_a_run_in_an_unreadable_experiment_is_denied(self, tracking_store):
        from mlflow_oidc_auth.validators.run import validate_can_read_run, validate_can_update_run

        readable = tracking_store.create_experiment(f"readable-{time.time_ns()}")
        other = tracking_store.create_experiment(f"other-{time.time_ns()}")
        readable_run, other_run = _new_run(tracking_store, readable, 10), _new_run(tracking_store, other, 10)

        with (
            patch("mlflow_oidc_auth.validators.run._get_tracking_store", return_value=tracking_store),
            patch("mlflow_oidc_auth.validators.run.effective_experiment_permission", side_effect=_granting({readable: READ})),
        ):
            with _app.test_request_context("/api/2.0/mlflow/metrics/get-history", query_string={"run_id": other_run, "metric_key": "k"}):
                assert validate_can_read_run("alice") is False
            with _app.test_request_context("/api/2.0/mlflow/metrics/get-history", query_string={"run_id": readable_run, "metric_key": "k"}):
                assert validate_can_read_run("alice") is True
                assert validate_can_update_run("alice") is False, "READ must not allow a write"

    def test_a_bulk_request_is_denied_when_any_run_is_unreadable(self, tracking_store):
        from mlflow_oidc_auth.validators.stuff import validate_can_read_metric_history_bulk

        readable = tracking_store.create_experiment(f"bulk-readable-{time.time_ns()}")
        other = tracking_store.create_experiment(f"bulk-other-{time.time_ns()}")
        run_ids = [_new_run(tracking_store, readable, 1), _new_run(tracking_store, other, 1)]

        with (
            patch("mlflow_oidc_auth.validators.stuff._get_tracking_store", return_value=tracking_store),
            patch("mlflow_oidc_auth.validators.stuff.effective_experiment_permission", side_effect=_granting({readable: READ})),
        ):
            assert validate_can_read_metric_history_bulk("alice", run_ids=run_ids) is False
            assert validate_can_read_metric_history_bulk("alice", run_ids=run_ids[:1]) is True
