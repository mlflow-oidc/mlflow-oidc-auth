"""Issues and the UI's GenAI job routes are scoped by their experiment.

``issues`` (create/get/update/search): READ to read, UPDATE to write, via the issue's
experiment. ``issues/invoke`` and ``genai/evaluate/invoke`` start a job that writes a run
into the experiment and reads the given traces: UPDATE on the experiment, READ on every
trace's experiment, and for issue detection USE on a named gateway secret or endpoint.
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

EXPERIMENT_OF = {"iss-victim": VICTIM, "run-victim": VICTIM, "run-own": OWN, "tr-victim": VICTIM, "tr-own": OWN}


def _missing(kind, key):
    raise MlflowException(f"{kind} '{key}' not found", RESOURCE_DOES_NOT_EXIST)


class _FakeTrackingStore(BaseFakeTrackingStore):
    def get_issue(self, issue_id):
        return SimpleNamespace(experiment_id=EXPERIMENT_OF[issue_id]) if issue_id in EXPERIMENT_OF else _missing("Issue", issue_id)

    def get_run(self, run_id):
        return SimpleNamespace(info=SimpleNamespace(experiment_id=EXPERIMENT_OF[run_id], run_id=run_id)) if run_id in EXPERIMENT_OF else _missing("Run", run_id)

    def get_trace_info(self, trace_id):
        return SimpleNamespace(experiment_id=EXPERIMENT_OF[trace_id], trace_id=trace_id) if trace_id in EXPERIMENT_OF else _missing("Trace", trace_id)

    def get_secret_info(self, secret_id=None, **_):
        return SimpleNamespace(secret_name="shared-key") if secret_id == "sec-1" else _missing("Secret", secret_id)


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    yield install_permission_store(tmp_path, monkeypatch, _FakeTrackingStore())
    flush_permission_cache()


# ---------------------------------------------------------------------------
# Issue CRUD
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
def test_create_issue_requires_update_on_the_experiment(prefix):
    path = f"{prefix}/3.0/mlflow/issues"
    body = {"experiment_id": VICTIM, "name": "n", "description": "d"}
    assert denied(hook(path, "POST", OUTSIDER, body=body))
    assert denied(hook(path, "POST", READER, body=body))
    assert allowed(hook(path, "POST", EDITOR, body=body))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_create_issue_needs_read_on_the_source_run(prefix):
    path = f"{prefix}/3.0/mlflow/issues"
    body = {"experiment_id": OWN, "name": "n", "description": "d"}
    assert allowed(hook(path, "POST", OUTSIDER, body={**body, "source_run_id": "run-own"}))
    assert denied(hook(path, "POST", OUTSIDER, body={**body, "source_run_id": "run-victim"}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_create_issue_authorizes_an_experiment_in_the_query_string_too(prefix):
    body = {"experiment_id": OWN, "name": "n", "description": "d"}
    assert denied(hook(f"{prefix}/3.0/mlflow/issues", "POST", OUTSIDER, body=body, query={"experiment_id": VICTIM}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_create_issue_cannot_be_attributed_to_someone_else(prefix):
    path = f"{prefix}/3.0/mlflow/issues"
    body = {"experiment_id": VICTIM, "name": "n", "description": "d"}
    assert allowed(hook(path, "POST", EDITOR, body={**body, "created_by": EDITOR}))
    assert allowed(hook(path, "POST", EDITOR, body={**body, "created_by": f" {EDITOR.upper()} "}))
    assert denied(hook(path, "POST", EDITOR, body={**body, "created_by": MANAGER}))
    assert denied(hook(path, "POST", EDITOR, body={**body, "created_by": EDITOR}, query={"created_by": MANAGER}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_get_issue_requires_read_on_its_experiment(prefix):
    path = f"{prefix}/3.0/mlflow/issues/iss-victim"
    assert denied(hook(path, "GET", OUTSIDER))
    assert allowed(hook(path, "GET", READER))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_update_issue_requires_update_on_its_experiment(prefix):
    path = f"{prefix}/3.0/mlflow/issues/iss-victim"
    assert denied(hook(path, "PATCH", OUTSIDER, body={"name": "x"}))
    assert denied(hook(path, "PATCH", READER, body={"name": "x"}))
    assert allowed(hook(path, "PATCH", EDITOR, body={"name": "x"}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_search_issues_requires_read_on_the_experiment(prefix):
    path = f"{prefix}/3.0/mlflow/issues/search"
    assert denied(hook(path, "POST", OUTSIDER, body={"experiment_id": VICTIM}))
    assert allowed(hook(path, "POST", READER, body={"experiment_id": VICTIM}))
    assert denied(hook(path, "POST", OUTSIDER, body={"experiment_id": OWN}, query={"experiment_id": VICTIM}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_search_issues_across_all_experiments_is_admin_only(prefix):
    path = f"{prefix}/3.0/mlflow/issues/search"
    assert denied(hook(path, "POST", MANAGER, body={}))
    assert allowed(hook(path, "POST", ADMIN, body={}))


# ---------------------------------------------------------------------------
# Job-starting routes
# ---------------------------------------------------------------------------

ISSUE_INVOKE = "/ajax-api/3.0/mlflow/issues/invoke"
EVALUATE_INVOKE = "/ajax-api/3.0/mlflow/genai/evaluate/invoke"


def _detection(experiment_id, traces, **extra):
    return {"experiment_id": experiment_id, "trace_ids": traces, "categories": ["c"], "provider": "openai", "model": "m", **extra}


def _evaluation(experiment_id, traces):
    return {"experiment_id": experiment_id, "trace_ids": traces, "serialized_scorers": ["{}"]}


@pytest.mark.parametrize("path, make", [(ISSUE_INVOKE, _detection), (EVALUATE_INVOKE, _evaluation)])
def test_invoke_requires_update_on_the_experiment(path, make):
    assert denied(hook(path, "POST", READER, body=make(VICTIM, ["tr-victim"])))
    assert denied(hook(path, "POST", OUTSIDER, body=make(VICTIM, ["tr-own"])))
    assert allowed(hook(path, "POST", EDITOR, body=make(VICTIM, ["tr-victim"])))


@pytest.mark.parametrize("path, make", [(ISSUE_INVOKE, _detection), (EVALUATE_INVOKE, _evaluation)])
def test_invoke_requires_read_on_every_trace(path, make):
    """Writing into one's own experiment must not pull another tenant's traces into it."""
    assert allowed(hook(path, "POST", OUTSIDER, body=make(OWN, ["tr-own"])))
    assert denied(hook(path, "POST", OUTSIDER, body=make(OWN, ["tr-own", "tr-victim"])))
    assert denied(hook(path, "POST", OUTSIDER, body=make(OWN, ["tr-unknown"])))


@pytest.mark.parametrize("path, make", [(ISSUE_INVOKE, _detection), (EVALUATE_INVOKE, _evaluation)])
def test_invoke_without_an_experiment_is_admin_only(path, make):
    body = make(VICTIM, ["tr-victim"])
    del body["experiment_id"]
    assert denied(hook(path, "POST", MANAGER, body=body))
    assert allowed(hook(path, "POST", ADMIN, body=body))


@pytest.mark.parametrize("path, make", [(ISSUE_INVOKE, _detection), (EVALUATE_INVOKE, _evaluation)])
def test_invoke_authorizes_an_experiment_in_the_query_string_too(path, make):
    assert denied(hook(path, "POST", OUTSIDER, body=make(OWN, ["tr-own"]), query={"experiment_id": VICTIM}))


def test_issue_detection_needs_use_on_a_named_gateway_secret(permission_store):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    permission_store.create_gateway_secret_permission("shared-key", OUTSIDER, "NO_PERMISSIONS")
    flush_permission_cache()
    assert denied(hook(ISSUE_INVOKE, "POST", OUTSIDER, body=_detection(OWN, ["tr-own"], secret_id="sec-1")))
    assert denied(hook(ISSUE_INVOKE, "POST", OUTSIDER, body=_detection(OWN, ["tr-own"], secret_id="sec-unknown")))
    assert allowed(hook(ISSUE_INVOKE, "POST", EDITOR, body=_detection(VICTIM, ["tr-victim"], secret_id="sec-1")))


def test_issue_detection_needs_use_on_a_named_gateway_endpoint(permission_store):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    permission_store.create_gateway_endpoint_permission("shared-endpoint", OUTSIDER, "NO_PERMISSIONS")
    flush_permission_cache()
    assert denied(hook(ISSUE_INVOKE, "POST", OUTSIDER, body=_detection(OWN, ["tr-own"], endpoint_name="shared-endpoint")))
    assert allowed(hook(ISSUE_INVOKE, "POST", EDITOR, body=_detection(VICTIM, ["tr-victim"], endpoint_name="shared-endpoint")))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_search_issues_scope_only_in_the_query_string_does_not_count(prefix):
    """MLflow reads the POST body only; with no experiment there it searches every experiment."""
    assert denied(hook(f"{prefix}/3.0/mlflow/issues/search", "POST", READER, body={}, query={"experiment_id": VICTIM}))
