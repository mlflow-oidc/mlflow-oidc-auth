"""``ListScorers`` with and without an experiment id, filtered per scorer.

With ``experiment_id`` the request needs READ on that experiment. Without one MLflow lists the
scorers of every active experiment, so the request is open to any authenticated user and the
after-request filter keeps only the scorers the caller can read: READ on the scorer's
experiment, and a scorer-level grant, when there is one, decides (``NO_PERMISSIONS`` hides).
Driven through the real hooks, MLflow's real view and the real permission store.
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import request
from mlflow.protos.service_pb2 import Scorer
from mlflow.server import app as mlflow_app

from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.tests.hooks.authz_harness import (
    ADMIN,
    OUTSIDER,
    OWN,
    PREFIXES,
    READER,
    VICTIM,
    BaseFakeTrackingStore,
    install_permission_store,
)

OPEN = "3"  # no grants for anyone: follows DEFAULT_MLFLOW_PERMISSION
SCORERS = [(VICTIM, "judge"), (OWN, "judge"), (OWN, "guarded"), (OPEN, "open")]


class _PagedList(list):
    token = None


class _FakeTrackingStore(BaseFakeTrackingStore):
    @staticmethod
    def _scorer(experiment_id, name):
        proto = Scorer(experiment_id=int(experiment_id), scorer_name=name, scorer_version=1, serialized_scorer="{}")
        return SimpleNamespace(to_proto=lambda: proto)

    def list_scorers(self, experiment_id):
        return [self._scorer(e, n) for e, n in SCORERS if e == str(experiment_id)]

    def search_experiments(self, **_kwargs):
        return _PagedList(SimpleNamespace(experiment_id=e) for e in (VICTIM, OWN, OPEN))

    def list_scorers_across_experiments(self, experiment_ids):
        return [self._scorer(e, n) for e, n in SCORERS if e in experiment_ids]


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    s = install_permission_store(tmp_path, monkeypatch, _FakeTrackingStore())
    monkeypatch.setattr("mlflow_oidc_auth.hooks.after_request.store", s, raising=False)
    # OUTSIDER: NO_PERMISSIONS on VICTIM, EDIT on OWN (harness). One scorer in OWN is withheld,
    # and a scorer-level READ on VICTIM's scorer does not open an unreadable experiment.
    s.create_scorer_permission(OWN, "guarded", OUTSIDER, "NO_PERMISSIONS")
    s.create_scorer_permission(VICTIM, "judge", OUTSIDER, "READ")
    flush_permission_cache()
    yield s
    flush_permission_cache()


def _list(prefix, username, query=None):
    """Run ListScorers through the real hooks and view; return the response."""
    from mlflow_oidc_auth.hooks.after_request import after_request_hook
    from mlflow_oidc_auth.hooks.before_request import before_request_hook

    environ = {AUTH_CONTEXT_KEY: AuthContext(username=username, is_admin=username == ADMIN)}
    kwargs = {"query_string": query} if query is not None else {}
    with mlflow_app.test_request_context(f"{prefix}/3.0/mlflow/scorers/list", method="GET", environ_base=environ, **kwargs):
        denied = before_request_hook()
        if denied is not None:
            return denied
        assert request.url_rule is not None
        view = mlflow_app.view_functions[request.url_rule.endpoint]
        return after_request_hook(mlflow_app.make_response(view(**(request.view_args or {}))))


def _names(resp):
    assert resp.status_code == 200, resp.status_code
    return sorted((str(s["experiment_id"]), s["scorer_name"]) for s in json.loads(resp.get_data()).get("scorers", []))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_cross_experiment_list_is_filtered_per_scorer(prefix):
    assert _names(_list(prefix, OUTSIDER)) == [(OWN, "judge"), (OPEN, "open")]


@pytest.mark.parametrize("prefix", PREFIXES)
def test_cross_experiment_list_for_reader_and_admin(prefix):
    everything = sorted(SCORERS)
    assert _names(_list(prefix, READER)) == everything
    assert _names(_list(prefix, ADMIN)) == everything


@pytest.mark.parametrize("prefix", PREFIXES)
def test_experiment_list_requires_read_on_the_experiment(prefix):
    resp = _list(prefix, OUTSIDER, {"experiment_id": VICTIM})
    assert resp.status_code == 403


@pytest.mark.parametrize("prefix", PREFIXES)
def test_experiment_list_hides_scorers_with_no_permissions_grant(prefix):
    assert _names(_list(prefix, OUTSIDER, {"experiment_id": OWN})) == [(OWN, "judge")]
    assert _names(_list(prefix, READER, {"experiment_id": OWN})) == [(OWN, "guarded"), (OWN, "judge")]


def test_scorer_without_own_grant_follows_its_experiment(monkeypatch):
    from mlflow_oidc_auth.config import config
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")
    flush_permission_cache()
    # OWN is readable through the EDIT grant; OPEN now falls to NO_PERMISSIONS.
    assert _names(_list("/api", OUTSIDER)) == [(OWN, "judge")]


def test_lookup_error_drops_the_row():
    with patch("mlflow_oidc_auth.hooks.after_request.effective_scorer_permission", side_effect=RuntimeError("store down")):
        assert _names(_list("/api", OUTSIDER)) == []
