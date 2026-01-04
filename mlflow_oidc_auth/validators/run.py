from mlflow.server.handlers import _get_tracking_store
from flask import request

from mlflow_oidc_auth.permissions import Permission
from mlflow_oidc_auth.utils import effective_experiment_permission, get_request_param


def _get_permission_from_run_id(username: str) -> Permission:
    # run permissions inherit from parent resource (experiment)
    # so we just get the experiment permission
    run_id = get_request_param("run_id")
    run = _get_tracking_store().get_run(run_id)
    experiment_id = run.info.experiment_id
    return effective_experiment_permission(experiment_id, username).permission


def validate_can_read_run(username: str):
    return _get_permission_from_run_id(username).can_read


def validate_can_update_run(username: str):
    return _get_permission_from_run_id(username).can_update


def validate_can_delete_run(username: str):
    return _get_permission_from_run_id(username).can_delete


def validate_can_manage_run(username: str):
    return _get_permission_from_run_id(username).can_manage


def validate_can_read_run_artifact(username: str):
    """Checks READ permission on run artifacts."""
    return _get_permission_from_run_id(username).can_read


def validate_can_update_run_artifact(username: str):
    """Checks UPDATE permission on run artifacts."""
    return _get_permission_from_run_id(username).can_update


def validate_can_read_metric_history_bulk_interval(username: str) -> bool:
    """Checks READ permission on all requested runs for the bulk interval endpoint."""
    run_ids = request.args.to_dict(flat=False).get("run_ids", [])
    if not run_ids:
        # Some clients use run_id instead
        run_ids = request.args.to_dict(flat=False).get("run_id", [])

    for run_id in run_ids:
        run = _get_tracking_store().get_run(run_id)
        experiment_id = run.info.experiment_id
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True
