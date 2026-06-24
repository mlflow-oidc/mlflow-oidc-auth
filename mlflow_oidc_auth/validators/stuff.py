from __future__ import annotations

import re
from typing import Any, Sequence

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


def _get_dataset_id() -> str:
    if request.view_args and request.view_args.get("dataset_id"):
        return str(request.view_args["dataset_id"])
    return get_request_param("dataset_id")


def _get_dataset_experiment_ids() -> list[str]:
    dataset_id = _get_dataset_id()
    return list(_get_tracking_store().get_dataset_experiment_ids(dataset_id=dataset_id))


def validate_can_read_dataset(username: str) -> bool:
    experiment_ids = _get_dataset_experiment_ids()
    if not experiment_ids:
        return False
    for experiment_id in experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True


def validate_can_update_dataset(username: str) -> bool:
    experiment_ids = _get_dataset_experiment_ids()
    if not experiment_ids:
        return False
    for experiment_id in experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_update:
            return False
    return True


def validate_can_delete_dataset(username: str) -> bool:
    experiment_ids = _get_dataset_experiment_ids()
    if not experiment_ids:
        return False
    for experiment_id in experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_delete:
            return False
    return True


def validate_can_create_dataset(username: str) -> bool:
    if request.method == "POST" and request.is_json:
        data = request.get_json(silent=True) or {}
        experiment_ids = data.get("experiment_ids", []) or []
    else:
        experiment_ids = request.args.getlist("experiment_ids")
    if not experiment_ids:
        return False
    for experiment_id in experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_update:
            return False
    return True


def validate_can_update_dataset_experiment_links(username: str) -> bool:
    existing_experiment_ids = _get_dataset_experiment_ids()
    if request.method == "POST" and request.is_json:
        data = request.get_json(silent=True) or {}
        target_experiment_ids = data.get("experiment_ids", []) or []
    else:
        target_experiment_ids = request.args.getlist("experiment_ids")

    all_experiment_ids = list({*existing_experiment_ids, *target_experiment_ids})
    if not all_experiment_ids:
        return False
    for experiment_id in all_experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_update:
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


def _collect_experiment_ids_from_payload(payload: Any) -> list[str]:
    ids: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"experiment_ids", "experimentIds"} and isinstance(value, list):
                    ids.extend(str(v) for v in value if v is not None)
                elif key in {"experiment_id", "experimentId"} and value is not None:
                    ids.append(str(value))
                elif key in {"mlflow_experiment", "mlflowExperiment"} and isinstance(value, dict):
                    for nested_key in ("experiment_id", "experimentId"):
                        if value.get(nested_key) is not None:
                            ids.append(str(value[nested_key]))
                else:
                    _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(payload)
    return ids


def validate_can_access_graphql(username: str) -> bool:
    if not request.is_json:
        return True

    payload = request.get_json(silent=True) or {}
    experiment_ids = _collect_experiment_ids_from_payload(payload)
    for experiment_id in experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True


def validate_can_search_registered_models(username: str) -> bool:
    filter_string = request.args.get("filter", "")
    if not filter_string:
        return True

    # Example: tags.`_mlflow_experiment_ids` ILIKE '%,1,%'
    matched = re.findall(r"%[, ]*(\d+)[, ]*%", filter_string)
    for experiment_id in matched:
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True


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
            for key in ("gateway_name", "gateway", "name", "target", "gateway_path"):
                if key in request.args:
                    return request.args.get(key)
        # Try JSON body
        if request.is_json:
            data = request.get_json(silent=True) or {}
            for key in ("gateway_name", "gateway", "name", "target", "gateway_path"):
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
