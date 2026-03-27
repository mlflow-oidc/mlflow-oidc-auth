"""Validators for prompt optimization job operations.

Prompt optimization jobs inherit permissions from their parent experiment.
The job_id is resolved to an experiment_id via the job's stored params.
"""

import json

from mlflow.server.jobs import get_job

from mlflow_oidc_auth.permissions import Permission
from mlflow_oidc_auth.utils import (
    effective_experiment_permission,
    get_request_param,
)


def _get_permission_from_prompt_optimization_job_id(username: str) -> Permission:
    """Resolve a prompt optimization job's permission from its parent experiment.

    Extracts the job_id from the Flask request, fetches the job entity,
    parses the experiment_id from the job's params JSON, then returns
    the effective experiment permission for the given user.

    Parameters:
        username: The authenticated username.

    Returns:
        The effective Permission for the job's parent experiment.
    """
    job_id = get_request_param("job_id")
    job_entity = get_job(job_id)
    params = json.loads(job_entity.params)
    experiment_id = params.get("experiment_id")
    return effective_experiment_permission(experiment_id, username).permission


def validate_can_read_prompt_optimization_job(username: str) -> bool:
    """Validate the user can read a prompt optimization job."""
    return _get_permission_from_prompt_optimization_job_id(username).can_read


def validate_can_update_prompt_optimization_job(username: str) -> bool:
    """Validate the user can update (cancel) a prompt optimization job."""
    return _get_permission_from_prompt_optimization_job_id(username).can_update


def validate_can_delete_prompt_optimization_job(username: str) -> bool:
    """Validate the user can delete a prompt optimization job."""
    return _get_permission_from_prompt_optimization_job_id(username).can_delete
