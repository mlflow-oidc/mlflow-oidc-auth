"""Evaluation datasets (``/3.0/mlflow/datasets/*``) are scoped by their linked experiments.

READ on every linked experiment to read, UPDATE to write, DELETE to delete. Create and
search need the experiments in ``experiment_ids``; add/remove need UPDATE on both the
dataset's experiments and the ones named. A dataset linked to no experiment is admin-only.
Driven through the real hook and permission store (see ``authz_harness``).
"""

import json

import pytest
from flask import Response
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST
from mlflow.server import app as mlflow_app

from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.tests.hooks.authz_harness import (
    ADMIN,
    EDITOR,
    BaseFakeTrackingStore,
    MANAGER,
    OUTSIDER,
    OWN,
    PREFIXES,
    READER,
    VICTIM,
    allowed,
    denied,
    hook,
    install_permission_store,
)

LINKS = {"ds-victim": [VICTIM], "ds-own": [OWN], "ds-both": [VICTIM, OWN], "ds-unlinked": []}


class _FakeTrackingStore(BaseFakeTrackingStore):
    def get_dataset_experiment_ids(self, dataset_id):
        if dataset_id not in LINKS:
            raise MlflowException(f"Dataset '{dataset_id}' not found", RESOURCE_DOES_NOT_EXIST)
        return list(LINKS[dataset_id])


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    yield install_permission_store(tmp_path, monkeypatch, _FakeTrackingStore())
    flush_permission_cache()


def _ds(prefix, dataset_id, tail=""):
    return f"{prefix}/3.0/mlflow/datasets/{dataset_id}{tail}"


READS = [pytest.param("", id="get"), pytest.param("/records", id="records"), pytest.param("/experiment-ids", id="experiment-ids")]
WRITES = [
    pytest.param("/tags", "PATCH", {"tags": "{}"}, id="set-tags"),
    pytest.param("/tags/k", "DELETE", None, id="delete-tag"),
    pytest.param("/records", "POST", {"records": "[]"}, id="upsert-records"),
    pytest.param("/records", "DELETE", {"dataset_record_ids": []}, id="delete-records"),
]


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("tail", READS)
def test_reading_a_dataset_requires_read_on_its_experiment(prefix, tail):
    path = _ds(prefix, "ds-victim", tail)
    assert denied(hook(path, "GET", OUTSIDER))
    assert allowed(hook(path, "GET", READER))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("tail, method, body", WRITES)
def test_writing_a_dataset_requires_update_on_its_experiment(prefix, tail, method, body):
    path = _ds(prefix, "ds-victim", tail)
    assert denied(hook(path, method, OUTSIDER, body=body))
    assert denied(hook(path, method, READER, body=body))
    assert allowed(hook(path, method, EDITOR, body=body))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_deleting_a_dataset_requires_delete_on_its_experiment(prefix):
    path = _ds(prefix, "ds-victim")
    assert denied(hook(path, "DELETE", EDITOR))
    assert allowed(hook(path, "DELETE", MANAGER))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_a_dataset_linked_to_several_experiments_needs_every_one(prefix):
    """The outsider may write OWN, but the dataset is also linked to VICTIM."""
    assert allowed(hook(_ds(prefix, "ds-own", "/tags"), "PATCH", OUTSIDER, body={"tags": "{}"}))
    assert denied(hook(_ds(prefix, "ds-both", "/tags"), "PATCH", OUTSIDER, body={"tags": "{}"}))
    assert denied(hook(_ds(prefix, "ds-both"), "GET", OUTSIDER))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("dataset_id", ["ds-unlinked", "ds-missing"])
def test_an_unlinked_or_unknown_dataset_is_admin_only(prefix, dataset_id):
    path = _ds(prefix, dataset_id)
    assert denied(hook(path, "GET", MANAGER))
    assert denied(hook(path, "DELETE", MANAGER))
    assert allowed(hook(path, "GET", ADMIN))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_a_dataset_id_in_the_body_that_differs_from_the_path_is_refused(prefix):
    resp = hook(_ds(prefix, "ds-own", "/tags"), "PATCH", OUTSIDER, body={"dataset_id": "ds-victim", "tags": "{}"})
    assert resp is not None and resp.status_code in (400, 403)


# ---------------------------------------------------------------------------
# create / search
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
def test_create_requires_update_on_every_named_experiment(prefix):
    path = f"{prefix}/3.0/mlflow/datasets/create"
    assert denied(hook(path, "POST", OUTSIDER, body={"name": "d", "experiment_ids": [VICTIM]}))
    assert denied(hook(path, "POST", READER, body={"name": "d", "experiment_ids": [VICTIM]}))
    assert allowed(hook(path, "POST", EDITOR, body={"name": "d", "experiment_ids": [VICTIM]}))
    assert allowed(hook(path, "POST", OUTSIDER, body={"name": "d", "experiment_ids": [OWN]}))
    assert denied(hook(path, "POST", OUTSIDER, body={"name": "d", "experiment_ids": [OWN, VICTIM]}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_create_without_an_experiment_is_admin_only(prefix):
    path = f"{prefix}/3.0/mlflow/datasets/create"
    assert denied(hook(path, "POST", MANAGER, body={"name": "d"}))
    assert allowed(hook(path, "POST", ADMIN, body={"name": "d"}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_create_authorizes_experiment_ids_in_the_query_string_too(prefix):
    path = f"{prefix}/3.0/mlflow/datasets/create"
    assert denied(hook(path, "POST", OUTSIDER, body={"name": "d", "experiment_ids": [OWN]}, query={"experiment_ids": VICTIM}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_search_requires_read_on_every_scoped_experiment(prefix):
    path = f"{prefix}/3.0/mlflow/datasets/search"
    assert denied(hook(path, "POST", OUTSIDER, body={"experiment_ids": [VICTIM]}))
    assert allowed(hook(path, "POST", READER, body={"experiment_ids": [VICTIM]}))
    assert denied(hook(path, "GET", OUTSIDER, query={"experiment_ids": VICTIM}))
    assert allowed(hook(path, "GET", READER, query={"experiment_ids": VICTIM}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_unscoped_search_is_admin_only(prefix):
    path = f"{prefix}/3.0/mlflow/datasets/search"
    assert denied(hook(path, "POST", MANAGER, body={}))
    assert allowed(hook(path, "POST", ADMIN, body={}))


def _filtered(username, datasets, is_admin=False):
    from mlflow_oidc_auth.hooks.after_request import _filter_search_evaluation_datasets

    environ = {AUTH_CONTEXT_KEY: AuthContext(username=username, is_admin=is_admin)}
    with mlflow_app.test_request_context("/api/3.0/mlflow/datasets/search", method="POST", environ_base=environ):
        resp = Response(json.dumps({"datasets": datasets}), mimetype="application/json")
        _filter_search_evaluation_datasets(resp)
        return [d["dataset_id"] for d in json.loads(resp.get_data())["datasets"]]


def test_search_results_keep_only_datasets_whose_experiments_are_all_readable():
    datasets = [{"dataset_id": d} for d in ("ds-victim", "ds-own", "ds-both", "ds-unlinked")]
    assert _filtered(OUTSIDER, datasets) == ["ds-own"]
    assert _filtered(READER, datasets) == ["ds-victim", "ds-own", "ds-both"]
    assert _filtered(ADMIN, datasets, is_admin=True) == ["ds-victim", "ds-own", "ds-both", "ds-unlinked"]


def test_search_filter_is_bound_to_every_search_route():
    from mlflow_oidc_auth.hooks.after_request import AFTER_REQUEST_HANDLERS, _filter_search_evaluation_datasets

    for prefix in PREFIXES:
        for method in ("GET", "POST"):
            assert AFTER_REQUEST_HANDLERS[(f"{prefix}/3.0/mlflow/datasets/search", method)] is _filter_search_evaluation_datasets


# ---------------------------------------------------------------------------
# add / remove experiments
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("action", ["add-experiments", "remove-experiments"])
def test_linking_requires_update_on_both_sides(prefix, action):
    # Linking one's own dataset into another tenant's experiment.
    assert denied(hook(_ds(prefix, "ds-own", f"/{action}"), "POST", OUTSIDER, body={"experiment_ids": [VICTIM]}))
    # Linking another tenant's dataset into one's own experiment.
    assert denied(hook(_ds(prefix, "ds-victim", f"/{action}"), "POST", OUTSIDER, body={"experiment_ids": [OWN]}))
    assert denied(hook(_ds(prefix, "ds-victim", f"/{action}"), "POST", READER, body={"experiment_ids": [VICTIM]}))
    assert allowed(hook(_ds(prefix, "ds-own", f"/{action}"), "POST", OUTSIDER, body={"experiment_ids": [OWN]}))
    assert allowed(hook(_ds(prefix, "ds-victim", f"/{action}"), "POST", EDITOR, body={"experiment_ids": [VICTIM]}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_linking_with_no_experiment_is_refused(prefix):
    assert denied(hook(_ds(prefix, "ds-victim", "/add-experiments"), "POST", MANAGER, body={"experiment_ids": []}))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("action", ["search", "create"])
def test_a_scope_only_in_the_query_string_of_a_post_does_not_count(prefix, action):
    """MLflow reads a POST's body only; a query-string scope would leave its search unscoped."""
    path = f"{prefix}/3.0/mlflow/datasets/{action}"
    assert denied(hook(path, "POST", READER, body={"name": "d"}, query={"experiment_ids": VICTIM}))
