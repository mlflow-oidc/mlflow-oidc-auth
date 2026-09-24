from __future__ import annotations

from flask import request
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.utils import effective_experiment_permission

# ---------------------------------------------------------------------------
# Dual-spelling extraction (security-critical)
#
# MLflow bodies are proto-JSON. protobuf's ParseDict accepts a field under BOTH its
# snake_case name and its lowerCamelCase json name, and when BOTH appear it resolves to
# the LAST one in JSON key order — which the caller controls. So a validator that reads
# only one spelling can be handed {"experiment_id":"mine","experimentId":"victim"}: it
# authorizes "mine" while MLflow operates on "victim" (cross-tenant read/delete/link).
#
# Defence: collect EVERY spelling's value and require the permission on ALL of them. A
# legitimate client sends a single spelling, so this never over-denies real traffic; a
# request carrying both is authorized against the victim value too and therefore denied.
# ---------------------------------------------------------------------------


def _json_body() -> dict:
    try:
        return request.get_json(silent=True) or {}
    except Exception:
        return {}


def _field_values(container, snake: str, camel: str) -> list:
    """All present values for a proto field across its snake_case and camelCase spellings."""
    values = []
    if isinstance(container, dict):
        for key in (snake, camel):
            value = container.get(key)
            if value is not None:
                values.append(value)
    return values


def _all_experiment_ids_from_search() -> list:
    """Every experiment id a trace search could resolve to, across all spellings:

    * v2 ``GET /traces?experiment_ids=...`` (repeated query param),
    * v2 ``POST`` body ``experiment_ids`` / ``experimentIds`` (repeated),
    * v3 ``POST /traces/search`` body ``locations[].mlflow_experiment.experiment_id``.
    """
    ids: list = list(request.args.getlist("experiment_ids"))
    body = _json_body()
    for lst in _field_values(body, "experiment_ids", "experimentIds"):
        if isinstance(lst, list):
            ids += lst
    for locations in _field_values(body, "locations", "locations"):
        for location in locations or []:
            for mlflow_experiment in _field_values(location, "mlflow_experiment", "mlflowExperiment"):
                ids += _field_values(mlflow_experiment, "experiment_id", "experimentId")
    return [i for i in ids if i]


def _all_trace_ids_from_batch() -> list:
    ids: list = list(request.args.getlist("trace_ids"))
    body = _json_body()
    for lst in _field_values(body, "trace_ids", "traceIds"):
        if isinstance(lst, list):
            ids += lst
    return [i for i in ids if i]


def _all_single_trace_ids() -> list:
    """A single-trace route may carry the id in the URL path (safe, one value), the query, or the
    body — and under either spelling. Collect every candidate and check them all."""
    ids: list = []
    view_args = request.view_args or {}
    for key in ("trace_id", "request_id"):
        if view_args.get(key):
            ids.append(view_args[key])
    for key in ("trace_id", "traceId", "request_id", "requestId"):
        value = request.args.get(key)
        if value:
            ids.append(value)
    body = _json_body()
    for key in ("trace_id", "traceId", "request_id", "requestId"):
        value = body.get(key)
        if value:
            ids.append(value)
    return list(dict.fromkeys(ids))


def _experiment_for_trace(trace_id: str) -> str:
    return _get_tracking_store().get_trace_info(trace_id).experiment_id


def _require_read_on_all(username: str, experiment_ids) -> bool:
    """Require READ on every referenced experiment; DENY when the set is empty/unresolved."""
    if not experiment_ids:
        return False
    for experiment_id in experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True


def _require_on_all_traces(username: str, attr: str) -> bool:
    """Resolve every candidate trace id to its experiment and require ``attr`` (can_read/
    can_update) on all. DENY on empty or any unresolvable trace (fail closed)."""
    trace_ids = _all_single_trace_ids()
    if not trace_ids:
        return False
    for trace_id in trace_ids:
        try:
            experiment_id = _experiment_for_trace(trace_id)
        except Exception:
            return False
        if not getattr(effective_experiment_permission(experiment_id, username).permission, attr):
            return False
    return True


def validate_can_read_traces_from_experiment_ids(username: str) -> bool:
    """SearchTraces (v2 experiment_ids), SearchTracesV3 (v3 locations), QueryTraceMetrics,
    CalculateTraceFilterCorrelation — all experiment-scoped reads."""
    return _require_read_on_all(username, _all_experiment_ids_from_search())


def validate_can_read_traces_from_trace_ids(username: str) -> bool:
    """BatchGetTraces / BatchGetTraceInfos: resolve each trace id to its experiment and require
    READ on all. DENY on empty or any unresolved trace."""
    trace_ids = _all_trace_ids_from_batch()
    if not trace_ids:
        return False
    experiment_ids = []
    for trace_id in trace_ids:
        try:
            experiment_ids.append(_experiment_for_trace(trace_id))
        except Exception:
            return False
    return _require_read_on_all(username, experiment_ids)


def validate_can_read_trace(username: str) -> bool:
    return _require_on_all_traces(username, "can_read")


def validate_can_update_trace(username: str) -> bool:
    return _require_on_all_traces(username, "can_update")


def validate_can_update_trace_from_experiment_id(username: str) -> bool:
    experiment_ids = _field_values(_json_body(), "experiment_id", "experimentId")
    if request.args.get("experiment_id"):
        experiment_ids.append(request.args.get("experiment_id"))
    if not experiment_ids:
        return False
    return all(effective_experiment_permission(e, username).permission.can_update for e in experiment_ids)


def validate_can_delete_traces_from_experiment_id(username: str) -> bool:
    experiment_ids = _field_values(_json_body(), "experiment_id", "experimentId")
    if request.args.get("experiment_id"):
        experiment_ids.append(request.args.get("experiment_id"))
    if not experiment_ids:
        return False
    return all(effective_experiment_permission(e, username).permission.can_delete for e in experiment_ids)


def validate_can_update_trace_from_run_id(username: str) -> bool:
    """LinkTracesToRun carries run_id in the body. A run inherits its experiment's permission;
    require UPDATE on every run's experiment across all run_id spellings."""
    body = _json_body()
    run_ids: list = []
    for key in ("run_id", "runId", "run_uuid"):
        value = body.get(key) or request.args.get(key)
        if value:
            run_ids.append(value)
    run_ids = list(dict.fromkeys(run_ids))
    if not run_ids:
        return False
    store = _get_tracking_store()
    for run_id in run_ids:
        try:
            experiment_id = store.get_run(run_id).info.experiment_id
        except Exception:
            return False
        if not effective_experiment_permission(experiment_id, username).permission.can_update:
            return False
    return True


def _start_trace_v3_trace_infos() -> list:
    """Every ``trace.trace_info`` object in a StartTraceV3 body, across both spellings."""
    infos: list = []
    for trace in _field_values(_json_body(), "trace", "trace"):
        infos += [info for info in _field_values(trace, "trace_info", "traceInfo") if isinstance(info, dict)]
    return infos


def validate_can_start_trace_v3(username: str) -> bool:
    """StartTraceV3 (``POST /3.0/mlflow/traces``): UPDATE on the destination experiment,
    and on the experiment of any existing trace the body names.

    The destination is ``trace.trace_info.trace_location.mlflow_experiment.experiment_id``.
    A body naming no experiment (or a non-experiment location) is denied — there is nothing
    to authorize against.

    The body also carries a caller-chosen ``trace_id``. MLflow's SQL store does not reject
    an id that already exists: it catches the IntegrityError and merges the body's tags,
    assessments and metadata into the EXISTING trace. Authorizing only the destination
    experiment would therefore let a caller who can write their own experiment write into
    any other tenant's trace by naming its id. So an existing trace must also be writable.
    Only a definite "does not exist" counts as a new trace; any other lookup failure denies.

    Parameters:
        username: The authenticated user.

    Returns:
        True when every referenced experiment grants UPDATE.
    """
    from mlflow.exceptions import MlflowException

    infos = _start_trace_v3_trace_infos()
    experiment_ids: list = []
    trace_ids: list = []
    for info in infos:
        for location in _field_values(info, "trace_location", "traceLocation"):
            for mlflow_experiment in _field_values(location, "mlflow_experiment", "mlflowExperiment"):
                experiment_ids += _field_values(mlflow_experiment, "experiment_id", "experimentId")
        trace_ids += _field_values(info, "trace_id", "traceId")
    experiment_ids = [e for e in experiment_ids if e]
    if not experiment_ids:
        return False

    for trace_id in dict.fromkeys(t for t in trace_ids if t):
        try:
            experiment_ids.append(_experiment_for_trace(trace_id))
        except MlflowException as e:
            if e.error_code == "RESOURCE_DOES_NOT_EXIST":
                continue
            return False
        except Exception:
            return False

    return all(effective_experiment_permission(e, username).permission.can_update for e in dict.fromkeys(experiment_ids))
