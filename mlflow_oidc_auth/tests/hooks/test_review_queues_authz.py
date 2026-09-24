"""Review queues (``/3.0/mlflow/review-queues/*``) are scoped by their experiment.

READ to read, UPDATE to create, change or add/remove items, DELETE to delete, MANAGE to
hand a queue to a new owner. A personal queue can only be fetched or created for the
caller, and review work can only be attributed to the caller.
Driven through the real hook and permission store (see ``authz_harness``).
"""

from types import SimpleNamespace

import pytest
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.tests.hooks.authz_harness import (
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


class _FakeTrackingStore(BaseFakeTrackingStore):
    def get_review_queue(self, queue_id):
        if queue_id != "rq-victim":
            raise MlflowException(f"Review queue '{queue_id}' not found", RESOURCE_DOES_NOT_EXIST)
        return SimpleNamespace(queue_id=queue_id, experiment_id=VICTIM)


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    yield install_permission_store(tmp_path, monkeypatch, _FakeTrackingStore())
    flush_permission_cache()


def _rq(prefix, action):
    return f"{prefix}/3.0/mlflow/review-queues/{action}"


@pytest.mark.parametrize("prefix", PREFIXES)
def test_create_requires_update_on_the_experiment(prefix):
    body = {"experiment_id": VICTIM, "name": "q", "queue_type": "CUSTOM"}
    assert denied(hook(_rq(prefix, "create"), "POST", OUTSIDER, body=body))
    assert denied(hook(_rq(prefix, "create"), "POST", READER, body=body))
    assert allowed(hook(_rq(prefix, "create"), "POST", EDITOR, body=body))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_personal_queue_is_only_for_the_caller(prefix):
    path = _rq(prefix, "get-or-create-user")
    assert allowed(hook(path, "POST", EDITOR, body={"experiment_id": VICTIM, "user": EDITOR}))
    assert allowed(hook(path, "POST", EDITOR, body={"experiment_id": VICTIM, "user": EDITOR.upper()}))
    assert denied(hook(path, "POST", EDITOR, body={"experiment_id": VICTIM, "user": READER}))
    assert denied(hook(path, "POST", EDITOR, body={"experiment_id": VICTIM, "user": EDITOR}, query={"user": READER}))
    assert denied(hook(path, "POST", READER, body={"experiment_id": VICTIM, "user": READER}))
    assert denied(hook(path, "POST", OUTSIDER, body={"experiment_id": VICTIM, "user": OUTSIDER}))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("action", ["get", "items/list"])
def test_reading_a_queue_requires_read_on_its_experiment(prefix, action):
    assert denied(hook(_rq(prefix, action), "GET", OUTSIDER, query={"queue_id": "rq-victim"}))
    assert allowed(hook(_rq(prefix, action), "GET", READER, query={"queue_id": "rq-victim"}))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("action, query", [("get-by-name", {"name": "q"}), ("list", {})])
def test_reading_an_experiment_s_queues_requires_read(prefix, action, query):
    assert denied(hook(_rq(prefix, action), "GET", OUTSIDER, query={"experiment_id": VICTIM, **query}))
    assert allowed(hook(_rq(prefix, action), "GET", READER, query={"experiment_id": VICTIM, **query}))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("action, extra", [("update", {"name": "renamed"}), ("items/add", {"item_ids": ["t"]}), ("items/remove", {"item_ids": ["t"]})])
def test_changing_a_queue_requires_update_on_its_experiment(prefix, action, extra):
    body = {"queue_id": "rq-victim", **extra}
    assert denied(hook(_rq(prefix, action), "POST", OUTSIDER, body=body))
    assert denied(hook(_rq(prefix, action), "POST", READER, body=body))
    assert allowed(hook(_rq(prefix, action), "POST", EDITOR, body=body))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_changing_a_queue_owner_requires_manage(prefix):
    body = {"queue_id": "rq-victim", "new_owner": EDITOR}
    assert denied(hook(_rq(prefix, "update"), "POST", EDITOR, body=body))
    assert allowed(hook(_rq(prefix, "update"), "POST", MANAGER, body=body))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_deleting_a_queue_requires_delete_on_its_experiment(prefix):
    assert denied(hook(_rq(prefix, "delete"), "POST", EDITOR, body={"queue_id": "rq-victim"}))
    assert allowed(hook(_rq(prefix, "delete"), "POST", MANAGER, body={"queue_id": "rq-victim"}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_setting_item_status_requires_update_and_the_caller_as_reviewer(prefix):
    path = _rq(prefix, "items/set-status")
    body = {"queue_id": "rq-victim", "item_id": "t", "status": "COMPLETED"}
    assert denied(hook(path, "POST", READER, body=body))
    assert allowed(hook(path, "POST", EDITOR, body=body))
    assert allowed(hook(path, "POST", EDITOR, body={**body, "completed_by": EDITOR}))
    assert denied(hook(path, "POST", EDITOR, body={**body, "completed_by": MANAGER}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_an_unknown_queue_is_not_served(prefix):
    resp = hook(_rq(prefix, "get"), "GET", MANAGER, query={"queue_id": "rq-missing"})
    assert resp is not None and resp.status_code in (403, 404)


@pytest.mark.parametrize("prefix", PREFIXES)
def test_a_second_experiment_in_the_query_string_is_authorized_too(prefix):
    body = {"experiment_id": OWN, "name": "q", "queue_type": "CUSTOM"}
    assert denied(hook(_rq(prefix, "create"), "POST", OUTSIDER, body=body, query={"experiment_id": VICTIM}))
