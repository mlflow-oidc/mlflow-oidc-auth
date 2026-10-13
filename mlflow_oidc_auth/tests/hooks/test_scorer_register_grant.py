"""Scorer grants across ``RegisterScorer`` versions and ``DeleteScorer`` (issue #453).

MLflow appends a new version when a scorer name is registered again in the same experiment;
the UI does this to edit a judge, and to re-create a guardrail whose scorer outlived it. So:

* only version 1 is a creation and grants the creator MANAGE; a later version grants nothing
  and must not fail on the creator's existing grant ("Scorer permission already exists");
* a later version needs UPDATE on the experiment, and a grant on the scorer itself, when
  there is one, decides — a scorer without one follows its experiment, as listing does;
* a grant on a name (user, group, regex or group-regex) binds its first registration too,
  since the creator's MANAGE would otherwise outrank it; one already held by the creator
  keeps its level;
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
    OUTSIDER,
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
        self.fail_lookups = False

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
        if self.fail_lookups:
            raise RuntimeError("tracking store unavailable")
        if not self.versions.get((str(experiment_id), name)):
            raise MlflowException(f"Scorer with name '{name}' not found", RESOURCE_DOES_NOT_EXIST)
        return SimpleNamespace()

    def delete_scorer(self, experiment_id, name, version=None):
        versions = self.versions.get((str(experiment_id), name), [])
        if version is None:
            versions.clear()
        else:
            versions.remove(int(version))


TRACKING_STORE = None


def permission_store_versions(experiment_id, name):
    return TRACKING_STORE.versions.get((str(experiment_id), name))


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    global TRACKING_STORE
    TRACKING_STORE = _FakeTrackingStore()
    s = install_permission_store(tmp_path, monkeypatch, TRACKING_STORE)
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
        assert before_request_hook() is None
        view = mlflow_app.view_functions[request.url_rule.endpoint]
        resp = after_request_hook(mlflow_app.make_response(view(**(request.view_args or {}))))
    assert resp.status_code == 200, resp.get_data()
    assert not permission_store_versions(VICTIM, "judge")
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
    assert _grant(permission_store, EDITOR) == "EDIT"  # not raised to MANAGE


@pytest.mark.parametrize("prefix", PREFIXES)
def test_scorer_without_a_grant_follows_its_experiment_under_deny_by_default(permission_store, monkeypatch, prefix):
    from mlflow_oidc_auth.config import config

    monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")
    assert _register(prefix, MANAGER).status_code == 200
    # EDITOR: EDIT on the experiment, no grant on the scorer — may save a new version.
    resp = _register(prefix, EDITOR)
    assert resp.status_code == 200, resp.get_data()
    # READER: READ on the experiment — may not.
    assert _register(prefix, READER).status_code == 403


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("source", ["regex", "group-regex"])
def test_regex_grant_binds_creation_and_new_versions(permission_store, prefix, source):
    if source == "regex":
        permission_store.create_scorer_regex_permission("^judge", 1, "READ", EDITOR)
    else:
        permission_store.populate_groups(["analysts"])
        permission_store.add_user_to_group(EDITOR, "analysts")
        permission_store.create_group_scorer_regex_permission("analysts", "^judge", 1, "NO_PERMISSIONS")
    # A new matching name: creating it would hand EDITOR a user MANAGE that outranks the regex.
    assert _register(prefix, EDITOR, name="judge-new").status_code == 403
    assert _register(prefix, MANAGER).status_code == 200
    assert _register(prefix, EDITOR).status_code == 403
    assert _register(prefix, EDITOR, name="other").status_code == 200  # no match: the experiment decides


@pytest.mark.parametrize("prefix", PREFIXES)
def test_user_without_a_record_may_add_a_version_but_not_create(permission_store, prefix):
    ghost = "ghost@example.com"  # authenticated, never provisioned; default MANAGE gives experiment UPDATE
    assert _register(prefix, MANAGER).status_code == 200
    resp = _register(prefix, ghost)
    assert resp.status_code == 200, resp.get_data()
    assert _register(prefix, ghost, name="brand-new").status_code == 403


@pytest.mark.parametrize("prefix", PREFIXES)
def test_delete_keeps_grants_when_the_version_lookup_fails(permission_store, prefix):
    assert _register(prefix, MANAGER).status_code == 200
    TRACKING_STORE.fail_lookups = True
    assert _delete(prefix, MANAGER).status_code == 200
    assert _grant(permission_store, MANAGER) == "MANAGE"


# ---------------------------------------------------------------------------
# A scorer with no grant of its own inherits its experiment's permission, for every scorer
# route; the experiment in turn falls back to DEFAULT_MLFLOW_PERMISSION. Run under the
# shipped deny-by-default so the inheritance, not the default, is what opens access.
# ---------------------------------------------------------------------------


def _authorized(path, method, username, *, query=None, body=None):
    """Whether the real before_request_hook lets the request through."""
    from mlflow_oidc_auth.hooks.before_request import before_request_hook
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    flush_permission_cache()
    environ = {AUTH_CONTEXT_KEY: AuthContext(username=username, is_admin=False)}
    kwargs = {"query_string": query} if query is not None else {"json": body}
    with mlflow_app.test_request_context(path, method=method, environ_base=environ, **kwargs):
        return before_request_hook() is None


@pytest.fixture
def deny_by_default(monkeypatch):
    from mlflow_oidc_auth.config import config

    monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize(
    "username, can_read, can_update, can_delete",
    [
        (MANAGER, True, True, True),  # MANAGE on the experiment
        (EDITOR, True, True, False),  # EDIT
        (READER, True, False, False),  # READ
        (OUTSIDER, False, False, False),  # NO_PERMISSIONS on the experiment
        ("ghost@example.com", False, False, False),  # nothing anywhere: the default decides
    ],
)
def test_scorer_without_a_grant_inherits_its_experiment(permission_store, deny_by_default, prefix, username, can_read, can_update, can_delete):
    TRACKING_STORE.register_scorer(VICTIM, "judge", "{}")  # someone else's scorer, no grants on it
    scorer = {"experiment_id": VICTIM, "name": "judge"}
    assert _authorized(f"{prefix}/3.0/mlflow/scorers/get", "GET", username, query=scorer) is can_read
    assert _authorized(f"{prefix}/3.0/mlflow/scorers/versions", "GET", username, query=scorer) is can_read
    assert _authorized(f"{prefix}/3.0/mlflow/scorers/register", "POST", username, body={**scorer, "serialized_scorer": "{}"}) is can_update
    assert _authorized(f"{prefix}/3.0/mlflow/scorers/delete", "DELETE", username, body=scorer) is can_delete


@pytest.mark.parametrize("prefix", PREFIXES)
def test_a_grant_on_the_scorer_overrides_its_experiment(permission_store, deny_by_default, prefix):
    TRACKING_STORE.register_scorer(VICTIM, "judge", "{}")
    scorer = {"experiment_id": VICTIM, "name": "judge"}
    permission_store.create_scorer_permission(VICTIM, "judge", EDITOR, "NO_PERMISSIONS")  # EDIT on the experiment
    permission_store.create_scorer_permission(VICTIM, "judge", READER, "MANAGE")  # READ on the experiment
    assert not _authorized(f"{prefix}/3.0/mlflow/scorers/get", "GET", EDITOR, query=scorer)
    assert _authorized(f"{prefix}/3.0/mlflow/scorers/delete", "DELETE", READER, body=scorer)
