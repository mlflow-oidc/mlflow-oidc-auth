"""Query-count regression tests for logged-model permission checks.

A logged model inherits its permission from its experiment, so a check on it needs one value:
the model's experiment id. The checks read it from ``get_logged_model``, which on MLflow's SQL
store also loads every tag, param and metric data point of the model: 4 statements, and an
entity for every row. A model that collects metrics at every training step made each check
slower as the training went on, including the check on every ``log-batch`` that names it.

These tests count the statements a check issues on a real MLflow SQL tracking store (SQLite),
for models of different sizes. The count must be one per model, whatever the model holds. The
experiment permission lookup is patched out: it is cached, and ``test_query_counts.py``
measures it.
"""

import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask, request
from mlflow.entities import Metric
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode
from mlflow.store.tracking.sqlalchemy_store import SqlAlchemyStore
from sqlalchemy import event

from mlflow_oidc_auth.permissions import EDIT, NO_PERMISSIONS, READ

_IGNORED_PREFIXES = ("PRAGMA", "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE")
_app = Flask(__name__)
_CHECKED_MODULES = ("mlflow_oidc_auth.validators.registered_model", "mlflow_oidc_auth.validators._referenced")


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


def _new_model(store, experiment_id, metric_points):
    run_id = store.create_run(experiment_id, user_id="alice", start_time=int(time.time() * 1000), tags=[], run_name="r").info.run_id
    model_id = store.create_logged_model(experiment_id=experiment_id, name="m", source_run_id=run_id).model_id
    metrics = [Metric(f"eval/key_{i % 20}", float(i), 0, i // 20, model_id=model_id) for i in range(metric_points)]
    for start in range(0, len(metrics), 1000):
        store.log_batch(run_id, metrics=metrics[start : start + 1000], params=[], tags=[])
    return run_id, model_id


def _granting(permission_by_experiment):
    """An ``effective_experiment_permission`` stand-in: the given level per experiment id."""
    return lambda experiment_id, username: SimpleNamespace(permission=permission_by_experiment.get(experiment_id, NO_PERMISSIONS))


def _checks_on(tracking_store, permission_by_experiment):
    """Patch both modules under test to resolve models on the real store with these grants."""
    patches = [patch(f"{m}._get_tracking_store", return_value=tracking_store) for m in _CHECKED_MODULES]
    patches += [patch(f"{m}.effective_experiment_permission", side_effect=_granting(permission_by_experiment)) for m in _CHECKED_MODULES]
    return patches


@pytest.fixture
def editable(tracking_store):
    """An experiment the caller holds EDIT on, with every module under test on the real store."""
    experiment_id = tracking_store.create_experiment(f"editable-{time.time_ns()}")
    patches = _checks_on(tracking_store, {experiment_id: EDIT})
    for p in patches:
        p.start()
    yield experiment_id
    for p in reversed(patches):
        p.stop()


def _on_model_route(model_id, method="GET", suffix=""):
    """A request context for a logged-model route, with ``model_id`` as the path parameter."""
    ctx = _app.test_request_context(f"/api/2.0/mlflow/logged-models/{model_id}{suffix}", method=method, json={} if method != "GET" else None)
    ctx.push()
    request.view_args = {"model_id": model_id}
    return ctx


class TestLoggedModelChecksAreConstantInModelSize:
    """The check must not scale with how many metric points, params or tags the model holds."""

    @pytest.mark.parametrize("metric_points", [1, 100, 2000])
    def test_logged_model_route_checks_are_one_statement(self, tracking_store, tracking_statements, editable, metric_points):
        """GET and PATCH on a logged model. Was 4 statements plus every metric point of the model."""
        from mlflow_oidc_auth.validators.registered_model import validate_can_read_logged_model, validate_can_update_logged_model

        _, model_id = _new_model(tracking_store, editable, metric_points)
        for validator, method, suffix in ((validate_can_read_logged_model, "GET", ""), (validate_can_update_logged_model, "PATCH", "/tags")):
            ctx = _on_model_route(model_id, method, suffix)
            try:
                tracking_statements.clear()
                assert validator("alice") is True
            finally:
                ctx.pop()
            assert len(tracking_statements) == 1, (validator.__name__, tracking_statements)

    @pytest.mark.parametrize("metric_points", [1, 100, 2000])
    def test_log_batch_check_is_one_statement_per_named_model(self, tracking_store, tracking_statements, editable, metric_points):
        """POST runs/log-batch whose metrics name logged models: one statement per distinct model.

        The run half of the check is patched out; it is not what this test measures.
        """
        from mlflow_oidc_auth.validators.run import validate_can_log_metrics

        run_id, first = _new_model(tracking_store, editable, metric_points)
        _, second = _new_model(tracking_store, editable, metric_points)
        metrics = [{"key": "loss", "value": 1.0, "timestamp": 0, "step": s, "model_id": m} for s, m in enumerate((first, second, first))]
        with (
            patch("mlflow_oidc_auth.validators.run.validate_can_update_run", return_value=True),
            _app.test_request_context("/api/2.0/mlflow/runs/log-batch", method="POST", json={"run_id": run_id, "metrics": metrics}),
        ):
            tracking_statements.clear()
            assert validate_can_log_metrics("alice") is True

        assert len(tracking_statements) == 2, tracking_statements


class TestLoggedModelChecksResolveTheRightExperiment:
    """Real-DB authorization tests, not query-count tests.

    A mock-chain test hands the check whatever experiment id the mock returns, so a lookup
    that reads the wrong column or the wrong model would still pass. These run the lookup on
    the real store: a grant on one experiment must not open a model in another.
    """

    @pytest.fixture
    def two_experiments(self, tracking_store):
        readable = tracking_store.create_experiment(f"readable-{time.time_ns()}")
        other = tracking_store.create_experiment(f"other-{time.time_ns()}")
        patches = _checks_on(tracking_store, {readable: READ})
        for p in patches:
            p.start()
        yield readable, other
        for p in reversed(patches):
            p.stop()

    def test_a_model_in_an_unreadable_experiment_is_denied(self, tracking_store, two_experiments):
        from mlflow_oidc_auth.validators.registered_model import validate_can_read_logged_model, validate_can_update_logged_model

        readable, other = two_experiments
        _, readable_model = _new_model(tracking_store, readable, 10)
        _, other_model = _new_model(tracking_store, other, 10)

        ctx = _on_model_route(other_model)
        try:
            assert validate_can_read_logged_model("alice") is False
        finally:
            ctx.pop()
        ctx = _on_model_route(readable_model)
        try:
            assert validate_can_read_logged_model("alice") is True
            assert validate_can_update_logged_model("alice") is False, "READ must not allow a write"
        finally:
            ctx.pop()

    def test_log_batch_naming_a_model_in_an_unwritable_experiment_is_denied(self, tracking_store, two_experiments):
        from mlflow_oidc_auth.validators.run import validate_can_log_metrics

        readable, other = two_experiments
        run_id, _ = _new_model(tracking_store, readable, 1)
        _, other_model = _new_model(tracking_store, other, 1)
        body = {"run_id": run_id, "metrics": [{"key": "loss", "value": 1.0, "timestamp": 0, "step": 0, "model_id": other_model}]}
        with (
            patch("mlflow_oidc_auth.validators.run.validate_can_update_run", return_value=True),
            _app.test_request_context("/api/2.0/mlflow/runs/log-batch", method="POST", json=body),
        ):
            assert validate_can_log_metrics("alice") is False

    def test_a_deleted_model_is_not_resolved(self, tracking_store, two_experiments):
        """A deleted model stays hidden: a reference to it is denied, a route on it is not found."""
        from mlflow_oidc_auth.validators._referenced import referenced_logged_model_permission
        from mlflow_oidc_auth.validators.registered_model import validate_can_read_logged_model

        readable, _ = two_experiments
        _, model_id = _new_model(tracking_store, readable, 1)
        tracking_store.delete_logged_model(model_id)

        assert referenced_logged_model_permission(model_id, "alice") is NO_PERMISSIONS
        ctx = _on_model_route(model_id)
        try:
            with pytest.raises(MlflowException) as raised:
                validate_can_read_logged_model("alice")
        finally:
            ctx.pop()
        assert raised.value.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST)
