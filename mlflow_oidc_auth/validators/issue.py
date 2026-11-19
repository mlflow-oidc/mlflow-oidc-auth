"""Validators for MLflow issues and the UI's asynchronous GenAI jobs.

An issue belongs to one experiment and inherits its permission. The two ``invoke`` routes
(``issues/invoke`` and ``genai/evaluate/invoke``) start a background job that creates a run
in the experiment and reads the traces it is given, so they need UPDATE on the experiment and
READ on the experiment of every trace. ``issues/invoke`` can also run on a stored gateway
secret or through a gateway endpoint; it then needs USE on that secret or endpoint. So does a
recurring detection schedule (MLflow 3.18), which an experiment tag carries, model included.
"""

from __future__ import annotations

from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.permissions import NO_PERMISSIONS, Permission
from mlflow_oidc_auth.utils import all_source_values, get_request_param_values, request_body_dict
from mlflow_oidc_auth.validators._detection_schedule import can_use_endpoint_name, can_use_secret_id, secret_supplies_provider_credentials
from mlflow_oidc_auth.validators._experiment_scope import names_only_caller, permission_on_all_experiments, trace_ids_permission, values_mlflow_also_reads
from mlflow_oidc_auth.validators.run import _permission_for_run


def _issue_permission(username: str) -> Permission:
    # issue_id is a path parameter; any other value in the query or body is authorized too.
    tracking_store = _get_tracking_store()
    experiment_ids = [tracking_store.get_issue(str(issue_id)).experiment_id for issue_id in get_request_param_values("issue_id")]
    return permission_on_all_experiments(experiment_ids, username)


def validate_can_read_issue(username: str) -> bool:
    """READ on the issue's experiment."""
    return _issue_permission(username).can_read


def validate_can_update_issue(username: str) -> bool:
    """UPDATE on the issue's experiment."""
    return _issue_permission(username).can_update


def validate_can_create_issue(username: str) -> bool:
    """UPDATE on the experiment, READ on the source run when one is named, and ``created_by``
    absent or the caller (MLflow stores it verbatim as the issue's author)."""
    if not names_only_caller("created_by", username):
        return False
    if not permission_on_all_experiments(get_request_param_values("experiment_id"), username).can_update:
        return False
    return all(_permission_for_run(str(run_id), username).can_read for run_id in all_source_values("source_run_id"))


def validate_can_search_issues(username: str) -> bool:
    """READ on the experiment; MLflow searches every experiment when none is given, so that is refused."""
    return permission_on_all_experiments(values_mlflow_also_reads("experiment_id"), username).can_read


def _job_request_permission(username: str) -> Permission:
    """UPDATE-level check shared by both invoke routes: experiment plus every trace."""
    experiment_permission = permission_on_all_experiments(all_source_values("experiment_id"), username)
    if not experiment_permission.can_update:
        return NO_PERMISSIONS
    trace_ids = all_source_values("trace_ids")
    if trace_ids and not trace_ids_permission(trace_ids, username).can_read:
        return NO_PERMISSIONS
    return experiment_permission


def _names_own_credentials() -> bool:
    """Whether the ``issues/invoke`` body names an endpoint or a secret, as MLflow reads it.

    MLflow runs the job on the server's own provider credentials exactly when the JSON body it
    validates has neither ``endpoint_name`` nor ``secret_id``, so the decision reads that body and
    nothing else.
    """
    body = request_body_dict()
    return isinstance(body, dict) and bool(body.get("endpoint_name") or body.get("secret_id"))


def validate_can_invoke_issue_detection(username: str) -> bool:
    """UPDATE on the experiment, READ on every trace, USE on any named secret or endpoint.

    A named secret must also carry the provider's credentials itself (see
    ``secret_supplies_provider_credentials``), or the job would mix in the server's own.

    With ``ISSUE_DETECTION_SERVER_CREDENTIALS_ADMIN_ONLY`` on, a request naming neither a secret
    nor an endpoint (so MLflow would use the server's own provider credentials) is refused too.
    """
    if not _job_request_permission(username).can_update:
        return False
    if config.ISSUE_DETECTION_SERVER_CREDENTIALS_ADMIN_ONLY and not _names_own_credentials():
        return False
    if not all(can_use_secret_id(secret_id, username) for secret_id in all_source_values("secret_id")):
        return False
    # MLflow reads the body: a secret it would load must carry the provider's credentials itself.
    body = request_body_dict()
    # With an endpoint named, MLflow runs the job on that gateway endpoint and the secret's values go unused.
    # MLflow's handler reads only the snake_case JSON keys (pinned by a test), so those are the
    # ones checked here. It runs on the named endpoint when one is given; only a blank one leaves
    # the secret in use.
    endpoint_name = body.get("endpoint_name") if isinstance(body, dict) else None
    if (
        isinstance(body, dict)
        and body.get("secret_id")
        and not (isinstance(endpoint_name, str) and endpoint_name.strip())
        and not secret_supplies_provider_credentials(body.get("provider"), body.get("secret_id"))
    ):
        return False
    return all(can_use_endpoint_name(name, username) for name in all_source_values("endpoint_name"))


def validate_can_sync_issue_detection_schedule(username: str) -> bool:
    """UPDATE on the experiment whose detection schedule state MLflow recomputes and writes.

    ``POST issues/schedule/state`` (MLflow 3.18) reads the experiment's stored detection schedule
    and writes its dispatch state back as experiment tags, the same write the schedule dialog makes
    through the tag endpoint just before. No experiment named denies.
    """
    return permission_on_all_experiments(all_source_values("experiment_id"), username).can_update


def validate_can_invoke_genai_evaluate(username: str) -> bool:
    """UPDATE on the experiment and READ on the experiment of every trace evaluated."""
    return _job_request_permission(username).can_update
