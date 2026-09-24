"""The Flask job routes (``/ajax-api/3.0/mlflow/jobs/*``) are scoped by the job's experiment.

READ to read a job, UPDATE to cancel it. A job that does not exist or records no experiment
is admin-only. Driven through the real hook and permission store (see ``authz_harness``).
"""

import json
from types import SimpleNamespace

import pytest
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.tests.hooks.authz_harness import (
    ADMIN,
    EDITOR,
    MANAGER,
    OUTSIDER,
    READER,
    VICTIM,
    BaseFakeTrackingStore,
    allowed,
    denied,
    hook,
    install_permission_store,
)

JOBS = {"job-victim": {"experiment_id": VICTIM, "trace_ids": []}, "job-unscoped": {"trace_ids": []}}


def _get_job(job_id):
    if job_id not in JOBS:
        raise MlflowException(f"Job '{job_id}' not found", RESOURCE_DOES_NOT_EXIST)
    return SimpleNamespace(job_id=job_id, params=json.dumps(JOBS[job_id]))


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    monkeypatch.setattr("mlflow_oidc_auth.validators.job.get_job", _get_job)
    yield install_permission_store(tmp_path, monkeypatch, BaseFakeTrackingStore())
    flush_permission_cache()


GET_JOB = "/ajax-api/3.0/mlflow/jobs/{}"
CANCEL_JOB = "/ajax-api/3.0/mlflow/jobs/cancel/{}"


def test_reading_a_job_requires_read_on_its_experiment():
    assert denied(hook(GET_JOB.format("job-victim"), "GET", OUTSIDER))
    assert allowed(hook(GET_JOB.format("job-victim"), "GET", READER))
    assert allowed(hook(GET_JOB.format("job-victim"), "HEAD", READER))
    assert denied(hook(GET_JOB.format("job-victim"), "HEAD", OUTSIDER))


def test_cancelling_a_job_requires_update_on_its_experiment():
    assert denied(hook(CANCEL_JOB.format("job-victim"), "PATCH", OUTSIDER))
    assert denied(hook(CANCEL_JOB.format("job-victim"), "PATCH", READER))
    assert allowed(hook(CANCEL_JOB.format("job-victim"), "PATCH", EDITOR))


@pytest.mark.parametrize("job_id", ["job-unscoped", "job-missing"])
def test_an_unresolvable_job_is_admin_only(job_id):
    assert denied(hook(GET_JOB.format(job_id), "GET", MANAGER))
    assert denied(hook(CANCEL_JOB.format(job_id), "PATCH", MANAGER))
    assert allowed(hook(GET_JOB.format(job_id), "GET", ADMIN))


def test_a_second_job_id_in_the_query_string_is_authorized_too():
    JOBS["job-own"] = {"experiment_id": "2"}
    try:
        assert allowed(hook(CANCEL_JOB.format("job-own"), "PATCH", OUTSIDER))
        assert denied(hook(CANCEL_JOB.format("job-own"), "PATCH", OUTSIDER, query={"job_id": "job-victim"}))
    finally:
        del JOBS["job-own"]
