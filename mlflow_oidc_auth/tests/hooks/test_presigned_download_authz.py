"""``POST 2.0/mlflow/artifacts/presigned-download-url`` needs READ on the run's experiment.

Driven through the real hook and permission store (see ``authz_harness``).
"""

from types import SimpleNamespace

import pytest

from mlflow_oidc_auth.tests.hooks.authz_harness import (
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

RUN_EXPERIMENT = {"run-victim": VICTIM, "run-own": OWN}


class _FakeTrackingStore(BaseFakeTrackingStore):
    def get_run(self, run_id):
        return SimpleNamespace(info=SimpleNamespace(run_id=run_id, experiment_id=RUN_EXPERIMENT[run_id]))


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    yield install_permission_store(tmp_path, monkeypatch, _FakeTrackingStore())
    flush_permission_cache()


@pytest.mark.parametrize("prefix", PREFIXES)
def test_presigned_download_requires_read_on_the_run(prefix):
    path = f"{prefix}/2.0/mlflow/artifacts/presigned-download-url"
    assert denied(hook(path, "POST", OUTSIDER, body={"run_id": "run-victim", "path": "model.pkl"}))
    assert allowed(hook(path, "POST", READER, body={"run_id": "run-victim", "path": "model.pkl"}))
    assert allowed(hook(path, "POST", OUTSIDER, body={"run_id": "run-own", "path": "model.pkl"}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_presigned_download_authorizes_every_run_source(prefix):
    path = f"{prefix}/2.0/mlflow/artifacts/presigned-download-url"
    assert denied(hook(path, "POST", OUTSIDER, body={"run_id": "run-own", "path": "m"}, query={"run_id": "run-victim"}))
    assert denied(hook(path, "POST", OUTSIDER, body={"run_id": "run-own", "run_uuid": "run-victim", "path": "m"}))
