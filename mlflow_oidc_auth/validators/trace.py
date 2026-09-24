from __future__ import annotations

from flask import request
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.utils import all_source_values, effective_experiment_permission, request_body_dict

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
    # The body exactly as MLflow parses it: on a proto route that is a FORCED parse, so a
    # DELETE/PATCH body sent without a JSON content type is still read. get_json(silent=
    # True) returned {} for it, and a check that saw nothing could not deny what MLflow
    # then acted on.
    return request_body_dict()


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
    # Path, every repetition in the query string, body under either spelling, form.
    ids = all_source_values("trace_id", "request_id")
    for key in ("traceId", "requestId"):
        ids += [v for v in request.args.getlist(key) if v]
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
    experiment_ids = all_source_values("experiment_id")
    if not experiment_ids:
        return False
    return all(effective_experiment_permission(e, username).permission.can_update for e in experiment_ids)


def validate_can_delete_traces_from_experiment_id(username: str) -> bool:
    experiment_ids = all_source_values("experiment_id")
    if not experiment_ids:
        return False
    return all(effective_experiment_permission(e, username).permission.can_delete for e in experiment_ids)


def validate_can_update_trace_from_run_id(username: str) -> bool:
    """LinkTracesToRun carries run_id in the body. A run inherits its experiment's permission;
    require UPDATE on every run's experiment across all run_id spellings."""
    # Every source, not "body or query": the former `body.get(k) or args.get(k)` skipped
    # the query string whenever the body carried the field, so a second run named there
    # was never checked (issue #285).
    run_ids = all_source_values("run_id", "run_uuid")
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
