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


def validate_can_create_gateway(username: str) -> bool:
    """Validate gateway create requests.

    Gateway creation is allowed for any authenticated (non-admin) user. This
    mirrors the UX for other resource creation endpoints where creators are
    granted MANAGE post-creation in an after-request handler.
    """

    # We intentionally allow authenticated users to create gateways. The
    # after-request hook will grant MANAGE permissions to the creator.
    return True


def validate_gateway_proxy(username: str) -> bool:
    """Validate gateway proxy requests.

    This attempts to extract a gateway identifier from the request and
    enforce READ for GET requests and UPDATE for POST (create/update).

    When no explicit gateway name can be extracted, it falls back to
    checking whether the user has the required capability on any gateway.
    """

    from mlflow_oidc_auth.store import store
    from mlflow_oidc_auth.permissions import get_permission
    from mlflow_oidc_auth.utils.permissions import can_use_gateway_endpoint, can_update_gateway_endpoint

    def _extract_gateway_name():
        # Try query params first
        if request.args:
            for key in ("gateway_name", "gateway", "name", "target"):
                if key in request.args:
                    return request.args.get(key)
        # Try JSON body
        if request.is_json:
            data = request.get_json(silent=True) or {}
            for key in ("gateway_name", "gateway", "name", "target"):
                if key in data:
                    return data.get(key)
        return None

    gateway_name = _extract_gateway_name()

    # Map HTTP method to required capability
    if request.method == "GET":
        # USE
        if gateway_name:
            return can_use_gateway_endpoint(str(gateway_name), username)
        # Fallback: check if user has any gateway endpoint with use
        perms = store.list_gateway_endpoint_permissions(username)
        return any(get_permission(p.permission).can_use for p in perms)
    else:
        # POST/PUT/DELETE -> UPDATE required
        if gateway_name:
            return can_update_gateway_endpoint(str(gateway_name), username)
        perms = store.list_gateway_endpoint_permissions(username)
        return any(get_permission(p.permission).can_update for p in perms)
