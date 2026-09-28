"""Creating a prompt optimization job is authorized on everything the job acts on.

``POST 3.0/mlflow/prompt-optimization/jobs`` needs UPDATE on the experiment (the run is
created there), UPDATE on the source prompt (the job registers a new version of it) and, when
``config.dataset_id`` is given, READ on every experiment the dataset is linked to.
Driven through the real hook and permission store (see ``authz_harness``).
"""

import pytest
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.tests.hooks.authz_harness import (
    ADMIN,
    EDITOR,
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

DATASETS = {"d-own": [OWN], "d-victim": [VICTIM], "d-unlinked": []}


class _FakeTrackingStore(BaseFakeTrackingStore):
    def get_dataset_experiment_ids(self, dataset_id):
        if dataset_id not in DATASETS:
            raise MlflowException("no dataset", RESOURCE_DOES_NOT_EXIST)
        return DATASETS[dataset_id]


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    s = install_permission_store(tmp_path, monkeypatch, _FakeTrackingStore())
    s.create_registered_model_permission("read-only-prompt", OUTSIDER, "READ")
    s.create_registered_model_permission("hidden-prompt", OUTSIDER, "NO_PERMISSIONS")
    flush_permission_cache()
    yield s
    flush_permission_cache()


def _path(prefix):
    return f"{prefix}/3.0/mlflow/prompt-optimization/jobs"


def _body(experiment_id=OWN, prompt_uri="prompts:/own-prompt/1", dataset_id="d-own", **config):
    body = {"experiment_id": experiment_id, "source_prompt_uri": prompt_uri, "config": {"optimizer_type": 1, **config}}
    if dataset_id is not None:
        body["config"]["dataset_id"] = dataset_id
    return body


@pytest.mark.parametrize("prefix", PREFIXES)
def test_allowed_with_update_on_experiment_and_prompt_and_read_on_dataset(prefix):
    assert allowed(hook(_path(prefix), "POST", OUTSIDER, body=_body()))
    assert allowed(hook(_path(prefix), "POST", OUTSIDER, body=_body(prompt_uri="prompts:/own-prompt@latest", dataset_id=None)))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_experiment_update_is_still_required(prefix):
    assert denied(hook(_path(prefix), "POST", OUTSIDER, body=_body(experiment_id=VICTIM, dataset_id=None)))
    assert denied(hook(_path(prefix), "POST", READER, body=_body(experiment_id=VICTIM, dataset_id=None)))
    assert allowed(hook(_path(prefix), "POST", EDITOR, body=_body(experiment_id=VICTIM, dataset_id=None)))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_update_on_the_source_prompt_is_required(prefix):
    assert denied(hook(_path(prefix), "POST", OUTSIDER, body=_body(prompt_uri="prompts:/read-only-prompt/1")))
    assert denied(hook(_path(prefix), "POST", OUTSIDER, body=_body(prompt_uri="prompts:/hidden-prompt@prod")))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("prompt_uri", ["", "hidden-prompt", "models:/own-prompt/1", "prompts:/own-prompt", "prompts:/a/b/c"])
def test_unrecognised_prompt_uri_is_refused(prefix, prompt_uri):
    assert denied(hook(_path(prefix), "POST", OUTSIDER, body=_body(prompt_uri=prompt_uri)))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_every_prompt_uri_in_any_source_is_authorized(prefix):
    resp = hook(_path(prefix), "POST", OUTSIDER, body=_body(), query={"source_prompt_uri": "prompts:/hidden-prompt/1"})
    assert resp is not None and resp.status_code in (400, 403)
    # Both spellings in one body: refused (the dual-spelling guard answers 400 first).
    resp = hook(_path(prefix), "POST", OUTSIDER, body={**_body(), "sourcePromptUri": "prompts:/hidden-prompt/1"})
    assert resp is not None and resp.status_code in (400, 403)


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("dataset_id", ["d-victim", "d-unlinked", "d-missing"])
def test_dataset_must_resolve_to_readable_experiments(prefix, dataset_id):
    assert denied(hook(_path(prefix), "POST", OUTSIDER, body=_body(dataset_id=dataset_id)))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_camel_case_dataset_id_is_authorized_too(prefix):
    body = _body()
    body["config"]["datasetId"] = "d-victim"
    resp = hook(_path(prefix), "POST", OUTSIDER, body=body)
    assert resp is not None and resp.status_code in (400, 403)


@pytest.mark.parametrize("prefix", PREFIXES)
def test_admin_is_not_restricted(prefix):
    assert allowed(hook(_path(prefix), "POST", ADMIN, body=_body(experiment_id=VICTIM, prompt_uri="prompts:/hidden-prompt/1", dataset_id="d-victim")))
