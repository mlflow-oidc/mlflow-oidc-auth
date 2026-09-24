"""Validators for MLflow's background-job routes served through Flask.

``GET /ajax-api/3.0/mlflow/jobs/<job_id>`` and ``PATCH /ajax-api/3.0/mlflow/jobs/cancel/<job_id>``
read and cancel the jobs the UI starts (issue detection, evaluation, prompt optimization).
Those jobs record the experiment they run in among their params (or, on MLflow 3.14, only the
run they write to), and inherit its permission:
READ to read a job, UPDATE to cancel it. A job that does not exist, or whose params name no
experiment, is admin-only.
"""

from __future__ import annotations

import json

from mlflow.server.handlers import _get_tracking_store
from mlflow.server.jobs import get_job

from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import NO_PERMISSIONS, Permission, intersect_permissions
from mlflow_oidc_auth.utils import all_source_values
from mlflow_oidc_auth.validators._experiment_scope import permission_on_all_experiments

logger = get_logger()


def _experiment_of_job(job_id: str) -> str | None:
    """The experiment a job runs in, or None if it cannot be resolved.

    Taken from ``params["experiment_id"]``, else from the run in ``params["run_id"]``: on
    MLflow 3.14 an evaluation job records only its run, not its experiment.
    """
    try:
        params = json.loads(get_job(job_id).params or "{}")
    except Exception:
        logger.debug("Could not resolve job for authorization")
        return None
    if not isinstance(params, dict):
        return None
    if experiment_id := params.get("experiment_id"):
        return str(experiment_id)
    if run_id := params.get("run_id"):
        try:
            return str(_get_tracking_store().get_run(str(run_id)).info.experiment_id)
        except Exception:
            logger.debug("Could not resolve the run of a job for authorization")
    return None


def _job_permission(username: str) -> Permission:
    # The path parameter MLflow dispatches on, plus any job_id in the query string or body.
    permissions = []
    for job_id in all_source_values("job_id"):
        experiment_id = _experiment_of_job(str(job_id))
        if experiment_id is None:
            return NO_PERMISSIONS
        permissions.append(permission_on_all_experiments([experiment_id], username))
    return intersect_permissions(permissions)


def validate_can_read_job(username: str) -> bool:
    """READ on the job's experiment."""
    return _job_permission(username).can_read


def validate_can_cancel_job(username: str) -> bool:
    """UPDATE on the job's experiment."""
    return _job_permission(username).can_update
