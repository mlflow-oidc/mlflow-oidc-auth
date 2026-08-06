from mlflow.server.handlers import _get_tracking_store
from flask import request

from mlflow_oidc_auth.permissions import Permission
from mlflow_oidc_auth.utils import effective_experiment_permission, get_request_param


def _permission_for_run(run_id: str, username: str) -> Permission:
    # run permissions inherit from parent resource (experiment)
    # so we just get the experiment permission
    run = _get_tracking_store().get_run(run_id)
    experiment_id = run.info.experiment_id
    return effective_experiment_permission(experiment_id, username).permission


def _get_permission_from_run_id(username: str) -> Permission:
    return _permission_for_run(get_request_param("run_id"), username)


def validate_can_read_run(username: str) -> bool:
    return _get_permission_from_run_id(username).can_read


def validate_can_update_run(username: str) -> bool:
    return _get_permission_from_run_id(username).can_update


def validate_can_delete_run(username: str) -> bool:
    return _get_permission_from_run_id(username).can_delete


def validate_can_manage_run(username: str) -> bool:
    return _get_permission_from_run_id(username).can_manage


def validate_can_read_run_artifact(username: str) -> bool:
    """Checks READ permission on run artifacts."""
    return _get_permission_from_run_id(username).can_read


def validate_can_update_run_artifact(username: str) -> bool:
    """Checks UPDATE permission on run artifacts (POST /mlflow/upload-artifact).

    Reads ``run_uuid`` from the QUERY STRING, because that is the only place MLflow's
    ``upload_artifact_handler`` looks::

        args = request.args
        run_uuid = args.get("run_uuid")

    The shared ``get_request_param`` helper reads the BODY on a POST, so the plugin
    authorized the run named in the body while MLflow wrote the artifact into the run
    named in the query string — the inverse of the #285 divergence, and a cross-tenant
    artifact write (issue #288). This route is the only one bound to this validator, so
    mirroring its handler exactly is safe.

    A request with no ``run_uuid`` query parameter is refused rather than passed along:
    MLflow rejects it with 400 regardless, and resolving nothing must never mean allow.
    """
    run_id = request.args.get("run_uuid")
    if not run_id:
        return False
    return _permission_for_run(run_id, username).can_update


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
