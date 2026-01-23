from __future__ import annotations

from typing import Sequence

from flask import request
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.utils import effective_experiment_permission, get_request_param


def validate_can_read_metric_history_bulk(username: str, run_ids: Sequence[str] | None = None) -> bool:
    """Validate READ permission for the legacy bulk metric-history endpoint.

    The endpoint accepts one or more run ids (query param repeated as `run_id`).
    Run permissions inherit from their parent experiment, so this checks
    READ permission on each run's experiment.

    Args:
        username: Authenticated username.
        run_ids: Optional explicit run ids (primarily for unit tests). When not provided,
            extracts `run_id` query params from the Flask request.

    Returns:
        True if the user has READ permission for all referenced runs.
    """

    if run_ids is None:
        run_ids = request.args.to_dict(flat=False).get("run_id", [])

    if not run_ids:
        raise MlflowException(
            "GetMetricHistoryBulk request must specify at least one run_id.",
            INVALID_PARAMETER_VALUE,
        )

    tracking_store = _get_tracking_store()
    for run_id in run_ids:
        run = tracking_store.get_run(run_id)
        experiment_id = run.info.experiment_id
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True


def validate_can_search_datasets(username: str) -> bool:
    """Validate READ permission for dataset search.

    This endpoint expects `experiment_ids` (POST json or query params).

    Args:
        username: Authenticated username.

    Returns:
        True if the user has READ permission for all requested experiments.
    """

    if request.method == "POST" and request.is_json:
        data = request.get_json(silent=True) or {}
        experiment_ids = data.get("experiment_ids", []) or []
    else:
        experiment_ids = request.args.getlist("experiment_ids")

    if not experiment_ids:
        raise MlflowException(
            "SearchDatasets request must specify at least one experiment_id.",
            INVALID_PARAMETER_VALUE,
        )

    for experiment_id in experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True


def validate_can_create_promptlab_run(username: str) -> bool:
    """Validate UPDATE permission for promptlab run creation.

    The request must include `experiment_id`.

    Args:
        username: Authenticated username.

    Returns:
        True if the user can UPDATE the target experiment.
    """

    try:
        experiment_id = get_request_param("experiment_id")
    except MlflowException as e:
        # Normalize the error message to keep this validator stable.
        raise MlflowException(
            "CreatePromptlabRun request must specify experiment_id.",
            INVALID_PARAMETER_VALUE,
        ) from e

    return effective_experiment_permission(experiment_id, username).permission.can_update


def validate_gateway_proxy(_username: str) -> bool:
    """Allow gateway proxy requests without permission checks."""

    return True
