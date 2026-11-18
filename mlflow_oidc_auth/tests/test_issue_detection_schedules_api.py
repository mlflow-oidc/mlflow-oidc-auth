"""The issue detection schedules admin API: real ``AuthMiddleware``, real store, real router.

* every endpoint is admin-only: a signed-in non-admin gets 403, an anonymous caller 401;
* the list shows each stored schedule with its recorded writer and what the guard makes of it;
* the check pauses what the guard would pause and says why.
"""

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mlflow.store.entities.paged_list import PagedList
from starlette.middleware.sessions import SessionMiddleware

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth import issue_detection_guard as guard
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.exceptions import register_exception_handlers
from mlflow_oidc_auth.middleware import AuthMiddleware
from mlflow_oidc_auth.routers.issue_detection_schedules import issue_detection_schedules_router
from mlflow_oidc_auth.tests.scim.conftest import basic
from mlflow_oidc_auth.tests.token_helpers import set_known_token

ADMIN = "admin@example.com"
ALICE = "alice@example.com"
ADMIN_PASSWORD = "schedules-api-admin"  # not a credential: only ever seeded into a tmp_path database
ALICE_PASSWORD = "schedules-api-alice"  # likewise
SCHEDULES = "/api/3.0/mlflow/issue-detection-schedules"
TAG = "mlflow.issueDetection.schedule"

pytestmark = pytest.mark.skipif(not guard.scheduler_available(), reason="MLflow's issue detection schedule arrived in 3.18")


def _schedule(model):
    return json.dumps({"version": 1, "cadence": "daily", "paused": False, "model": model})


class _TrackingStore:
    def __init__(self):
        self.tags = {"1": {TAG: _schedule({"provider": "openai", "model": "m", "secretId": "sec-1"})}, "2": {TAG: _schedule({"endpointName": "team"})}}

    def get_experiment(self, experiment_id):
        return SimpleNamespace(experiment_id=experiment_id, name=f"experiment-{experiment_id}", workspace=None, tags=dict(self.tags[experiment_id]))

    def search_experiments(self, **_):
        return PagedList([self.get_experiment(e) for e in sorted(self.tags)], None)

    def set_experiment_tag(self, experiment_id, tag):
        self.tags[experiment_id][tag.key] = tag.value

    def get_secret_info(self, secret_id=None, **_):
        return SimpleNamespace(secret_name="team-key")


@pytest.fixture
def tracking(monkeypatch):
    t = _TrackingStore()
    monkeypatch.setattr("mlflow.server.handlers._tracking_store", t)
    return t


@pytest.fixture
def store(tmp_path, monkeypatch, tracking):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
    monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "MANAGE")
    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(ADMIN, "Admin", is_admin=True)
    s.create_user(ALICE, "Alice")
    set_known_token(s, ADMIN, ADMIN_PASSWORD)
    set_known_token(s, ALICE, ALICE_PASSWORD)
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", s)
    flush_permission_cache()
    yield s
    object.__setattr__(store_module.store, "_instance", previous)
    flush_permission_cache()
    s.engine.dispose()


@pytest.fixture
def app(store):
    application = FastAPI()
    register_exception_handlers(application)
    application.include_router(issue_detection_schedules_router)
    application.add_middleware(AuthMiddleware)
    application.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential")
    return application


@pytest.fixture
def admin(app):
    with TestClient(app, headers=basic(ADMIN, ADMIN_PASSWORD)) as c:
        yield c


@pytest.fixture
def alice(app):
    with TestClient(app, headers=basic(ALICE, ALICE_PASSWORD)) as c:
        yield c


@pytest.mark.parametrize("method,path", [("get", SCHEDULES), ("post", f"{SCHEDULES}/check")])
def test_non_admin_gets_403(alice, tracking, method, path):
    before = json.dumps(tracking.tags)
    assert alice.request(method.upper(), path).status_code == 403
    assert json.dumps(tracking.tags) == before


def test_anonymous_is_refused(app):
    assert TestClient(app).get(SCHEDULES).status_code == 401


def test_the_list_shows_each_schedule_with_its_writer_and_verdict(admin, store, tracking):
    guard.record_author("2", None, ALICE, tracking.tags["2"][TAG])

    body = admin.get(SCHEDULES).json()

    assert body["supported"] is True
    assert body["guard_interval_seconds"] == config.ISSUE_DETECTION_SCHEDULE_GUARD_INTERVAL_SECONDS
    assert body["server_credentials_admin_only"] is False
    entries = {e["experiment_id"]: e for e in body["schedules"]}
    assert entries["1"]["author"] is None and entries["1"]["violation"] == guard.REASON_UNKNOWN_AUTHOR
    assert entries["1"]["model"]["secret_name"] == "team-key" and entries["1"]["uses_server_credentials"] is False
    assert entries["2"]["author"] == ALICE and entries["2"]["violation"] is None
    assert entries["2"]["model"]["endpoint_name"] == "team"
    # Listing pauses nothing.
    assert not json.loads(tracking.tags["1"][TAG])["paused"]


def test_the_check_pauses_what_the_guard_would_and_says_why(admin, store, tracking):
    guard.record_author("2", None, ALICE, tracking.tags["2"][TAG])

    body = admin.post(f"{SCHEDULES}/check").json()

    assert body == {"checked": 2, "paused": [{"experiment_id": "1", "workspace": None, "reason": guard.REASON_UNKNOWN_AUTHOR}], "failed": []}
    assert json.loads(tracking.tags["1"][TAG])["paused"] is True
    assert not json.loads(tracking.tags["2"][TAG])["paused"]
    listed = {e["experiment_id"]: e for e in admin.get(SCHEDULES).json()["schedules"]}
    assert listed["1"]["paused"] is True and listed["1"]["guard_reason"] == guard.REASON_UNKNOWN_AUTHOR and listed["1"]["violation"] is None
