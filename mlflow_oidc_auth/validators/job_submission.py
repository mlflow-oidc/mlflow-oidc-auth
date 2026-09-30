"""Authorization of job submissions on MLflow's FastAPI job API (``POST /ajax-api/3.0/jobs/``).

The request names a job function (``job_name``) and the keyword arguments it runs with
(``params``). The job then acts on the experiments, runs, traces and other resources those
params name, so a non-admin submission is authorized against them, per job function:

* every experiment the job writes to, directly or through a run or trace it names, needs
  UPDATE, as does a prompt the job registers a new version of; an evaluation dataset the job
  only reads needs READ on its experiments;
* a trace, run or dataset that cannot be resolved denies;
* a gateway endpoint named as the model needs USE;
* a ``username`` param, which the job uses as its identity towards the gateway, must be
  absent or the caller.

A job function not listed here, a parameter a job function does not declare, or a value of
the wrong type denies. This covers the job functions MLflow 3.16.1 allows
(``mlflow.server.jobs._ALLOWED_JOB_NAME_LIST``); one added by a later release, or through
``_MLFLOW_ALLOWED_JOB_NAME_LIST``, is admin-only until it is classified here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.utils import effective_scorer_permission, get_run_experiment_id
from mlflow_oidc_auth.utils.permissions import can_use_gateway_endpoint
from mlflow_oidc_auth.validators._model_uri import is_gateway_provider, split_model_uri
from mlflow_oidc_auth.validators._experiment_scope import permission_on_all_experiments, trace_ids_permission
from mlflow_oidc_auth.validators.prompt_optimization_job import can_read_dataset_experiments, can_update_prompt_uri

logger = get_logger()


class _Unauthorized(Exception):
    """Raised inside a job check to deny the submission."""


def _require(condition: bool) -> None:
    if not condition:
        raise _Unauthorized


def _id(value: Any) -> str:
    """A resource id given as a non-empty string (or an integer, for experiment ids)."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise _Unauthorized
    text = str(value).strip()
    _require(bool(text))
    return text


def _ids(value: Any) -> list[str]:
    _require(isinstance(value, list))
    return [_id(v) for v in value]


def _update_on_experiment(experiment_id: Any, username: str) -> str:
    experiment_id = _id(experiment_id)
    _require(permission_on_all_experiments([experiment_id], username).can_update)
    return experiment_id


def _update_on_traces(trace_ids: Any, username: str) -> None:
    ids = _ids(trace_ids)
    if ids:
        _require(trace_ids_permission(ids, username).can_update)


def _update_on_run(run_id: Any, username: str) -> None:
    run_id = _id(run_id)
    try:
        experiment_id = get_run_experiment_id(_get_tracking_store(), run_id)
    except Exception:
        raise _Unauthorized
    _require(permission_on_all_experiments([experiment_id], username).can_update)


def _caller_or_absent(value: Any, username: str) -> None:
    _require(value is None or value == username)


def _gateway_model(model: Any, username: str) -> None:
    """A gateway model needs USE on the endpoint MLflow will call; another provider's model is
    unchecked, as on MLflow's ``issues/invoke`` route. A malformed model URI denies."""
    if model is None:
        return
    _require(isinstance(model, str) and bool(model))
    parsed = split_model_uri(model)
    _require(parsed is not None)
    provider, name = parsed
    if is_gateway_provider(provider):
        _require(can_use_gateway_endpoint(name, username))


def _check_invoke_scorer(params: dict[str, Any], username: str) -> None:
    _update_on_experiment(params.get("experiment_id"), username)
    _update_on_traces(params.get("trace_ids"), username)
    _caller_or_absent(params.get("username"), username)


def _check_online_scorer(params: dict[str, Any], username: str) -> None:
    experiment_id = _update_on_experiment(params.get("experiment_id"), username)
    online_scorers = params.get("online_scorers")
    _require(isinstance(online_scorers, list))
    for scorer in online_scorers:
        _require(isinstance(scorer, dict))
        name = _id(scorer.get("name"))
        _require(effective_scorer_permission(experiment_id=experiment_id, scorer_name=name, user=username).permission.can_update)


def _check_issue_detection(params: dict[str, Any], username: str) -> None:
    _update_on_experiment(params.get("experiment_id"), username)
    _update_on_traces(params.get("trace_ids"), username)
    _update_on_run(params.get("run_id"), username)
    _gateway_model(params.get("model"), username)


def _check_genai_evaluate(params: dict[str, Any], username: str) -> None:
    _update_on_run(params.get("run_id"), username)
    _update_on_traces(params.get("trace_ids"), username)
    if params.get("experiment_id") is not None:
        _update_on_experiment(params.get("experiment_id"), username)
    _caller_or_absent(params.get("username"), username)


def _check_optimize_prompts(params: dict[str, Any], username: str) -> None:
    _update_on_experiment(params.get("experiment_id"), username)
    _update_on_run(params.get("run_id"), username)
    # The job registers the optimized template as a new version of this prompt.
    _require(can_update_prompt_uri(params.get("prompt_uri"), username))
    dataset_id = params.get("dataset_id")
    if dataset_id:
        _require(can_read_dataset_experiments(dataset_id, username))


# job name -> (parameters the job function declares, check)
_JOB_CHECKS: dict[str, tuple[frozenset[str], Callable[[dict[str, Any], str], None]]] = {
    "invoke_scorer": (
        frozenset({"experiment_id", "serialized_scorer", "trace_ids", "log_assessments", "username", "scorer_version"}),
        _check_invoke_scorer,
    ),
    "run_online_trace_scorer": (frozenset({"experiment_id", "online_scorers"}), _check_online_scorer),
    "run_online_session_scorer": (frozenset({"experiment_id", "online_scorers"}), _check_online_scorer),
    "invoke_issue_detection": (frozenset({"experiment_id", "trace_ids", "categories", "run_id", "model"}), _check_issue_detection),
    "invoke_genai_evaluate": (
        frozenset({"trace_ids", "serialized_scorers", "run_id", "username", "scorer_versions", "experiment_id"}),
        _check_genai_evaluate,
    ),
    "optimize_prompts": (
        frozenset({"run_id", "experiment_id", "prompt_uri", "dataset_id", "optimizer_type", "optimizer_config", "scorer_names"}),
        _check_optimize_prompts,
    ),
}


def can_submit_job(payload: Any, username: str) -> bool:
    """Whether a non-admin ``username`` may submit the job described by ``payload``.

    Parameters:
        payload: The parsed JSON body of the submit request.
        username: The authenticated, non-admin caller.

    Returns:
        True only if the job function is known, every parameter is one it declares, and the
        caller holds the permission each named resource requires. False otherwise, including
        on any lookup error.
    """
    if not isinstance(payload, dict):
        return False
    job_name = payload.get("job_name")
    params = payload.get("params")
    if not isinstance(job_name, str) or not isinstance(params, dict):
        return False
    spec = _JOB_CHECKS.get(job_name)
    if spec is None:
        return False
    declared, check = spec
    if not set(params) <= declared:
        return False
    try:
        check(params, username)
    except _Unauthorized:
        return False
    except Exception:
        logger.debug("Job submission authorization failed on a lookup error")
        return False
    return True
