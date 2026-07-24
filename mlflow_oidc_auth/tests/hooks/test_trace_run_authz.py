"""Issue #259: authorization for the traces surface and runs/search (previously default-allow)."""

from unittest.mock import MagicMock, patch

from flask import Flask

from mlflow_oidc_auth.validators import trace as trace_v

_app = Flask(__name__)

_TP = "mlflow_oidc_auth.validators.trace"


def _perm(*, read=False, update=False, delete=False):
    p = MagicMock()
    p.permission.can_read = read
    p.permission.can_update = update
    p.permission.can_delete = delete
    return p


def _eff(mapping):
    """effective_experiment_permission side_effect: experiment_id -> PermissionResult mock."""

    def _fn(experiment_id, username):
        return mapping.get(experiment_id, _perm())  # unknown -> no permissions

    return _fn


class TestSearchTraceAuthz:
    def test_v2_get_query_readable_allowed(self):
        with _app.test_request_context("/api/2.0/mlflow/traces?experiment_ids=1", method="GET"):
            with patch(f"{_TP}.effective_experiment_permission", side_effect=_eff({"1": _perm(read=True)})):
                assert trace_v.validate_can_read_traces_from_experiment_ids("u") is True

    def test_v2_get_query_unreadable_denied(self):
        with _app.test_request_context("/api/2.0/mlflow/traces?experiment_ids=1&experiment_ids=2", method="GET"):
            with patch(f"{_TP}.effective_experiment_permission", side_effect=_eff({"1": _perm(read=True), "2": _perm(read=False)})):
                assert trace_v.validate_can_read_traces_from_experiment_ids("u") is False

    def test_v3_locations_resolved(self):
        body = {"locations": [{"mlflow_experiment": {"experiment_id": "9"}}]}
        with _app.test_request_context("/api/3.0/mlflow/traces/search", method="POST", json=body):
            with patch(f"{_TP}.effective_experiment_permission", side_effect=_eff({"9": _perm(read=True)})):
                assert trace_v.validate_can_read_traces_from_experiment_ids("u") is True

    def test_empty_scope_denied(self):
        """Regression: an unscoped trace search must DENY, not vacuously allow (would leak all traces)."""
        with _app.test_request_context("/api/3.0/mlflow/traces/search", method="POST", json={}):
            with patch(f"{_TP}.effective_experiment_permission", side_effect=_eff({})):
                assert trace_v.validate_can_read_traces_from_experiment_ids("u") is False

    def test_camelcase_location_cannot_hide_experiment(self):
        """Regression: MLflow proto-JSON accepts camelCase, so a location under 'mlflowExperiment'/
        'experimentId' must still be seen and checked — otherwise an attacker hides an unreadable
        experiment from the validator while MLflow still searches it (cross-tenant leak)."""
        body = {
            "locations": [
                {"mlflow_experiment": {"experiment_id": "MINE"}},
                {"mlflowExperiment": {"experimentId": "VICTIM"}},
            ]
        }
        with _app.test_request_context("/api/3.0/mlflow/traces/search", method="POST", json=body):
            with patch(f"{_TP}.effective_experiment_permission", side_effect=_eff({"MINE": _perm(read=True)})):
                assert trace_v.validate_can_read_traces_from_experiment_ids("u") is False

    def test_camelcase_body_experiment_ids_seen(self):
        with _app.test_request_context("/api/3.0/mlflow/traces/metrics", method="POST", json={"experimentIds": ["42"]}):
            with patch(f"{_TP}.effective_experiment_permission", side_effect=_eff({"42": _perm(read=False)})):
                assert trace_v.validate_can_read_traces_from_experiment_ids("u") is False


class TestSingleTraceAuthz:
    def test_path_trace_id_resolved_read(self):
        """Path-id route: proves the view_args fix (was raising MlflowException)."""
        with _app.test_request_context("/api/3.0/mlflow/traces/t-abc", method="GET"):
            from flask import request

            request.view_args = {"trace_id": "t-abc"}
            with (
                patch(f"{_TP}._get_tracking_store") as ts,
                patch(f"{_TP}.effective_experiment_permission", side_effect=_eff({"e1": _perm(read=True)})),
            ):
                ts.return_value.get_trace_info.return_value.experiment_id = "e1"
                assert trace_v.validate_can_read_trace("u") is True

    def test_path_trace_id_unreadable_denied(self):
        with _app.test_request_context("/api/2.0/mlflow/traces/r1/tags", method="PATCH", json={}):
            from flask import request

            request.view_args = {"request_id": "r1"}
            with (
                patch(f"{_TP}._get_tracking_store") as ts,
                patch(f"{_TP}.effective_experiment_permission", side_effect=_eff({"e1": _perm(read=True, update=False)})),
            ):
                ts.return_value.get_trace_info.return_value.experiment_id = "e1"
                assert trace_v.validate_can_update_trace("u") is False

    def test_no_trace_id_denied(self):
        with _app.test_request_context("/api/3.0/mlflow/traces/get", method="GET"):
            assert trace_v.validate_can_read_trace("u") is False


class TestBatchTraceAuthz:
    def test_mixed_readable_denied(self):
        with _app.test_request_context("/api/3.0/mlflow/traces/batchGetInfos", method="POST", json={"trace_ids": ["a", "b"]}):
            with (
                patch(f"{_TP}._get_tracking_store") as ts,
                patch(f"{_TP}.effective_experiment_permission", side_effect=_eff({"e1": _perm(read=True), "e2": _perm(read=False)})),
            ):
                ts.return_value.get_trace_info.side_effect = [MagicMock(experiment_id="e1"), MagicMock(experiment_id="e2")]
                assert trace_v.validate_can_read_traces_from_trace_ids("u") is False

    def test_all_readable_allowed(self):
        with _app.test_request_context("/api/3.0/mlflow/traces/batchGet?trace_ids=a&trace_ids=b", method="GET"):
            with (
                patch(f"{_TP}._get_tracking_store") as ts,
                patch(f"{_TP}.effective_experiment_permission", side_effect=_eff({"e1": _perm(read=True)})),
            ):
                ts.return_value.get_trace_info.return_value.experiment_id = "e1"
                assert trace_v.validate_can_read_traces_from_trace_ids("u") is True

    def test_empty_denied(self):
        with _app.test_request_context("/api/3.0/mlflow/traces/batchGetInfos", method="POST", json={}):
            assert trace_v.validate_can_read_traces_from_trace_ids("u") is False

    def test_unresolvable_trace_denied(self):
        with _app.test_request_context("/api/3.0/mlflow/traces/batchGetInfos", method="POST", json={"trace_ids": ["ghost"]}):
            with patch(f"{_TP}._get_tracking_store") as ts:
                ts.return_value.get_trace_info.side_effect = Exception("not found")
                assert trace_v.validate_can_read_traces_from_trace_ids("u") is False


class TestDeleteTraceAuthz:
    def test_delete_requires_delete_on_experiment(self):
        with _app.test_request_context("/api/2.0/mlflow/traces/delete-traces", method="POST", json={"experiment_id": "e1"}):
            with patch(f"{_TP}.effective_experiment_permission", side_effect=_eff({"e1": _perm(delete=False)})):
                assert trace_v.validate_can_delete_traces_from_experiment_id("u") is False
            with patch(f"{_TP}.effective_experiment_permission", side_effect=_eff({"e1": _perm(delete=True)})):
                assert trace_v.validate_can_delete_traces_from_experiment_id("u") is True


class TestBindings:
    """Structural guards on the before_request dispatch (#259)."""

    def test_no_imported_validator_is_left_unbound(self):
        """Every validate_can_* imported into the hook must be bound to some handler dict — the
        6 trace validators were previously imported-but-unbound (silent no-ops)."""
        import mlflow_oidc_auth.hooks.before_request as b

        bound = set()
        for d in (
            b.BEFORE_REQUEST_HANDLERS,
            b.BEFORE_REQUEST_VALIDATORS,
            b.PARAMETERIZED_BEFORE_REQUEST_VALIDATORS,
            b.WORKSPACE_BEFORE_REQUEST_HANDLERS,
            b.WORKSPACE_BEFORE_REQUEST_VALIDATORS,
            b.LOGGED_MODEL_BEFORE_REQUEST_HANDLERS,
            b.LOGGED_MODEL_BEFORE_REQUEST_VALIDATORS,
        ):
            for v in d.values():
                bound.add(getattr(v, "__name__", v))
        # Trace + run-search validators must now be bound (the #259 fix).
        for name in (
            "validate_can_read_traces_from_experiment_ids",
            "validate_can_read_traces_from_trace_ids",
            "validate_can_read_trace",
            "validate_can_update_trace",
            "validate_can_delete_traces_from_experiment_id",
            "validate_can_update_trace_from_run_id",
        ):
            assert name in bound, f"{name} is imported but not bound to any route"

    def test_trace_metrics_and_correlation_are_bound(self):
        """These v3 trace reads take experiment_ids and were initially left default-allow (leak)."""
        from unittest.mock import MagicMock

        from mlflow_oidc_auth.hooks.before_request import _find_validator

        for path in (
            "/api/3.0/mlflow/traces/metrics",
            "/api/3.0/mlflow/traces/calculate-filter-correlation",
        ):
            v = _find_validator(MagicMock(path=path, method="POST"))
            assert getattr(v, "__name__", None) == "validate_can_read_traces_from_experiment_ids", path

    def test_search_endpoints_not_before_denied(self):
        """Redundancy guard: registered-model/model-version/logged-model searches must stay
        unbound in before_request (after_request filters them gracefully); a before-deny would
        403 a whole search that touches one unreadable item."""
        from mlflow_oidc_auth.hooks.before_request import BEFORE_REQUEST_VALIDATORS

        keys = {k[0] for k in BEFORE_REQUEST_VALIDATORS}
        for path in (
            "/api/2.0/mlflow/registered-models/search",
            "/api/2.0/mlflow/model-versions/search",
            "/api/2.0/mlflow/logged-models/search",
        ):
            assert path not in keys, f"{path} should not be before_request-bound (#259 redundancy)"

    def test_graphql_not_before_bound(self):
        from mlflow_oidc_auth.hooks.before_request import BEFORE_REQUEST_VALIDATORS

        assert not any("graphql" in k[0] for k in BEFORE_REQUEST_VALIDATORS)
