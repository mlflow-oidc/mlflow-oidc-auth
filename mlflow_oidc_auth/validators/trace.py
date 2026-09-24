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
        # dict.fromkeys: a field whose two spellings coincide (single-word names such as
        # "trace" or "locations") must be read once, not twice.
        for key in dict.fromkeys((snake, camel)):
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


def _start_trace_v3_trace_infos() -> list:
    """Every ``trace.trace_info`` object in a StartTraceV3 body, across both spellings."""
    infos: list = []
    for trace in _field_values(_json_body(), "trace", "trace"):
        infos += [info for info in _field_values(trace, "trace_info", "traceInfo") if isinstance(info, dict)]
    return infos


def _assessments_of(info: dict) -> list:
    """Every assessment object under a trace_info, across both spellings of the list."""
    return [a for lst in _field_values(info, "assessments", "assessments") if isinstance(lst, list) for a in lst if isinstance(a, dict)]


def validate_can_start_trace_v3(username: str) -> bool:
    """StartTraceV3 (``POST /3.0/mlflow/traces``): UPDATE on the destination experiment,
    plus the checks MLflow's merge-on-conflict behaviour requires.

    The destination is ``trace.trace_info.trace_location.mlflow_experiment.experiment_id``.
    A body naming no experiment (or a non-experiment location) is denied — there is nothing
    to authorize against.

    The body also carries a caller-chosen ``trace_id``. MLflow's SQL store does not reject
    an id that already exists: it catches the IntegrityError and merges the body into the
    EXISTING trace. So when the named trace exists:

    * UPDATE is required on its current experiment (tags / metadata are written into it);
    * DELETE is also required there when the destination differs, because the merge
      re-homes the trace into the destination — it vanishes from its experiment, which is
      a delete that ``DeleteTraces`` would gate on DELETE;
    * assessments carrying an ``assessment_id`` are refused, because the merge upserts by
      ``assessment_id`` alone and the owner of an arbitrary assessment id cannot be
      resolved here — naming another tenant's assessment would overwrite or move it.

    An assessment that names a different ``trace_id`` than the trace being started is
    refused outright: no legitimate client sends one, and the store trusts it. Only a
    definite "does not exist" counts as a new trace; any other lookup failure denies.

    Parameters:
        username: The authenticated user.

    Returns:
        True when every check above passes.
    """
    from mlflow.exceptions import MlflowException

    from mlflow_oidc_auth.utils.request_helpers import _is_scalar

    infos = _start_trace_v3_trace_infos()
    destinations: list = []
    for info in infos:
        for location in _field_values(info, "trace_location", "traceLocation"):
            for mlflow_experiment in _field_values(location, "mlflow_experiment", "mlflowExperiment"):
                destinations += _field_values(mlflow_experiment, "experiment_id", "experimentId")
    # A list / dict where an id belongs names no single resource; refuse rather than let it
    # reach a set or a store lookup, which would raise and turn the auth hook into a 500.
    if not all(_is_scalar(e) for e in destinations):
        return False
    destinations = list(dict.fromkeys(e for e in destinations if e))
    if not destinations:
        return False

    need_update = list(destinations)
    need_delete: list = []
    for info in infos:
        # MLflow trusts the caller-chosen trace_id, and an absent one is stored as "" — so a
        # second id-less request collides with the first and takes the merge path. An absent
        # id is therefore not "a new trace": every trace_info must name a non-empty string id.
        own_values = _field_values(info, "trace_id", "traceId")
        if not own_values or not all(isinstance(t, str) and t for t in own_values):
            return False
        own_ids = set(own_values)
        assessments = _assessments_of(info)
        for assessment in assessments:
            named_values = _field_values(assessment, "trace_id", "traceId")
            assessment_ids = _field_values(assessment, "assessment_id", "assessmentId")
            if not all(_is_scalar(v) for v in named_values + assessment_ids):
                return False
            named = {t for t in named_values if t}
            if named - own_ids:
                return False
        for trace_id in own_ids:
            try:
                existing_experiment = _experiment_for_trace(trace_id)
            except MlflowException as e:
                if e.error_code == "RESOURCE_DOES_NOT_EXIST":
                    continue
                return False
            except Exception:
                return False
            if any(_field_values(a, "assessment_id", "assessmentId") for a in assessments):
                return False
            need_update.append(existing_experiment)
            if any(existing_experiment != d for d in destinations):
                need_delete.append(existing_experiment)

    # The union rule: MLflow reads only the nested body fields above, but any flat
    # experiment / trace id the request also carries (query string, top-level body, form)
    # is authorized too, so a divergence in what MLflow parses can never widen access.
    need_update += all_source_values("experiment_id")
    for trace_id in all_source_values("trace_id", "request_id"):
        try:
            need_update.append(_experiment_for_trace(trace_id))
        except MlflowException as e:
            if e.error_code != "RESOURCE_DOES_NOT_EXIST":
                return False
        except Exception:
            return False

    for experiment_id in dict.fromkeys(need_update):
        if not effective_experiment_permission(experiment_id, username).permission.can_update:
            return False
    for experiment_id in dict.fromkeys(need_delete):
        if not effective_experiment_permission(experiment_id, username).permission.can_delete:
            return False
    return True
