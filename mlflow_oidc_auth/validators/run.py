from mlflow.server.handlers import _get_tracking_store
from flask import request

from mlflow_oidc_auth.permissions import Permission, intersect_permissions
from mlflow_oidc_auth.utils import all_source_values, effective_experiment_permission, get_request_param_values


def _permission_for_run(run_id: str, username: str) -> Permission:
    # run permissions inherit from parent resource (experiment)
    # so we just get the experiment permission
    run = _get_tracking_store().get_run(run_id)
    experiment_id = run.info.experiment_id
    return effective_experiment_permission(experiment_id, username).permission


def _get_permission_from_run_id(username: str) -> Permission:
    # Every run the request names under run_id or run_uuid, in any source — MLflow acts
    # on one of them, and the union means it does not matter which (issue #285).
    return intersect_permissions(_permission_for_run(run_id, username) for run_id in get_request_param_values("run_id"))


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
    Every repetition of ``run_uuid`` in the query string must be updatable too (the
    union rule). The BODY is deliberately not consulted: on this route it is the
    artifact itself, so reading it as JSON would refuse an owner uploading a JSON file
    that happens to contain a ``run_id``, and reading it as form data would consume a
    multipart stream before the handler sees it.
    """
    run_id = request.args.get("run_uuid")
    if not run_id:
        return False
    run_ids = list(dict.fromkeys([run_id, *(r for r in request.args.getlist("run_uuid") if r)]))
    return all(_permission_for_run(r, username).can_update for r in run_ids)


def validate_can_read_metric_history_bulk_interval(username: str) -> bool:
    """Checks READ permission on all requested runs for the bulk interval endpoint.

    Every run named under ``run_ids`` or ``run_id`` (some clients use the latter), in
    any request source — not only the query string MLflow reads on this GET (#285).
    """
    run_ids = all_source_values("run_ids", "run_id")

    for run_id in run_ids:
        run = _get_tracking_store().get_run(run_id)
        experiment_id = run.info.experiment_id
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True
