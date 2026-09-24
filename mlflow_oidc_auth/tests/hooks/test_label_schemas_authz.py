"""Label schemas (``/3.0/mlflow/label-schemas/*``) are scoped by their experiment.

READ to read, UPDATE to create or update, DELETE to delete. A schema that carries no
experiment id is readable by any authenticated user and writable only by an admin.
Driven through the real hook and permission store (see ``authz_harness``).
"""

from types import SimpleNamespace

import pytest
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

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

SCHEMAS = {"ls-victim": VICTIM, "ls-unscoped": None}


class _FakeTrackingStore(BaseFakeTrackingStore):
    def get_label_schema(self, schema_id):
        if schema_id not in SCHEMAS:
            raise MlflowException(f"Label schema '{schema_id}' not found", RESOURCE_DOES_NOT_EXIST)
        return SimpleNamespace(schema_id=schema_id, experiment_id=SCHEMAS[schema_id])


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    yield install_permission_store(tmp_path, monkeypatch, _FakeTrackingStore())
    flush_permission_cache()


def _ls(prefix, action):
    return f"{prefix}/3.0/mlflow/label-schemas/{action}"


@pytest.mark.parametrize("prefix", PREFIXES)
def test_create_requires_update_on_the_experiment(prefix):
    body = {"experiment_id": VICTIM, "name": "quality"}
    assert denied(hook(_ls(prefix, "create"), "POST", OUTSIDER, body=body))
    assert denied(hook(_ls(prefix, "create"), "POST", READER, body=body))
    assert allowed(hook(_ls(prefix, "create"), "POST", EDITOR, body=body))
    assert denied(hook(_ls(prefix, "create"), "POST", OUTSIDER, body={"experiment_id": OWN, "name": "q"}, query={"experiment_id": VICTIM}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_get_requires_read_on_the_schema_experiment(prefix):
    assert denied(hook(_ls(prefix, "get"), "GET", OUTSIDER, query={"schema_id": "ls-victim"}))
    assert allowed(hook(_ls(prefix, "get"), "GET", READER, query={"schema_id": "ls-victim"}))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("action, query", [("get-by-name", {"name": "quality"}), ("list", {})])
def test_reading_an_experiment_s_schemas_requires_read(prefix, action, query):
    assert denied(hook(_ls(prefix, action), "GET", OUTSIDER, query={"experiment_id": VICTIM, **query}))
    assert allowed(hook(_ls(prefix, action), "GET", READER, query={"experiment_id": VICTIM, **query}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_update_requires_update_on_the_schema_experiment(prefix):
    assert denied(hook(_ls(prefix, "update"), "PATCH", READER, body={"schema_id": "ls-victim", "name": "x"}))
    assert allowed(hook(_ls(prefix, "update"), "PATCH", EDITOR, body={"schema_id": "ls-victim", "name": "x"}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_delete_requires_delete_on_the_schema_experiment(prefix):
    assert denied(hook(_ls(prefix, "delete"), "DELETE", EDITOR, body={"schema_id": "ls-victim"}))
    assert allowed(hook(_ls(prefix, "delete"), "DELETE", MANAGER, body={"schema_id": "ls-victim"}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_a_schema_without_an_experiment_is_readable_but_admin_writable(prefix):
    assert allowed(hook(_ls(prefix, "get"), "GET", OUTSIDER, query={"schema_id": "ls-unscoped"}))
    assert denied(hook(_ls(prefix, "update"), "PATCH", MANAGER, body={"schema_id": "ls-unscoped", "name": "x"}))
    assert denied(hook(_ls(prefix, "delete"), "DELETE", MANAGER, body={"schema_id": "ls-unscoped"}))
    assert allowed(hook(_ls(prefix, "delete"), "DELETE", ADMIN, body={"schema_id": "ls-unscoped"}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_a_second_schema_id_in_the_query_string_is_authorized_too(prefix):
    assert denied(hook(_ls(prefix, "update"), "PATCH", OUTSIDER, body={"schema_id": "ls-unscoped", "name": "x"}, query={"schema_id": "ls-victim"}))
