"""Run, trace and webhook mutations MLflow serves must reach a validator (issue #291).

A ``None`` validator is not a deny: ``before_request_hook`` falls through and MLflow serves
the request. These routes had no entry in the validator maps, so any authenticated user
could mutate another tenant's runs and traces, or register a webhook that receives every
tenant's registry events.

Driven end to end: MLflow's REAL Flask routing table, the REAL ``before_request_hook`` and
a REAL permission store. Only the MLflow tracking store is faked, to place runs and traces
in experiments. ``DEFAULT_MLFLOW_PERMISSION`` is MANAGE, so every denial below comes from an
explicit grant being consulted, never from a restrictive default.
"""

from types import SimpleNamespace

import pytest
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST
from mlflow.server import app as mlflow_app

from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext

VICTIM_EXPERIMENT = "1"
OWN_EXPERIMENT = "2"
EDITOR = "editor@example.com"  # EDIT on the victim experiment
READER = "reader@example.com"  # READ only — not enough to write
OUTSIDER = "outsider@example.com"  # NO_PERMISSIONS on the victim, EDIT on their own
ADMIN = "admin@example.com"

PREFIXES = ("/api", "/ajax-api")


class _FakeTrackingStore:
    """Runs and existing traces live in the victim experiment; ``new-*`` traces do not exist."""

    def get_run(self, run_id):
        return SimpleNamespace(info=SimpleNamespace(experiment_id=VICTIM_EXPERIMENT, run_id=run_id))

    def get_trace_info(self, trace_id):
        if trace_id.startswith("new-"):
            raise MlflowException(f"Trace '{trace_id}' not found", RESOURCE_DOES_NOT_EXIST)
        return SimpleNamespace(experiment_id=VICTIM_EXPERIMENT, trace_id=trace_id)


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.config import config
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    monkeypatch.setattr("mlflow_oidc_auth.store.store", s, raising=False)
    monkeypatch.setattr("mlflow_oidc_auth.utils.permissions.store", s, raising=False)
    monkeypatch.setattr("mlflow_oidc_auth.hooks.before_request.store", s, raising=False)
    monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE")
    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
    monkeypatch.setattr("mlflow.server.handlers._tracking_store", _FakeTrackingStore())

    for user in (EDITOR, READER, OUTSIDER, ADMIN):
        s.create_user(user, "pw", user, is_admin=user == ADMIN)
    s.create_experiment_permission(VICTIM_EXPERIMENT, EDITOR, "EDIT")
    s.create_experiment_permission(VICTIM_EXPERIMENT, READER, "READ")
    s.create_experiment_permission(VICTIM_EXPERIMENT, OUTSIDER, "NO_PERMISSIONS")
    s.create_experiment_permission(OWN_EXPERIMENT, OUTSIDER, "EDIT")

    flush_permission_cache()
    yield s
    flush_permission_cache()


def _hook(path, method, username, *, body=None, is_admin=False):
    """Run the real before_request_hook for one request through MLflow's real routing."""
    from flask import request

    from mlflow_oidc_auth.hooks.before_request import before_request_hook

    environ = {AUTH_CONTEXT_KEY: AuthContext(username=username, is_admin=is_admin)}
    kwargs = {"json": body} if body is not None else {}
    with mlflow_app.test_request_context(path, method=method, environ_base=environ, **kwargs):
        assert request.url_rule is not None, f"precondition: MLflow must route {method} {path}"
        return before_request_hook()


def _denied(resp):
    return resp is not None and resp.status_code == 403


# ---------------------------------------------------------------------------
# Run mutations: LogInputs / LogOutputs
# ---------------------------------------------------------------------------

RUN_MUTATIONS = [
    pytest.param("/2.0/mlflow/runs/log-inputs", {"run_id": "r1", "datasets": []}, id="log-inputs"),
    pytest.param("/2.0/mlflow/runs/outputs", {"run_id": "r1", "models": [{"model_id": "m-1", "step": 0}]}, id="log-outputs"),
]


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("suffix, body", RUN_MUTATIONS)
def test_run_mutation_requires_update_on_the_run(prefix, suffix, body):
    path = prefix + suffix
    assert _denied(_hook(path, "POST", OUTSIDER, body=body)), f"{path}: outsider mutated another tenant's run"
    assert _denied(_hook(path, "POST", READER, body=body)), f"{path}: READ is not enough to write a run"
    assert _hook(path, "POST", EDITOR, body=body) is None, f"{path}: denied to a user holding EDIT"


# ---------------------------------------------------------------------------
# Trace writes: StartTrace (v2), StartTraceV3, EndTrace (v2)
# ---------------------------------------------------------------------------


def _v3_body(experiment_id, trace_id):
    return {
        "trace": {
            "trace_info": {
                "trace_id": trace_id,
                "trace_location": {"type": "MLFLOW_EXPERIMENT", "mlflow_experiment": {"experiment_id": experiment_id}},
                "request_time": "2026-01-01T00:00:00Z",
                "state": "OK",
            }
        }
    }


@pytest.mark.parametrize("prefix", PREFIXES)
def test_start_trace_v2_requires_update_on_the_experiment(prefix):
    path = f"{prefix}/2.0/mlflow/traces"
    body = {"experiment_id": VICTIM_EXPERIMENT, "timestamp_ms": 1}
    assert _denied(_hook(path, "POST", OUTSIDER, body=body))
    assert _denied(_hook(path, "POST", READER, body=body))
    assert _hook(path, "POST", EDITOR, body=body) is None


@pytest.mark.parametrize("prefix", PREFIXES)
def test_start_trace_v2_without_an_experiment_is_denied(prefix):
    assert _denied(_hook(f"{prefix}/2.0/mlflow/traces", "POST", EDITOR, body={"timestamp_ms": 1}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_start_trace_v3_requires_update_on_the_destination(prefix):
    path = f"{prefix}/3.0/mlflow/traces"
    body = _v3_body(VICTIM_EXPERIMENT, "new-trace")
    assert _denied(_hook(path, "POST", OUTSIDER, body=body))
    assert _denied(_hook(path, "POST", READER, body=body))
    assert _hook(path, "POST", EDITOR, body=body) is None


@pytest.mark.parametrize("prefix", PREFIXES)
def test_start_trace_v3_into_own_experiment_is_allowed(prefix):
    assert _hook(f"{prefix}/3.0/mlflow/traces", "POST", OUTSIDER, body=_v3_body(OWN_EXPERIMENT, "new-trace")) is None


@pytest.mark.parametrize("prefix", PREFIXES)
def test_start_trace_v3_cannot_merge_into_another_tenants_existing_trace(prefix):
    """MLflow merges a StartTraceV3 whose trace_id already exists into that trace.

    The outsider may write their OWN experiment, so authorizing only the destination would
    let them write tags, assessments and metadata into the victim's trace by naming its id.
    """
    body = _v3_body(OWN_EXPERIMENT, "tr-victim")
    assert _denied(_hook(f"{prefix}/3.0/mlflow/traces", "POST", OUTSIDER, body=body))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_start_trace_v3_camel_case_body_is_honoured(prefix):
    body = {"trace": {"traceInfo": {"traceId": "new-x", "traceLocation": {"mlflowExperiment": {"experimentId": VICTIM_EXPERIMENT}}}}}
    assert _denied(_hook(f"{prefix}/3.0/mlflow/traces", "POST", OUTSIDER, body=body))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize(
    "body",
    [
        pytest.param({}, id="empty"),
        pytest.param({"trace": {"trace_info": {"trace_id": "new-x"}}}, id="no-location"),
        pytest.param({"trace": {"trace_info": {"trace_location": {"type": "INFERENCE_TABLE"}}}}, id="non-experiment-location"),
    ],
)
def test_start_trace_v3_with_no_experiment_is_denied(prefix, body):
    assert _denied(_hook(f"{prefix}/3.0/mlflow/traces", "POST", EDITOR, body=body))


def test_start_trace_v3_lookup_failure_other_than_not_found_denies(monkeypatch):
    """Only a definite 'does not exist' means a new trace; anything else fails closed."""

    class _Broken(_FakeTrackingStore):
        def get_trace_info(self, trace_id):
            raise RuntimeError("store unavailable")

    monkeypatch.setattr("mlflow.server.handlers._tracking_store", _Broken())
    assert _denied(_hook("/api/3.0/mlflow/traces", "POST", EDITOR, body=_v3_body(VICTIM_EXPERIMENT, "anything")))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_end_trace_v2_requires_update_on_the_trace(prefix):
    path = f"{prefix}/2.0/mlflow/traces/tr-victim"
    body = {"timestamp_ms": 2, "status": "OK"}
    assert _denied(_hook(path, "PATCH", OUTSIDER, body=body))
    assert _denied(_hook(path, "PATCH", READER, body=body))
    assert _hook(path, "PATCH", EDITOR, body=body) is None


# ---------------------------------------------------------------------------
# MLflow's native registry webhooks: admin-only
# ---------------------------------------------------------------------------


def _webhook_requests():
    """Every (concrete path, method) MLflow serves for its webhook API, HEAD included."""
    import re

    from mlflow_oidc_auth.hooks.before_request import MLFLOW_WEBHOOK_ROUTE_MARKER

    pairs = []
    for rule in mlflow_app.url_map.iter_rules():
        if MLFLOW_WEBHOOK_ROUTE_MARKER not in str(rule):
            continue
        path = re.sub(r"<[^>]+>", "wh-1", str(rule))
        for method in sorted((rule.methods or set()) - {"OPTIONS"}):
            pairs.append((path, method))
    return pairs


def test_mlflow_registers_the_webhook_family_under_both_prefixes():
    """Pin the surface: 6 route/method pairs per prefix (create/list/get/update/delete/test)."""
    pairs = {(p, m) for p, m in _webhook_requests() if m != "HEAD"}
    assert len(pairs) == 12, sorted(pairs)
    assert {p.split("/2.0/")[0] for p, _m in pairs} == set(PREFIXES)


@pytest.mark.parametrize("path, method", _webhook_requests())
def test_webhook_route_denies_non_admins(path, method):
    body = {"name": "x", "url": "https://example.com/hook", "events": []} if method in ("POST", "PATCH") else None
    assert _denied(_hook(path, method, EDITOR, body=body)), f"{method} {path} served to a non-admin"


@pytest.mark.parametrize("path, method", _webhook_requests())
def test_webhook_route_allows_admins(path, method):
    body = {"name": "x", "url": "https://example.com/hook", "events": []} if method in ("POST", "PATCH") else None
    assert _hook(path, method, ADMIN, body=body, is_admin=True) is None, f"{method} {path} denied to an admin"


# ---------------------------------------------------------------------------
# StartTraceV3 merge-on-conflict: re-homing and assessment upserts
# ---------------------------------------------------------------------------


def test_start_trace_v3_rehoming_an_existing_trace_requires_delete_on_its_experiment(permission_store):
    """The merge moves an existing trace into the destination: a delete on its source.

    The editor holds EDIT (UPDATE, not DELETE) on the victim experiment and on their own.
    Naming the victim trace with their own experiment as destination must be refused.
    """
    permission_store.create_experiment_permission(OWN_EXPERIMENT, EDITOR, "EDIT")
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    flush_permission_cache()
    assert _denied(_hook("/api/3.0/mlflow/traces", "POST", EDITOR, body=_v3_body(OWN_EXPERIMENT, "tr-victim")))
    # Same experiment: no re-homing, UPDATE is enough (the log_spans / start_trace race).
    assert _hook("/api/3.0/mlflow/traces", "POST", EDITOR, body=_v3_body(VICTIM_EXPERIMENT, "tr-victim")) is None


def _with_assessments(body, assessments):
    body["trace"]["trace_info"]["assessments"] = assessments
    return body


def test_start_trace_v3_cannot_upsert_an_assessment_by_id_into_an_existing_trace():
    """The merge upserts assessments by assessment_id alone, whose owner cannot be resolved."""
    body = _with_assessments(_v3_body(VICTIM_EXPERIMENT, "tr-victim"), [{"assessment_id": "a-other", "feedback": {"value": 1}}])
    assert _denied(_hook("/api/3.0/mlflow/traces", "POST", EDITOR, body=body))


def test_start_trace_v3_assessment_naming_another_trace_is_denied():
    body = _with_assessments(_v3_body(VICTIM_EXPERIMENT, "new-t"), [{"trace_id": "tr-other", "feedback": {"value": 1}}])
    assert _denied(_hook("/api/3.0/mlflow/traces", "POST", EDITOR, body=body))


def test_start_trace_v3_new_trace_with_its_own_assessments_is_allowed():
    """Exporting / copying a trace with assessments into a fresh id stays allowed."""
    body = _with_assessments(_v3_body(VICTIM_EXPERIMENT, "new-t"), [{"assessment_id": "a-1", "trace_id": "new-t", "feedback": {"value": 1}}])
    assert _hook("/api/3.0/mlflow/traces", "POST", EDITOR, body=body) is None


# ---------------------------------------------------------------------------
# StartTraceV3 id shapes: absent ids and non-scalar ids must be refused, never 500
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("trace_id", [None, ""], ids=["absent", "empty"])
def test_start_trace_v3_without_a_trace_id_is_denied(trace_id):
    """MLflow stores an absent trace_id as "", so a second id-less start merges into the first."""
    body = _v3_body(OWN_EXPERIMENT, "placeholder")
    if trace_id is None:
        del body["trace"]["trace_info"]["trace_id"]
    else:
        body["trace"]["trace_info"]["trace_id"] = trace_id
    assert _denied(_hook("/api/3.0/mlflow/traces", "POST", OUTSIDER, body=body))


_NON_SCALARS = [pytest.param(["x"], id="list"), pytest.param({"a": "b"}, id="dict")]


@pytest.mark.parametrize("value", _NON_SCALARS)
def test_start_trace_v3_non_scalar_trace_id_is_refused(value):
    body = _v3_body(OWN_EXPERIMENT, "new-t")
    body["trace"]["trace_info"]["trace_id"] = value
    assert _denied(_hook("/api/3.0/mlflow/traces", "POST", OUTSIDER, body=body))


@pytest.mark.parametrize("value", _NON_SCALARS)
def test_start_trace_v3_non_scalar_experiment_id_is_refused(value):
    assert _denied(_hook("/api/3.0/mlflow/traces", "POST", OUTSIDER, body=_v3_body(value, "new-t")))


@pytest.mark.parametrize("field", ["trace_id", "assessment_id"])
@pytest.mark.parametrize("value", _NON_SCALARS)
def test_start_trace_v3_non_scalar_assessment_ids_are_refused(field, value):
    body = _with_assessments(_v3_body(OWN_EXPERIMENT, "new-t"), [{field: value, "feedback": {"value": 1}}])
    assert _denied(_hook("/api/3.0/mlflow/traces", "POST", OUTSIDER, body=body))


def test_start_trace_v3_looks_each_trace_up_once(monkeypatch):
    """Single-word fields ("trace", "assessments") share both spellings; read them once."""
    calls = []

    class _Counting(_FakeTrackingStore):
        def get_trace_info(self, trace_id):
            calls.append(trace_id)
            return super().get_trace_info(trace_id)

    monkeypatch.setattr("mlflow.server.handlers._tracking_store", _Counting())
    body = _with_assessments(_v3_body(VICTIM_EXPERIMENT, "new-t"), [{"trace_id": "new-t", "feedback": {"value": 1}}])
    assert _hook("/api/3.0/mlflow/traces", "POST", EDITOR, body=body) is None
    assert calls == ["new-t"]


def test_field_values_reads_a_shared_spelling_once():
    from mlflow_oidc_auth.validators.trace import _field_values

    assert _field_values({"trace": {"a": 1}}, "trace", "trace") == [{"a": 1}]
    assert _field_values({"trace_id": "a", "traceId": "b"}, "trace_id", "traceId") == ["a", "b"]
