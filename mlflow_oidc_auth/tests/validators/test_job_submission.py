"""Authorization of job submissions on MLflow's FastAPI job API, per job function.

Driven against the real permission store (see ``tests/hooks/authz_harness``); only MLflow's
tracking store is faked, to place traces, runs and datasets in experiments.
``DEFAULT_MLFLOW_PERMISSION`` is MANAGE, so every denial below comes from a grant.
"""

from types import SimpleNamespace

import pytest
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.tests.hooks.authz_harness import (
    EDITOR,
    OUTSIDER,
    OWN,
    READER,
    VICTIM,
    BaseFakeTrackingStore,
    install_permission_store,
)
from mlflow_oidc_auth.validators.job_submission import can_submit_job

TRACES = {"t-victim": VICTIM, "t-own": OWN}
RUNS = {"r-victim": VICTIM, "r-own": OWN}
DATASETS = {"d-victim": [VICTIM], "d-own": [OWN], "d-unlinked": []}


class _FakeTrackingStore(BaseFakeTrackingStore):
    def get_trace_info(self, trace_id):
        if trace_id not in TRACES:
            raise MlflowException("no trace", RESOURCE_DOES_NOT_EXIST)
        return SimpleNamespace(experiment_id=TRACES[trace_id])

    def get_run(self, run_id):
        if run_id not in RUNS:
            raise MlflowException("no run", RESOURCE_DOES_NOT_EXIST)
        return SimpleNamespace(info=SimpleNamespace(experiment_id=RUNS[run_id]))

    def get_dataset_experiment_ids(self, dataset_id):
        if dataset_id not in DATASETS:
            raise MlflowException("no dataset", RESOURCE_DOES_NOT_EXIST)
        return DATASETS[dataset_id]


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    s = install_permission_store(tmp_path, monkeypatch, _FakeTrackingStore())
    s.create_scorer_permission(OWN, "guarded", OUTSIDER, "NO_PERMISSIONS")
    s.create_registered_model_permission("hidden-prompt", OUTSIDER, "NO_PERMISSIONS")
    s.create_registered_model_permission("read-only-prompt", OUTSIDER, "READ")
    s.create_gateway_endpoint_permission("hidden-endpoint", OUTSIDER, "NO_PERMISSIONS")
    flush_permission_cache()
    yield s
    flush_permission_cache()


def _job(job_name, **params):
    return {"job_name": job_name, "params": params}


# --- invoke_scorer -----------------------------------------------------------------------


def _scorer(experiment_id=OWN, trace_ids=("t-own",), **extra):
    return _job("invoke_scorer", experiment_id=experiment_id, serialized_scorer="{}", trace_ids=list(trace_ids), log_assessments=True, **extra)


def test_invoke_scorer_on_own_experiment_and_traces_is_allowed():
    assert can_submit_job(_scorer(), OUTSIDER)
    assert can_submit_job(_scorer(username=OUTSIDER), OUTSIDER)


def test_invoke_scorer_needs_update_on_the_experiment():
    assert not can_submit_job(_scorer(experiment_id=VICTIM, trace_ids=()), OUTSIDER)
    assert not can_submit_job(_scorer(experiment_id=VICTIM, trace_ids=()), READER)
    assert can_submit_job(_scorer(experiment_id=VICTIM, trace_ids=()), EDITOR)


def test_invoke_scorer_needs_update_on_every_trace_experiment():
    assert not can_submit_job(_scorer(trace_ids=("t-own", "t-victim")), OUTSIDER)


def test_invoke_scorer_denies_an_unresolvable_trace():
    assert not can_submit_job(_scorer(trace_ids=("t-missing",)), OUTSIDER)


def test_invoke_scorer_username_must_be_the_caller():
    assert not can_submit_job(_scorer(username=EDITOR), OUTSIDER)


# --- online scorers ----------------------------------------------------------------------


@pytest.mark.parametrize("job_name", ["run_online_trace_scorer", "run_online_session_scorer"])
def test_online_scorer_jobs(job_name):
    def online(experiment_id, name):
        return _job(job_name, experiment_id=experiment_id, online_scorers=[{"name": name, "serialized_scorer": "{}", "online_config": {}}])

    assert can_submit_job(online(OWN, "judge"), OUTSIDER)
    assert not can_submit_job(online(OWN, "guarded"), OUTSIDER)
    assert not can_submit_job(online(VICTIM, "judge"), OUTSIDER)
    assert not can_submit_job(_job(job_name, experiment_id=OWN, online_scorers=[{"serialized_scorer": "{}"}]), OUTSIDER)


# --- issue detection ---------------------------------------------------------------------


def _issues(**overrides):
    params = {"experiment_id": OWN, "trace_ids": ["t-own"], "categories": ["c"], "run_id": "r-own", "model": "openai:/gpt"}
    params.update(overrides)
    return _job("invoke_issue_detection", **params)


def test_issue_detection():
    assert can_submit_job(_issues(), OUTSIDER)
    assert can_submit_job(_issues(model="gateway:/open-endpoint"), OUTSIDER)
    assert not can_submit_job(_issues(model="gateway:/hidden-endpoint"), OUTSIDER)


@pytest.mark.parametrize("model", ["gateway:/hidden-endpoint", "gateway://hidden-endpoint", "gateway:///hidden-endpoint", "Gateway:/hidden-endpoint"])
def test_issue_detection_checks_the_endpoint_mlflow_calls(model):
    # MLflow splits on the first ":/" and strips leading slashes, so all of these call hidden-endpoint.
    assert not can_submit_job(_issues(model=model), OUTSIDER)


@pytest.mark.parametrize("model", ["gateway:/open-endpoint", "gateway://open-endpoint", "gateway:///open-endpoint", "openai:/gpt"])
def test_issue_detection_allows_usable_models(model):
    assert can_submit_job(_issues(model=model), OUTSIDER)


@pytest.mark.parametrize("model", ["gateway:/", "gateway:///", "no-provider", ":/x", ""])
def test_issue_detection_denies_a_malformed_model(model):
    assert not can_submit_job(_issues(model=model), OUTSIDER)
    assert not can_submit_job(_issues(run_id="r-victim"), OUTSIDER)
    assert not can_submit_job(_issues(run_id="r-missing"), OUTSIDER)
    assert not can_submit_job(_issues(trace_ids=["t-victim"]), OUTSIDER)
    assert not can_submit_job(_issues(experiment_id=VICTIM), OUTSIDER)


# --- genai evaluate ----------------------------------------------------------------------


def _evaluate(**overrides):
    params = {"trace_ids": ["t-own"], "serialized_scorers": ["{}"], "run_id": "r-own"}
    params.update(overrides)
    return _job("invoke_genai_evaluate", **params)


def test_genai_evaluate():
    assert can_submit_job(_evaluate(), OUTSIDER)
    assert can_submit_job(_evaluate(experiment_id=OWN, username=OUTSIDER), OUTSIDER)
    assert not can_submit_job(_evaluate(run_id="r-victim"), OUTSIDER)
    assert not can_submit_job(_evaluate(trace_ids=["t-victim"]), OUTSIDER)
    assert not can_submit_job(_evaluate(experiment_id=VICTIM), OUTSIDER)
    assert not can_submit_job(_evaluate(username=EDITOR), OUTSIDER)
    assert not can_submit_job(_evaluate(run_id=None), OUTSIDER)


# --- prompt optimization -----------------------------------------------------------------


def _optimize(**overrides):
    params = {
        "run_id": "r-own",
        "experiment_id": OWN,
        "prompt_uri": "prompts:/open-prompt/1",
        "dataset_id": "d-own",
        "optimizer_type": "gepa",
        "optimizer_config": None,
        "scorer_names": ["Correctness"],
    }
    params.update(overrides)
    return _job("optimize_prompts", **params)


def test_optimize_prompts():
    assert can_submit_job(_optimize(), OUTSIDER)
    assert can_submit_job(_optimize(prompt_uri="prompts:/open-prompt@latest", dataset_id=""), OUTSIDER)
    assert not can_submit_job(_optimize(prompt_uri="prompts:/hidden-prompt/1"), OUTSIDER)
    # The job registers a new version of the prompt, so READ is not enough.
    assert not can_submit_job(_optimize(prompt_uri="prompts:/read-only-prompt/1"), OUTSIDER)
    assert not can_submit_job(_optimize(prompt_uri="models:/open-prompt/1"), OUTSIDER)
    assert not can_submit_job(_optimize(dataset_id="d-victim"), OUTSIDER)
    assert not can_submit_job(_optimize(dataset_id="d-unlinked"), OUTSIDER)
    assert not can_submit_job(_optimize(dataset_id="d-missing"), OUTSIDER)
    assert not can_submit_job(_optimize(experiment_id=VICTIM), OUTSIDER)
    assert not can_submit_job(_optimize(run_id="r-victim"), OUTSIDER)


# --- shape -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"params": {}},
        {"job_name": "invoke_scorer"},
        {"job_name": "invoke_scorer", "params": []},
        _job("some_future_job", experiment_id=OWN),
        _job("invoke_scorer", experiment_id=OWN, serialized_scorer="{}", trace_ids=[], unexpected=1),
        _job("invoke_scorer", experiment_id=OWN, serialized_scorer="{}", trace_ids="t-own"),
        _job("invoke_scorer", experiment_id={"id": OWN}, serialized_scorer="{}", trace_ids=[]),
        _job("invoke_scorer", serialized_scorer="{}", trace_ids=[]),
    ],
)
def test_unclassifiable_submissions_are_denied(payload):
    assert not can_submit_job(payload, OUTSIDER)


def test_every_job_mlflow_allows_is_classified():
    from mlflow.server.jobs import _ALLOWED_JOB_NAME_LIST

    from mlflow_oidc_auth.validators.job_submission import _JOB_CHECKS

    assert set(_ALLOWED_JOB_NAME_LIST) <= set(_JOB_CHECKS)


#: Parameters a job function gained in an MLflow release after the supported floor (3.16.0). The
#: validator declares them so that newer MLflow's jobs are not refused; on the floor the job
#: function does not take them, and a submission carrying one fails in MLflow, not here.
_ADDED_AFTER_FLOOR = {
    # MLflow 3.16.1
    "invoke_scorer": {"scorer_version"},
    "invoke_genai_evaluate": {"experiment_id", "scorer_versions"},
}


def test_declared_params_match_the_job_function_signatures():
    """Every parameter the installed job function takes is declared (else real jobs are refused),
    and a declared one it does not take is a known later addition (else the list has drifted)."""
    import inspect

    from mlflow.server.jobs.utils import _load_function, get_job_fn_fullname

    from mlflow_oidc_auth.validators.job_submission import _JOB_CHECKS

    for job_name, (declared, _check) in _JOB_CHECKS.items():
        fn = _load_function(get_job_fn_fullname(job_name))
        accepted = set(inspect.signature(fn).parameters)
        assert accepted <= declared, (job_name, accepted - declared)
        assert declared - accepted <= _ADDED_AFTER_FLOOR.get(job_name, set()), (job_name, declared - accepted)
