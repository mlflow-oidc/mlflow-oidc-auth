"""HEAD is authorized exactly like its GET twin, end to end (issue #286).

werkzeug auto-registers HEAD on every GET rule and dispatches it to the GET view,
stripping the body but keeping ``Content-Length``. Every validator in the plugin is keyed
on "GET", so a lookup on the literal method found nothing for HEAD, and a missing validator
is not a deny: the request fell through, and the response headers became an existence and
exact-byte-size oracle over any tenant's run artifacts, model-version artifacts, trace
artifacts and metric history.

These tests drive the REAL ``before_request_hook`` against MLflow's REAL Flask routing table
(so ``view_args`` and route matching are production's) and a REAL permission store. Only the
MLflow tracking store is faked, to map run / trace / logged-model ids onto an experiment.

Grants are deliberately explicit in both directions — the outsider holds NO_PERMISSIONS, the
reader holds READ — with ``DEFAULT_MLFLOW_PERMISSION`` set to MANAGE. A denial can therefore
only come from the grant being consulted, never from a restrictive default.
"""

from types import SimpleNamespace

import pytest
from mlflow.server import app as mlflow_app

from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.hooks.http_method import authorization_method

READER = "reader@example.com"
OUTSIDER = "outsider@example.com"
EXPERIMENT_ID = "1"
MODEL_NAME = "victim-model"


class _FakeTrackingStore:
    """Resolves every run / trace / logged model onto the one victim experiment."""

    def get_run(self, run_id):
        return SimpleNamespace(info=SimpleNamespace(experiment_id=EXPERIMENT_ID, run_id=run_id))

    def get_trace_info(self, trace_id):
        return SimpleNamespace(experiment_id=EXPERIMENT_ID, trace_id=trace_id)

    def get_logged_model(self, model_id):
        return SimpleNamespace(experiment_id=EXPERIMENT_ID, model_id=model_id)


@pytest.fixture
def permission_store(tmp_path, monkeypatch):
    """A real SqlAlchemyStore with an explicit READ grant and an explicit NO_PERMISSIONS grant."""
    from mlflow_oidc_auth.config import config
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    # utils.permissions binds the singleton by name at import time, so the module attribute
    # alone is not enough — patch every reader of it this path touches.
    monkeypatch.setattr("mlflow_oidc_auth.store.store", s, raising=False)
    monkeypatch.setattr("mlflow_oidc_auth.utils.permissions.store", s, raising=False)
    monkeypatch.setattr("mlflow_oidc_auth.hooks.before_request.store", s, raising=False)
    monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE")
    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
    monkeypatch.setattr("mlflow.server.handlers._tracking_store", _FakeTrackingStore())

    for user, level in ((READER, "READ"), (OUTSIDER, "NO_PERMISSIONS")):
        s.create_user(user, "pw", user)
        s.create_experiment_permission(EXPERIMENT_ID, user, level)
        s.create_registered_model_permission(MODEL_NAME, user, level)

    flush_permission_cache()
    yield s
    flush_permission_cache()


def _hook(path, method, username, query=None):
    """Run the real before_request_hook for one request through MLflow's real routing."""
    from mlflow_oidc_auth.hooks.before_request import before_request_hook

    environ = {AUTH_CONTEXT_KEY: AuthContext(username=username, is_admin=False)}
    with mlflow_app.test_request_context(path, method=method, query_string=query or {}, environ_base=environ):
        from flask import request

        assert request.url_rule is not None, f"precondition: MLflow must route {method} {path}"
        return before_request_hook()


# (path, query) for every non-proto route #286 names, plus the -interval twin.
NON_PROTO_READS = [
    pytest.param("/get-artifact", {"run_uuid": "r1", "path": "big.txt"}, id="get-artifact"),
    pytest.param("/model-versions/get-artifact", {"name": MODEL_NAME, "version": "1", "path": "model.pkl"}, id="model-versions-get-artifact"),
    pytest.param("/ajax-api/2.0/mlflow/get-trace-artifact", {"request_id": "tr-1"}, id="get-trace-artifact"),
    pytest.param("/ajax-api/2.0/mlflow/metrics/get-history-bulk", {"run_id": "r1", "metric_key": "loss"}, id="get-history-bulk"),
    pytest.param(
        "/ajax-api/2.0/mlflow/metrics/get-history-bulk-interval",
        {"run_ids": "r1", "metric_key": "loss"},
        id="get-history-bulk-interval",
    ),
]


def test_head_folds_onto_get_and_nothing_else():
    assert authorization_method("HEAD") == "GET"
    for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
        assert authorization_method(method) == method


@pytest.mark.parametrize("path, query", NON_PROTO_READS)
def test_head_is_denied_without_read(permission_store, path, query):
    """The oracle itself: HEAD must receive the same 403 as its GET twin."""
    for method in ("GET", "HEAD"):
        resp = _hook(path, method, OUTSIDER, query)
        assert resp is not None and resp.status_code == 403, f"{method} {path} served to a user holding NO_PERMISSIONS"


@pytest.mark.parametrize("path, query", NON_PROTO_READS)
def test_head_is_allowed_with_read(permission_store, path, query):
    """Closing the hole must not deny the rightful reader — HEAD decides like GET."""
    for method in ("GET", "HEAD"):
        assert _hook(path, method, READER, query) is None, f"{method} {path} denied to a user holding READ"


def test_head_on_a_get_gated_proto_route(permission_store):
    """GET /logged-models/<model_id> is a proto route gated for GET only (GetLoggedModel)."""
    path = "/api/2.0/mlflow/logged-models/m-123"
    for method in ("GET", "HEAD"):
        denied = _hook(path, method, OUTSIDER)
        assert denied is not None and denied.status_code == 403, f"{method} {path} served to a user holding NO_PERMISSIONS"
        assert _hook(path, method, READER) is None, f"{method} {path} denied to a user holding READ"


def test_head_on_a_query_string_proto_route_never_falls_through(permission_store):
    """A HEAD on a query-string proto GET route must reach a decision, never be served unchecked.

    MLflow proto-parses a HEAD from the (empty) body rather than the query string, so the
    request is refused for everyone; what matters here is that the outsider is refused.
    """
    resp = _hook("/api/2.0/mlflow/runs/get", "HEAD", OUTSIDER, {"run_id": "r1"})
    assert resp is not None and resp.status_code in (400, 403)
