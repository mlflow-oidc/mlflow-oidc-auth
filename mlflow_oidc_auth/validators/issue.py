"""Validators for MLflow issues and the UI's asynchronous GenAI jobs.

An issue belongs to one experiment and inherits its permission. The two ``invoke`` routes
(``issues/invoke`` and ``genai/evaluate/invoke``) start a background job that creates a run
in the experiment and reads the traces it is given, so they need UPDATE on the experiment and
READ on the experiment of every trace. ``issues/invoke`` can also run on a stored gateway
secret or through a gateway endpoint; it then needs USE on that secret or endpoint.
"""

from __future__ import annotations

from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.permissions import NO_PERMISSIONS, Permission
from mlflow_oidc_auth.utils import all_source_values, get_request_param_values
from mlflow_oidc_auth.utils.permissions import can_use_gateway_endpoint, can_use_gateway_secret
from mlflow_oidc_auth.validators._experiment_scope import names_only_caller, permission_on_all_experiments, trace_ids_permission, values_mlflow_also_reads
from mlflow_oidc_auth.validators.gateway import _resolve_secret_name_from_id
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


def validate_can_invoke_issue_detection(username: str) -> bool:
    """UPDATE on the experiment, READ on every trace, USE on any named secret or endpoint."""
    if not _job_request_permission(username).can_update:
        return False
    for secret_id in all_source_values("secret_id"):
        secret_name = _resolve_secret_name_from_id(str(secret_id))
        if not secret_name or not can_use_gateway_secret(secret_name, username):
            return False
    return all(can_use_gateway_endpoint(str(name), username) for name in all_source_values("endpoint_name"))


def validate_can_invoke_genai_evaluate(username: str) -> bool:
    """UPDATE on the experiment and READ on the experiment of every trace evaluated."""
    return _job_request_permission(username).can_update
