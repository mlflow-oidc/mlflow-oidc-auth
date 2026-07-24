from __future__ import annotations

from flask import request
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.permissions import NO_PERMISSIONS, Permission
from mlflow_oidc_auth.utils import effective_experiment_permission
from mlflow_oidc_auth.validators.run import _get_permission_from_run_id


def _pick(data, *keys):
    """First present value among ``keys``. Bodies are proto-JSON, which accepts BOTH the
    snake_case field name AND the camelCase json name — so every field must be read under
    both spellings, or an attacker can hide an experiment from the check under the spelling
    we don't read while MLflow still searches it (cross-tenant leak)."""
    if not isinstance(data, dict):
        return None
    for key in keys:
        if data.get(key) is not None:
            return data[key]
    return None


def _json_body() -> dict:
    try:
        return request.get_json(silent=True) or {}
    except Exception:
        return {}


def _resolve_trace_id() -> str | None:
    """A trace id can arrive in the URL path (v3 ``/traces/<trace_id>``, v2
    ``/traces/<request_id>/...``), the query string (``GET /traces/get?trace_id=``),
    or the JSON body (``link-prompts``). Check all three, path first."""
    view_args = request.view_args or {}
    for key in ("trace_id", "request_id"):
        if view_args.get(key):
            return view_args[key]
    for key in ("trace_id", "traceId", "request_id", "requestId"):
        if request.args.get(key):
            return request.args.get(key)
    return _pick(_json_body(), "trace_id", "traceId", "request_id", "requestId")


def _experiment_for_trace(trace_id: str) -> str:
    return _get_tracking_store().get_trace_info(trace_id).experiment_id


def _require_read_on_all(username: str, experiment_ids) -> bool:
    """Require READ on every referenced experiment. DENY when the set is empty or
    unresolved — an unscoped trace query would otherwise return every tenant's traces (#259)."""
    if not experiment_ids:
        return False
    for experiment_id in experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True


def _search_experiment_ids() -> list:
    """Collect experiment_ids across the trace-search variants:

    * v2 ``GET /traces?experiment_ids=...`` (repeated query param),
    * v2 ``POST`` body ``experiment_ids``,
    * v3 ``POST /traces/search`` body ``locations[].mlflow_experiment.experiment_id``.
    """
    ids: list = list(request.args.getlist("experiment_ids"))
    body = _json_body()
    body_ids = _pick(body, "experiment_ids", "experimentIds")
    if isinstance(body_ids, list):
        ids += body_ids
    for location in _pick(body, "locations") or []:
        mlflow_experiment = _pick(location, "mlflow_experiment", "mlflowExperiment")
        experiment_id = _pick(mlflow_experiment or {}, "experiment_id", "experimentId")
        if experiment_id:
            ids.append(experiment_id)
    return [i for i in ids if i]


def _permission_for_trace(username: str) -> Permission:
    trace_id = _resolve_trace_id()
    if not trace_id:
        return NO_PERMISSIONS
    experiment_id = _experiment_for_trace(trace_id)
    return effective_experiment_permission(experiment_id, username).permission


def validate_can_read_traces_from_experiment_ids(username: str) -> bool:
    """SearchTraces (v2 experiment_ids) and SearchTracesV3 (v3 locations)."""
    return _require_read_on_all(username, _search_experiment_ids())


def validate_can_read_traces_from_trace_ids(username: str) -> bool:
    """BatchGetTraces / BatchGetTraceInfos carry a list of ``trace_ids``; resolve each to its
    experiment and require READ on all. DENY on empty or any unresolved trace."""
    body = _json_body()
    trace_ids = request.args.getlist("trace_ids") or _pick(body, "trace_ids", "traceIds") or []
    if not isinstance(trace_ids, list) or not trace_ids:
        return False
    experiment_ids = []
    for trace_id in trace_ids:
        try:
            experiment_ids.append(_experiment_for_trace(trace_id))
        except Exception:
            return False  # an unresolvable trace id fails closed
    return _require_read_on_all(username, experiment_ids)


def validate_can_read_trace(username: str) -> bool:
    return _permission_for_trace(username).can_read


def validate_can_update_trace(username: str) -> bool:
    return _permission_for_trace(username).can_update


def validate_can_update_trace_from_experiment_id(username: str) -> bool:
    body = _json_body()
    experiment_id = _pick(body, "experiment_id", "experimentId") or request.args.get("experiment_id")
    if not experiment_id:
        return False
    return effective_experiment_permission(experiment_id, username).permission.can_update


def validate_can_delete_traces_from_experiment_id(username: str) -> bool:
    body = _json_body()
    experiment_id = _pick(body, "experiment_id", "experimentId") or request.args.get("experiment_id")
    if not experiment_id:
        return False
    return effective_experiment_permission(experiment_id, username).permission.can_delete


def validate_can_update_trace_from_run_id(username: str) -> bool:
    # LinkTracesToRun carries run_id in the body.
    return _get_permission_from_run_id(username).can_update
