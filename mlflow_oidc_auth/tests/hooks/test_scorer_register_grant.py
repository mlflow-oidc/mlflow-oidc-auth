"""Scorer grants across ``RegisterScorer`` versions and ``DeleteScorer`` (issue #453).

MLflow appends a new version when a scorer name is registered again in the same experiment;
the UI does this to edit a judge, and to re-create a guardrail whose scorer outlived it. So:

* only version 1 is a creation and grants the creator MANAGE; a later version grants nothing
  and must not fail on the creator's existing grant ("Scorer permission already exists");
* a later version is an update of that scorer and needs UPDATE on it, not only on the
  experiment;
* a user or group grant on a name binds its first registration too;
* ``DeleteScorer`` with a ``version`` removes that version only, so the grants stay until the
  last version is gone — and only the scorer MLflow acted on is considered.

Driven through the real hooks, MLflow's real views and the real permission store.
"""

from types import SimpleNamespace

import pytest
from flask import request
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST
from mlflow.server import app as mlflow_app

from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.tests.hooks.authz_harness import (
    EDITOR,
    MANAGER,
    OWN,
    PREFIXES,
    READER,
    VICTIM,
    BaseFakeTrackingStore,
    install_permission_store,
)


class _FakeTrackingStore(BaseFakeTrackingStore):
    """Scorer versions as MLflow keeps them: the record outlives versions deleted one by one."""

    def __init__(self):
        self.versions = {}

    def register_scorer(self, experiment_id, name, serialized_scorer):
        versions = self.versions.setdefault((str(experiment_id), name), [])
        versions.append(max(versions, default=0) + 1)
        return SimpleNamespace(
            scorer_version=versions[-1],
            scorer_id=f"id-{experiment_id}-{name}",
            experiment_id=str(experiment_id),
            scorer_name=name,
            _serialized_scorer=serialized_scorer,
            creation_time=0,
        )

    def get_scorer(self, experiment_id, name, version=None):
        if not self.versions.get((str(experiment_id), name)):
            raise MlflowException(f"Scorer with name '{name}' not found", RESOURCE_DOES_NOT_EXIST)
        return SimpleNamespace()

    def delete_scorer(self, experiment_id, name, version=None):
        versions = self.versions.get((str(experiment_id), name), [])
        if version is None:
            versions.clear()
        else:
            versions.remove(int(version))


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    s = install_permission_store(tmp_path, monkeypatch, _FakeTrackingStore())
    monkeypatch.setattr("mlflow_oidc_auth.hooks.after_request.store", s, raising=False)
    yield s
    flush_permission_cache()


def _call(path, method, username, body):
    """Run one request through the real hooks and view; return the response."""
    from mlflow_oidc_auth.hooks.after_request import after_request_hook
    from mlflow_oidc_auth.hooks.before_request import before_request_hook
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    flush_permission_cache()
    environ = {AUTH_CONTEXT_KEY: AuthContext(username=username, is_admin=False)}
    with mlflow_app.test_request_context(path, method=method, json=body, environ_base=environ):
        denied = before_request_hook()
        if denied is not None:
            return denied
        view = mlflow_app.view_functions[request.url_rule.endpoint]
        return after_request_hook(mlflow_app.make_response(view(**(request.view_args or {}))))


def _register(prefix, username, name="judge"):
    body = {"experiment_id": VICTIM, "name": name, "serialized_scorer": "{}"}
    return _call(f"{prefix}/3.0/mlflow/scorers/register", "POST", username, body)


def _delete(prefix, username, name="judge", version=None):
    body = {"experiment_id": VICTIM, "name": name}
    if version is not None:
        body["version"] = version
    return _call(f"{prefix}/3.0/mlflow/scorers/delete", "DELETE", username, body)


def _grant(store, username):
    try:
        return store.get_scorer_permission(VICTIM, "judge", username).permission
    except MlflowException:
        return None


@pytest.mark.parametrize("prefix", PREFIXES)
def test_creator_gets_manage_on_first_version(permission_store, prefix):
    resp = _register(prefix, MANAGER)
    assert resp.status_code == 200, resp.get_data()
    assert _grant(permission_store, MANAGER) == "MANAGE"


@pytest.mark.parametrize("prefix", PREFIXES)
def test_creator_re_registering_succeeds(permission_store, prefix):
    assert _register(prefix, MANAGER).status_code == 200
    resp = _register(prefix, MANAGER)
    assert resp.status_code == 200, resp.get_data()
    assert _grant(permission_store, MANAGER) == "MANAGE"


@pytest.mark.parametrize("prefix", PREFIXES)
def test_new_version_by_another_user_grants_nothing(permission_store, prefix):
    assert _register(prefix, MANAGER).status_code == 200
    resp = _register(prefix, EDITOR)
    assert resp.status_code == 200, resp.get_data()
    assert _grant(permission_store, EDITOR) is None


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("scorer_permission", ["READ", "NO_PERMISSIONS"])
def test_new_version_needs_update_on_the_scorer(permission_store, prefix, scorer_permission):
    assert _register(prefix, MANAGER).status_code == 200
    permission_store.create_scorer_permission(VICTIM, "judge", EDITOR, scorer_permission)
    assert _register(prefix, EDITOR).status_code == 403
    assert _register(prefix, MANAGER).status_code == 200  # the owner still can


@pytest.mark.parametrize("prefix", PREFIXES)
def test_new_scorer_still_needs_update_on_the_experiment(permission_store, prefix):
    assert _register(prefix, READER).status_code == 403


@pytest.mark.parametrize("prefix", PREFIXES)
def test_deleting_one_version_keeps_the_grants(permission_store, prefix):
    assert _register(prefix, MANAGER).status_code == 200
    assert _register(prefix, MANAGER).status_code == 200
    permission_store.create_scorer_permission(VICTIM, "judge", EDITOR, "NO_PERMISSIONS")
    assert _delete(prefix, MANAGER, version=2).status_code == 200
    assert _grant(permission_store, MANAGER) == "MANAGE"
    assert _grant(permission_store, EDITOR) == "NO_PERMISSIONS"


@pytest.mark.parametrize("prefix", PREFIXES)
def test_deleting_the_last_version_clears_the_grants(permission_store, prefix):
    assert _register(prefix, MANAGER).status_code == 200
    assert _register(prefix, MANAGER).status_code == 200
    assert _delete(prefix, MANAGER, version=2).status_code == 200
    assert _delete(prefix, MANAGER, version=1).status_code == 200
    assert _grant(permission_store, MANAGER) is None
    # The name starts clean: the next registration is a creation again.
    assert _register(prefix, MANAGER).status_code == 200
    assert _grant(permission_store, MANAGER) == "MANAGE"


@pytest.mark.parametrize("prefix", PREFIXES)
def test_deleting_every_version_clears_the_grants(permission_store, prefix):
    assert _register(prefix, MANAGER).status_code == 200
    assert _register(prefix, MANAGER).status_code == 200
    assert _delete(prefix, MANAGER).status_code == 200
    assert _grant(permission_store, MANAGER) is None


@pytest.mark.parametrize("prefix", PREFIXES)
def test_delete_leaves_grants_on_a_pair_mlflow_did_not_act_on(permission_store, prefix):
    # (OWN, "judge") has no version this request can see — as for a scorer of another
    # workspace — and is named only in the query string, which MLflow does not read here.
    assert _register(prefix, MANAGER).status_code == 200
    permission_store.create_scorer_permission(OWN, "judge", EDITOR, "NO_PERMISSIONS")
    from mlflow_oidc_auth.hooks.after_request import after_request_hook
    from mlflow_oidc_auth.hooks.before_request import before_request_hook

    environ = {AUTH_CONTEXT_KEY: AuthContext(username=MANAGER, is_admin=False)}
    body = {"experiment_id": VICTIM, "name": "judge"}
    with mlflow_app.test_request_context(
        f"{prefix}/3.0/mlflow/scorers/delete", method="DELETE", json=body, query_string={"experiment_id": OWN}, environ_base=environ
    ):
        if before_request_hook() is None:
            view = mlflow_app.view_functions[request.url_rule.endpoint]
            after_request_hook(mlflow_app.make_response(view(**(request.view_args or {}))))
    assert permission_store.get_scorer_permission(OWN, "judge", EDITOR).permission == "NO_PERMISSIONS"


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("scorer_permission", ["READ", "NO_PERMISSIONS"])
def test_grant_set_before_creation_binds_the_first_registration(permission_store, prefix, scorer_permission):
    permission_store.create_scorer_permission(VICTIM, "judge", EDITOR, scorer_permission)
    assert _register(prefix, EDITOR).status_code == 403


@pytest.mark.parametrize("prefix", PREFIXES)
def test_first_registration_keeps_a_grant_set_before_creation(permission_store, prefix):
    permission_store.create_scorer_permission(VICTIM, "judge", EDITOR, "EDIT")
    resp = _register(prefix, EDITOR)
    assert resp.status_code == 200, resp.get_data()
    assert _grant(permission_store, EDITOR) == "EDIT"
