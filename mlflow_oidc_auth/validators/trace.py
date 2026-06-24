from __future__ import annotations

from typing import Optional

from flask import request
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.permissions import Permission
from mlflow_oidc_auth.utils import effective_experiment_permission, get_request_param
from mlflow_oidc_auth.validators.run import _get_permission_from_run_id


def _get_trace_id() -> str:
    # MLflow protos sometimes use request_id where the tracking store uses trace_id.
    return get_request_param("trace_id") if _has_request_param("trace_id") else get_request_param("request_id")


def _has_request_param(name: str) -> bool:
    try:
        get_request_param(name)
        return True
    except Exception:
        return False


def _get_permission_from_trace_id(username: str) -> Permission:
    trace_id = _get_trace_id()
    trace_info = _get_tracking_store().get_trace_info(trace_id)
    experiment_id = trace_info.experiment_id
    return effective_experiment_permission(experiment_id, username).permission


def validate_can_read_traces_from_experiment_ids(username: str) -> bool:
    # SearchTraces v2 uses experiment_ids, while SearchTraces v3 uses locations[].
    try:
        data = request.get_json(silent=True) or {}
        experiment_ids = list(data.get("experiment_ids", []) or [])
        if locations := data.get("locations", []):
            for location in locations:
                if not isinstance(location, dict):
                    continue
                mlflow_experiment = location.get("mlflow_experiment")
                if isinstance(mlflow_experiment, dict):
                    experiment_id = mlflow_experiment.get("experiment_id")
                    if experiment_id:
                        experiment_ids.append(str(experiment_id))
    except Exception:
        experiment_ids = []

    for experiment_id in experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True


def validate_can_read_traces_from_trace_ids(username: str) -> bool:
    trace_ids = []
    if request.method == "POST" and request.is_json:
        data = request.get_json(silent=True) or {}
        trace_ids = data.get("trace_ids", []) or []
    else:
        trace_ids = request.args.getlist("trace_ids")

    tracking_store = _get_tracking_store()
    for trace_id in trace_ids:
        trace_info = tracking_store.get_trace_info(trace_id)
        if not effective_experiment_permission(trace_info.experiment_id, username).permission.can_read:
            return False
    return True


def validate_can_read_trace(username: str) -> bool:
    return _get_permission_from_trace_id(username).can_read


def validate_can_update_trace(username: str) -> bool:
    return _get_permission_from_trace_id(username).can_update


def validate_can_update_trace_from_experiment_id(username: str) -> bool:
    experiment_id = get_request_param("experiment_id")
    return effective_experiment_permission(experiment_id, username).permission.can_update


def validate_can_delete_traces_from_experiment_id(username: str) -> bool:
    experiment_id = get_request_param("experiment_id")
    return effective_experiment_permission(experiment_id, username).permission.can_delete


def validate_can_update_trace_from_run_id(username: str) -> bool:
    # LinkTracesToRun uses run_id
    return _get_permission_from_run_id(username).can_update
