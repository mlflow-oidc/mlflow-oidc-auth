"""Scorer online-scoring configuration routes are scoped by the scorer's experiment.

``PUT scorers/online-config`` needs UPDATE on the experiment; ``GET scorers/online-configs``
needs READ on the experiment of every configuration the scorer ids resolve to.
Driven through the real hook and permission store (see ``authz_harness``).
"""

import json
from types import SimpleNamespace

import pytest

from mlflow_oidc_auth.tests.hooks.authz_harness import (
    ADMIN,
    EDITOR,
    MANAGER,
    OUTSIDER,
    OWN,
    PREFIXES,
    READER,
    VICTIM,
    BaseFakeTrackingStore,
    allowed,
    denied,
    hook,
    install_permission_store,
)

CONFIG_EXPERIMENT = {"sc-victim": VICTIM, "sc-own": OWN, "sc-own-guarded": OWN, "sc-own-orphan": OWN}


SCORER_NAME = {"sc-victim": "judge", "sc-own": "judge", "sc-own-guarded": "guarded"}


class _FakeTrackingStore(BaseFakeTrackingStore):
    def get_online_scoring_configs(self, scorer_ids):
        return [SimpleNamespace(scorer_id=s, experiment_id=CONFIG_EXPERIMENT[s]) for s in scorer_ids if s in CONFIG_EXPERIMENT]

    def list_scorers(self, experiment_id):
        return [
            SimpleNamespace(scorer_id=s, scorer_name=SCORER_NAME[s], experiment_id=e)
            for s, e in CONFIG_EXPERIMENT.items()
            if e == experiment_id and s in SCORER_NAME
        ]


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    s = install_permission_store(tmp_path, monkeypatch, _FakeTrackingStore())
    # The outsider may write their own experiment, but one scorer in it is withheld.
    s.create_scorer_permission(OWN, "guarded", OUTSIDER, "NO_PERMISSIONS")
    flush_permission_cache()
    yield s
    flush_permission_cache()


def _put(prefix):
    return f"{prefix}/3.0/mlflow/scorers/online-config"


def _get(prefix):
    return f"{prefix}/3.0/mlflow/scorers/online-configs"


@pytest.mark.parametrize("prefix", PREFIXES)
def test_writing_a_config_requires_update_on_the_experiment(prefix):
    body = {"experiment_id": VICTIM, "name": "judge", "sample_rate": 0.5}
    assert denied(hook(_put(prefix), "PUT", OUTSIDER, body=body))
    assert denied(hook(_put(prefix), "PUT", READER, body=body))
    assert allowed(hook(_put(prefix), "PUT", EDITOR, body=body))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_writing_a_config_authorizes_every_experiment_source(prefix):
    body = {"experiment_id": OWN, "name": "judge", "sample_rate": 0.5}
    assert allowed(hook(_put(prefix), "PUT", OUTSIDER, body=body))
    assert denied(hook(_put(prefix), "PUT", OUTSIDER, body=body, query={"experiment_id": VICTIM}))
    assert denied(hook(_put(prefix), "PUT", OUTSIDER, body={**body, "experimentId": VICTIM}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_writing_a_config_with_a_double_encoded_body_is_authorized_on_the_decoded_value(prefix):
    """MLflow decodes a JSON-string body a second time; so must the check."""
    from flask import request as flask_request
    from mlflow.server import app as mlflow_app

    from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
    from mlflow_oidc_auth.hooks.before_request import before_request_hook

    data = json.dumps(json.dumps({"experiment_id": VICTIM, "name": "judge", "sample_rate": 0.5}))
    environ = {AUTH_CONTEXT_KEY: AuthContext(username=OUTSIDER, is_admin=False)}
    with mlflow_app.test_request_context(
        _put(prefix), method="PUT", data=data, content_type="application/json", query_string={"experiment_id": OWN}, environ_base=environ
    ):
        assert flask_request.url_rule is not None
        assert denied(before_request_hook())


@pytest.mark.parametrize("prefix", PREFIXES)
def test_writing_a_config_without_an_experiment_is_admin_only(prefix):
    assert denied(hook(_put(prefix), "PUT", MANAGER, body={"name": "judge", "sample_rate": 0.5}))
    assert allowed(hook(_put(prefix), "PUT", ADMIN, body={"name": "judge", "sample_rate": 0.5}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_reading_configs_requires_read_on_every_resolved_experiment(prefix):
    assert denied(hook(_get(prefix), "GET", OUTSIDER, query={"scorer_ids": "sc-victim"}))
    assert allowed(hook(_get(prefix), "GET", READER, query={"scorer_ids": "sc-victim"}))
    assert allowed(hook(_get(prefix), "GET", OUTSIDER, query={"scorer_ids": "sc-own"}))
    assert denied(hook(_get(prefix), "GET", OUTSIDER, query=[("scorer_ids", "sc-own"), ("scorer_ids", "sc-victim")]))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_reading_configs_with_no_scorer_id_is_admin_only(prefix):
    assert denied(hook(_get(prefix), "GET", MANAGER))
    assert allowed(hook(_get(prefix), "GET", ADMIN))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_writing_a_config_honours_scorer_level_grants(prefix):
    body = {"experiment_id": OWN, "sample_rate": 0.5}
    assert allowed(hook(_put(prefix), "PUT", OUTSIDER, body={**body, "name": "judge"}))
    assert denied(hook(_put(prefix), "PUT", OUTSIDER, body={**body, "name": "guarded"}))
    assert denied(hook(_put(prefix), "PUT", OUTSIDER, body={**body, "name": "judge"}, query={"name": "guarded"}))
    assert denied(hook(_put(prefix), "PUT", MANAGER, body={"experiment_id": VICTIM, "sample_rate": 0.5}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_reading_configs_honours_scorer_level_grants(prefix):
    assert allowed(hook(_get(prefix), "GET", OUTSIDER, query={"scorer_ids": "sc-own"}))
    assert denied(hook(_get(prefix), "GET", OUTSIDER, query={"scorer_ids": "sc-own-guarded"}))
    assert denied(hook(_get(prefix), "GET", OUTSIDER, query=[("scorer_ids", "sc-own"), ("scorer_ids", "sc-own-guarded")]))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_reading_a_config_whose_scorer_cannot_be_found_is_refused(prefix):
    assert denied(hook(_get(prefix), "GET", MANAGER, query={"scorer_ids": "sc-own-orphan"}))
