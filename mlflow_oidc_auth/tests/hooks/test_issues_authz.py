"""Issues and the UI's GenAI job routes are scoped by their experiment.

``issues`` (create/get/update/search): READ to read, UPDATE to write, via the issue's
experiment. ``issues/invoke`` and ``genai/evaluate/invoke`` start a job that writes a run
into the experiment and reads the given traces: UPDATE on the experiment, READ on every
trace's experiment, and for issue detection USE on a named gateway secret or endpoint.
Driven through the real hook and permission store (see ``authz_harness``).
"""

import os
from pathlib import Path
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

    # Secret values are placeholders, never credentials. "sec-base-only" lacks the provider's API key.
    SECRETS = {
        "sec-1": ("shared-key", {"api_key": "placeholder-value"}, {}),
        "sec-base-only": ("base-only", {}, {"api_base": "https://example.invalid/v1"}),
    }

    def get_secret_info(self, secret_id=None, **_):
        if secret_id not in self.SECRETS:
            _missing("Secret", secret_id)
        name, _value, auth_config = self.SECRETS[secret_id]
        return SimpleNamespace(secret_name=name, auth_config=auth_config)

    def _get_decrypted_secret(self, secret_id):
        if secret_id not in self.SECRETS:
            _missing("Secret", secret_id)
        return dict(self.SECRETS[secret_id][1])


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


@pytest.mark.parametrize("endpoint_name", ["/shared-endpoint", "//shared-endpoint"])
def test_issue_detection_checks_the_endpoint_mlflow_calls(permission_store, endpoint_name):
    """MLflow calls ``gateway:/<endpoint_name>`` with leading slashes stripped from the name."""
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    permission_store.create_gateway_endpoint_permission("shared-endpoint", OUTSIDER, "NO_PERMISSIONS")
    flush_permission_cache()
    assert denied(hook(ISSUE_INVOKE, "POST", OUTSIDER, body=_detection(OWN, ["tr-own"], endpoint_name=endpoint_name)))
    assert allowed(hook(ISSUE_INVOKE, "POST", OUTSIDER, body=_detection(OWN, ["tr-own"], endpoint_name="/open-endpoint")))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_search_issues_scope_only_in_the_query_string_does_not_count(prefix):
    """MLflow reads the POST body only; with no experiment there it searches every experiment."""
    assert denied(hook(f"{prefix}/3.0/mlflow/issues/search", "POST", READER, body={}, query={"experiment_id": VICTIM}))


SCHEDULE_STATE = "/ajax-api/3.0/mlflow/issues/schedule/state"


@pytest.fixture
def schedule_state_route():
    """The route exists from MLflow 3.18; on an older MLflow there is nothing to authorize."""
    from mlflow_oidc_auth.hooks.before_request import BEFORE_REQUEST_VALIDATORS

    if not any(path.endswith("mlflow/issues/schedule/state") for path, _ in BEFORE_REQUEST_VALIDATORS):
        pytest.skip("MLflow's issue detection schedule arrived in 3.18")


def test_syncing_a_detection_schedule_needs_update_on_the_experiment(schedule_state_route):
    assert allowed(hook(SCHEDULE_STATE, "POST", EDITOR, body={"experiment_id": VICTIM}))
    assert denied(hook(SCHEDULE_STATE, "POST", READER, body={"experiment_id": VICTIM}))
    assert denied(hook(SCHEDULE_STATE, "POST", OUTSIDER, body={"experiment_id": VICTIM}))
    assert allowed(hook(SCHEDULE_STATE, "POST", OUTSIDER, body={"experiment_id": OWN}))


def test_syncing_a_detection_schedule_without_an_experiment_is_admin_only(schedule_state_route):
    assert denied(hook(SCHEDULE_STATE, "POST", MANAGER, body={}))
    assert allowed(hook(SCHEDULE_STATE, "POST", ADMIN, body={}))


def test_syncing_a_detection_schedule_authorizes_the_query_string_too(schedule_state_route):
    assert denied(hook(SCHEDULE_STATE, "POST", OUTSIDER, body={"experiment_id": OWN}, query={"experiment_id": VICTIM}))


@pytest.mark.parametrize(
    "user, body, query, expected",
    [
        (EDITOR, {"experiment_id": VICTIM}, None, True),
        (READER, {"experiment_id": VICTIM}, None, False),
        (OUTSIDER, {"experiment_id": VICTIM}, None, False),
        (OUTSIDER, {"experiment_id": OWN}, None, True),
        (OUTSIDER, {"experiment_id": OWN}, {"experiment_id": VICTIM}, False),
        (OUTSIDER, {"experimentId": VICTIM, "experiment_id": OWN}, None, False),
        (MANAGER, {}, None, False),
    ],
)
def test_the_schedule_state_validator_on_any_mlflow(user, body, query, expected):
    """The validator itself, so it is exercised where MLflow predates the route (3.16, 3.17) too."""
    from mlflow.server import app

    from mlflow_oidc_auth.validators import validate_can_sync_issue_detection_schedule

    with app.test_request_context(SCHEDULE_STATE, method="POST", json=body, query_string=query or {}):
        assert validate_can_sync_issue_detection_schedule(user) is expected


# --- the recurring detection schedule (MLflow 3.18) -------------------------------------------
SET_EXPERIMENT_TAG = "/api/2.0/mlflow/experiments/set-experiment-tag"
CREATE_EXPERIMENT = "/api/2.0/mlflow/experiments/create"
SCHEDULE_TAG = "mlflow.issueDetection.schedule"


def _schedule(model):
    import json

    return json.dumps({"version": 1, "cadence": "daily", "model": model})


@pytest.fixture
def shared_gateway_denied(permission_store):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    permission_store.create_gateway_secret_permission("shared-key", OUTSIDER, "NO_PERMISSIONS")
    permission_store.create_gateway_endpoint_permission("shared-endpoint", OUTSIDER, "NO_PERMISSIONS")
    flush_permission_cache()


@pytest.mark.parametrize(
    "model",
    [
        {"provider": "openai", "model": "m", "secretId": "sec-1"},
        {"provider": "openai", "model": "m", "secretId": "sec-unknown"},
        {"endpointName": "shared-endpoint"},
        {"endpointName": "/shared-endpoint"},
        {"endpointName": " shared-endpoint "},
        {"provider": "gateway", "model": "shared-endpoint"},
        {"provider": " GATEWAY ", "model": "/shared-endpoint"},
        {"endpointName": "shared-endpoint", "secretId": "sec-1"},
        {"endpointName": ["shared-endpoint"]},
        "gateway:/shared-endpoint",
    ],
)
def test_a_schedule_tag_needs_use_on_the_model_it_runs_on(shared_gateway_denied, model):
    """The scheduler runs on the tag's endpoint or decrypted secret: editing one's own experiment is not enough."""
    body = {"experiment_id": OWN, "key": SCHEDULE_TAG, "value": _schedule(model)}
    assert denied(hook(SET_EXPERIMENT_TAG, "POST", OUTSIDER, body=body))
    assert denied(hook(CREATE_EXPERIMENT, "POST", OUTSIDER, body={"name": "mine", "tags": [{"key": SCHEDULE_TAG, "value": _schedule(model)}]}))


def test_a_schedule_tag_on_a_usable_model_is_allowed(shared_gateway_denied):
    for model in ({"provider": "openai", "model": "m", "secretId": "sec-1"}, {"endpointName": "shared-endpoint"}, {"provider": "openai", "model": "m"}):
        assert allowed(hook(SET_EXPERIMENT_TAG, "POST", EDITOR, body={"experiment_id": VICTIM, "key": SCHEDULE_TAG, "value": _schedule(model)}))
    # No model, or one MLflow will not run: the server's default, nothing named.
    assert allowed(hook(SET_EXPERIMENT_TAG, "POST", OUTSIDER, body={"experiment_id": OWN, "key": SCHEDULE_TAG, "value": _schedule(None)}))
    assert allowed(hook(CREATE_EXPERIMENT, "POST", OUTSIDER, body={"name": "mine", "tags": [{"key": SCHEDULE_TAG, "value": _schedule(None)}]}))


def test_a_schedule_tag_still_needs_update_on_the_experiment(shared_gateway_denied):
    assert denied(hook(SET_EXPERIMENT_TAG, "POST", READER, body={"experiment_id": VICTIM, "key": SCHEDULE_TAG, "value": _schedule(None)}))


def test_a_second_copy_of_the_key_or_value_cannot_hide_the_schedule(shared_gateway_denied):
    denied_value = _schedule({"endpointName": "shared-endpoint"})
    assert denied(
        hook(
            SET_EXPERIMENT_TAG,
            "POST",
            OUTSIDER,
            body={"experiment_id": OWN, "key": "harmless", "value": _schedule(None)},
            query={"key": SCHEDULE_TAG, "value": denied_value},
        )
    )


def test_other_experiment_tags_are_unaffected(shared_gateway_denied):
    body = {"experiment_id": OWN, "key": "note", "value": _schedule({"endpointName": "shared-endpoint"})}
    assert allowed(hook(SET_EXPERIMENT_TAG, "POST", OUTSIDER, body=body))


@pytest.mark.parametrize("value", ["not json", "[]", '"a string"'])
def test_a_schedule_tag_that_is_not_a_schedule_envelope_is_refused(shared_gateway_denied, value):
    """Every schedule MLflow writes is a JSON object; anything else has no use but to slip past a parser."""
    assert denied(hook(SET_EXPERIMENT_TAG, "POST", OUTSIDER, body={"experiment_id": OWN, "key": SCHEDULE_TAG, "value": value}))


@pytest.mark.parametrize(
    "envelope",
    [
        {"version": 2, "cadence": "daily", "model": {"endpointName": "shared-endpoint"}},
        {"version": 1, "cadence": "fortnightly", "model": {"provider": "openai", "model": "m", "secretId": "sec-1"}},
    ],
)
def test_a_schedule_this_mlflow_would_not_run_is_still_checked(shared_gateway_denied, envelope):
    """A later MLflow may run an envelope this one ignores, and on 3.16/3.17 there is no scheduler yet."""
    import json

    assert denied(hook(SET_EXPERIMENT_TAG, "POST", OUTSIDER, body={"experiment_id": OWN, "key": SCHEDULE_TAG, "value": json.dumps(envelope)}))


def test_a_scheduler_module_that_cannot_be_loaded_denies(shared_gateway_denied, monkeypatch):
    """MLflow internals moving must not switch the check off."""
    from mlflow_oidc_auth.validators import _detection_schedule

    def broken():
        raise ImportError("parse_detection_schedule moved")

    monkeypatch.setattr(_detection_schedule, "_mlflow_schedule_parser", broken)
    assert denied(hook(SET_EXPERIMENT_TAG, "POST", EDITOR, body={"experiment_id": VICTIM, "key": SCHEDULE_TAG, "value": _schedule(None)}))


def test_the_scheduler_module_is_absent_only_when_mlflow_has_none(monkeypatch):
    from mlflow_oidc_auth.validators import _detection_schedule

    monkeypatch.setattr(_detection_schedule, "_SCHEDULE_MODULE", "mlflow.no_such_package.schedule")
    assert _detection_schedule._mlflow_schedule_parser() is None


def test_the_scheduler_parser_decides_when_mlflow_has_one(shared_gateway_denied, monkeypatch):
    """Where the stored envelope looks harmless but MLflow's parser reads a gateway model, the parser wins."""
    from types import SimpleNamespace

    from mlflow_oidc_auth.validators import _detection_schedule

    parsed = SimpleNamespace(model=SimpleNamespace(secret_id="", to_model_uri=lambda: "gateway:/shared-endpoint"))
    monkeypatch.setattr(_detection_schedule, "_mlflow_schedule_parser", lambda: lambda raw: parsed)
    assert denied(hook(SET_EXPERIMENT_TAG, "POST", OUTSIDER, body={"experiment_id": OWN, "key": SCHEDULE_TAG, "value": _schedule(None)}))


def test_a_create_body_naming_the_schedule_tag_that_cannot_be_read_denies(shared_gateway_denied, monkeypatch):
    from mlflow_oidc_auth.validators import experiment

    monkeypatch.setattr(experiment, "request_body_dict", lambda: {})
    body = {"name": "mine", "tags": [{"key": SCHEDULE_TAG, "value": _schedule(None)}]}
    assert denied(hook(CREATE_EXPERIMENT, "POST", OUTSIDER, body=body))
    assert allowed(hook(CREATE_EXPERIMENT, "POST", OUTSIDER, body={"name": "mine", "tags": [{"key": "note", "value": "v"}]}))


# --- a named secret must carry the provider's credentials itself ------------------------------


def test_issue_detection_refuses_a_secret_without_the_providers_key():
    """A named secret must carry the provider's API key itself."""
    assert denied(hook(ISSUE_INVOKE, "POST", EDITOR, body=_detection(VICTIM, ["tr-victim"], secret_id="sec-base-only")))
    assert allowed(hook(ISSUE_INVOKE, "POST", EDITOR, body=_detection(VICTIM, ["tr-victim"], secret_id="sec-1")))


@pytest.mark.parametrize("provider, expected", [("openai", True), ("OpenAI", True), ("anthropic", True), ("bedrock", False), ("no-such-provider", False)])
def test_issue_detection_reads_the_secret_as_the_provider_mlflow_loads_it_for(provider, expected):
    body = {**_detection(VICTIM, ["tr-victim"], secret_id="sec-1"), "provider": provider}
    assert allowed(hook(ISSUE_INVOKE, "POST", EDITOR, body=body)) is expected


def test_issue_detection_does_not_read_a_secret_an_endpoint_makes_unused():
    """MLflow runs on the named endpoint, so only USE on the secret and endpoint is checked."""
    body = _detection(VICTIM, ["tr-victim"], secret_id="sec-base-only", endpoint_name="shared-endpoint")
    assert allowed(hook(ISSUE_INVOKE, "POST", EDITOR, body=body))


def test_a_blank_endpoint_name_does_not_skip_the_secrets_credentials():
    body = _detection(VICTIM, ["tr-victim"], secret_id="sec-base-only", endpoint_name="  ")
    assert denied(hook(ISSUE_INVOKE, "POST", EDITOR, body=body))


def test_a_schedule_on_an_endpoint_does_not_read_the_secret_it_also_names():
    model = {"endpointName": "shared-endpoint", "provider": "openai", "model": "m", "secretId": "sec-base-only"}
    assert allowed(hook(SET_EXPERIMENT_TAG, "POST", EDITOR, body={"experiment_id": VICTIM, "key": SCHEDULE_TAG, "value": _schedule(model)}))


def test_a_schedule_write_decrypts_each_secret_once(monkeypatch):
    reads = []
    real = _FakeTrackingStore._get_decrypted_secret

    def counting(self, secret_id):
        reads.append(secret_id)
        return real(self, secret_id)

    monkeypatch.setattr(_FakeTrackingStore, "_get_decrypted_secret", counting)
    model = {"provider": "openai", "model": "m", "secretId": "sec-1"}
    assert allowed(hook(SET_EXPERIMENT_TAG, "POST", EDITOR, body={"experiment_id": VICTIM, "key": SCHEDULE_TAG, "value": _schedule(model)}))
    assert reads == ["sec-1"]


def test_the_provider_is_read_as_mlflow_reads_it():
    """MLflow lower-cases the provider and nothing else, so a padded one is an unknown provider."""
    body = {**_detection(VICTIM, ["tr-victim"], secret_id="sec-1"), "provider": "openai "}
    assert denied(hook(ISSUE_INVOKE, "POST", EDITOR, body=body))


def test_issue_detection_refuses_a_secret_mlflow_cannot_read(monkeypatch):
    def unreadable(self, secret_id):
        raise RuntimeError("cannot decrypt")

    monkeypatch.setattr(_FakeTrackingStore, "_get_decrypted_secret", unreadable)
    assert denied(hook(ISSUE_INVOKE, "POST", EDITOR, body=_detection(VICTIM, ["tr-victim"], secret_id="sec-1")))


def test_a_schedule_refuses_a_secret_without_the_providers_key(shared_gateway_denied):
    for model in ({"provider": "openai", "model": "m", "secretId": "sec-base-only"}, {"provider": "bedrock", "model": "m", "secretId": "sec-1"}):
        body = {"experiment_id": VICTIM, "key": SCHEDULE_TAG, "value": _schedule(model)}
        assert denied(hook(SET_EXPERIMENT_TAG, "POST", EDITOR, body=body))
        assert denied(hook(CREATE_EXPERIMENT, "POST", EDITOR, body={"name": "mine", "tags": [{"key": SCHEDULE_TAG, "value": _schedule(model)}]}))
    assert allowed(
        hook(
            SET_EXPERIMENT_TAG,
            "POST",
            EDITOR,
            body={"experiment_id": VICTIM, "key": SCHEDULE_TAG, "value": _schedule({"provider": "openai", "model": "m", "secretId": "sec-1"})},
        )
    )


def test_the_required_credential_variables_follow_mlflows_provider_table():
    from mlflow_oidc_auth.validators._detection_schedule import _required_credential_variables

    assert _required_credential_variables({"api_key": "OPENAI_API_KEY", "api_base": "OPENAI_API_BASE"}) == {"OPENAI_API_KEY"}
    assert _required_credential_variables("ANTHROPIC_API_KEY") == {"ANTHROPIC_API_KEY"}
    assert _required_credential_variables(
        {"aws_access_key_id": "AWS_ACCESS_KEY_ID", "aws_secret_access_key": "AWS_SECRET_ACCESS_KEY", "aws_session_token": "AWS_SESSION_TOKEN"}
    ) == {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"}
    assert _required_credential_variables(None) == set()


def test_reading_a_secret_first_keeps_mlflows_job_map_whole(tmp_path):
    """The check must not be the first import of MLflow's job module: in a fresh process that
    drops issue detection from MLflow's job-name map, and every detection job is then refused."""
    import subprocess
    import sys

    script = (
        "from mlflow_oidc_auth.validators._detection_schedule import secret_supplies_provider_credentials\n"
        "secret_supplies_provider_credentials('openai', 'no-such-secret')\n"
        "from mlflow.server.jobs.utils import get_job_fn_fullname\n"
        "print(get_job_fn_fullname('invoke_issue_detection'))\n"
    )
    repo_root = str(Path(__file__).resolve().parents[3])
    env = {
        **os.environ,
        "MLFLOW_DISABLE_AGENT_HINT": "1",
        "MLFLOW_TRACKING_URI": f"sqlite:///{tmp_path / 'mlflow.db'}",
        "PYTHONPATH": os.pathsep.join(filter(None, [repo_root, os.environ.get("PYTHONPATH")])),
    }
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120, cwd=tmp_path, env=env)
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.strip().endswith("invoke_issue_detection_job")


<<<<<<< HEAD
# --- ISSUE_DETECTION_SERVER_CREDENTIALS_ADMIN_ONLY ---------------------------------------------


@pytest.fixture
def server_credentials_admin_only(monkeypatch):
    from mlflow_oidc_auth.config import config

    monkeypatch.setattr(config, "ISSUE_DETECTION_SERVER_CREDENTIALS_ADMIN_ONLY", True)


def test_invoke_on_server_credentials_is_admin_only_when_configured(server_credentials_admin_only):
    assert denied(hook(ISSUE_INVOKE, "POST", EDITOR, body=_detection(VICTIM, ["tr-victim"])))
    assert denied(hook(ISSUE_INVOKE, "POST", EDITOR, body=_detection(VICTIM, ["tr-victim"], secret_id="", endpoint_name="")))
    assert allowed(hook(ISSUE_INVOKE, "POST", EDITOR, body=_detection(VICTIM, ["tr-victim"], secret_id="sec-1")))
    assert allowed(hook(ISSUE_INVOKE, "POST", EDITOR, body=_detection(VICTIM, ["tr-victim"], endpoint_name="shared-endpoint")))
    assert allowed(hook(ISSUE_INVOKE, "POST", ADMIN, body=_detection(VICTIM, ["tr-victim"])))


def test_invoke_on_server_credentials_reads_the_body_mlflow_reads(server_credentials_admin_only):
    """MLflow decides from the JSON body alone: a secret or endpoint in the query string does not count."""
    body = _detection(VICTIM, ["tr-victim"])
    assert denied(hook(ISSUE_INVOKE, "POST", EDITOR, body=body, query={"secret_id": "sec-1"}))
    assert denied(hook(ISSUE_INVOKE, "POST", EDITOR, body=body, query={"endpoint_name": "shared-endpoint"}))


def test_invoke_on_server_credentials_is_open_by_default():
    assert allowed(hook(ISSUE_INVOKE, "POST", EDITOR, body=_detection(VICTIM, ["tr-victim"])))


@pytest.mark.parametrize(
    "model",
    [None, {"provider": "openai", "model": "m"}, {"provider": "openai", "model": "m", "secretId": ""}, "not-an-object"],
)
def test_a_schedule_on_server_credentials_is_admin_only_when_configured(server_credentials_admin_only, model):
    body = {"experiment_id": VICTIM, "key": SCHEDULE_TAG, "value": _schedule(model)}
    assert denied(hook(SET_EXPERIMENT_TAG, "POST", EDITOR, body=body))
    assert denied(hook(CREATE_EXPERIMENT, "POST", EDITOR, body={"name": "mine", "tags": [{"key": SCHEDULE_TAG, "value": _schedule(model)}]}))
    assert allowed(hook(SET_EXPERIMENT_TAG, "POST", ADMIN, body=body))


@pytest.mark.parametrize(
    "model",
    [{"provider": "openai", "model": "m", "secretId": "sec-1"}, {"endpointName": "shared-endpoint"}, {"provider": "gateway", "model": "shared-endpoint"}],
)
def test_a_schedule_on_its_own_credential_is_allowed_when_configured(server_credentials_admin_only, model):
    assert allowed(hook(SET_EXPERIMENT_TAG, "POST", EDITOR, body={"experiment_id": VICTIM, "key": SCHEDULE_TAG, "value": _schedule(model)}))


def test_a_schedule_the_parser_reads_as_server_credentials_is_refused(server_credentials_admin_only, monkeypatch):
    """The envelope names a secret, but the parser MLflow runs reads none: the parser's reading counts too."""
    from types import SimpleNamespace

    from mlflow_oidc_auth.validators import _detection_schedule

    parsed = SimpleNamespace(paused=False, model=SimpleNamespace(endpoint_name="", provider="openai", secret_id="", to_model_uri=lambda: "openai:/m"))
    monkeypatch.setattr(_detection_schedule, "_mlflow_schedule_parser", lambda: lambda raw: parsed)
    body = {"experiment_id": VICTIM, "key": SCHEDULE_TAG, "value": _schedule({"provider": "openai", "model": "m", "secretId": "sec-1"})}
    assert denied(hook(SET_EXPERIMENT_TAG, "POST", EDITOR, body=body))
=======
def test_mlflows_invoke_handler_reads_only_the_snake_case_credential_keys():
    """The credential check reads ``secret_id`` / ``endpoint_name`` / ``provider`` from the JSON
    body because that is all MLflow reads; another spelling or source must fail here first."""
    import inspect
    import re

    from mlflow.server import handlers

    source = inspect.getsource(inspect.unwrap(handlers._invoke_issue_detection_handler))
    assert set(re.findall(r'request_json\.get\("([A-Za-z_]+)"\)', source)) >= {"secret_id", "endpoint_name", "provider"}
    for spelling in ("secretId", "endpointName", "request.args", "request.form", "request.values"):
        assert spelling not in source, spelling
>>>>>>> origin/fix/secret-provider-credentials
