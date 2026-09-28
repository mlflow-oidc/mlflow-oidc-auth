"""Shared helpers for resources whose permission is inherited from an experiment.

Every helper here fails closed: an empty set of experiments, or a referenced resource that
cannot be resolved, yields ``NO_PERMISSIONS``, never ``DEFAULT_MLFLOW_PERMISSION``.
"""

from __future__ import annotations

from typing import Iterable

from mlflow.exceptions import MlflowException
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.permissions import NO_PERMISSIONS, Permission, intersect_permissions
from mlflow_oidc_auth.utils import all_source_values, effective_experiment_permission, get_request_param


def permission_on_all_experiments(experiment_ids: Iterable, username: str) -> Permission:
    """The capabilities ``username`` holds on EVERY experiment in ``experiment_ids``.

    Parameters:
        experiment_ids: Experiment ids the request touches. Duplicates are ignored.
        username: The authenticated user.

    Returns:
        The intersected permission; ``NO_PERMISSIONS`` when ``experiment_ids`` is empty.
    """
    distinct = list(dict.fromkeys(str(e) for e in experiment_ids if e is not None and str(e).strip()))
    return intersect_permissions(effective_experiment_permission(e, username).permission for e in distinct)


def trace_ids_permission(trace_ids: Iterable, username: str) -> Permission:
    """The capabilities ``username`` holds on the experiments of every trace in ``trace_ids``.

    A trace that cannot be resolved yields ``NO_PERMISSIONS``.

    Parameters:
        trace_ids: Trace ids named by the request.
        username: The authenticated user.

    Returns:
        The intersected permission; ``NO_PERMISSIONS`` for an unresolvable trace.
    """
    experiment_ids = []
    tracking_store = _get_tracking_store()
    for trace_id in dict.fromkeys(str(t) for t in trace_ids):
        try:
            experiment_ids.append(tracking_store.get_trace_info(trace_id).experiment_id)
        except Exception:
            return NO_PERMISSIONS
    return permission_on_all_experiments(experiment_ids, username)


def values_mlflow_also_reads(param: str) -> list:
    """Every value of ``param`` in any source, or ``[]`` if MLflow's own source has none.

    For a proto field that MLflow treats as optional (a search scope, say), a value that
    only appears in a source MLflow ignores must not satisfy the check: MLflow would act
    with the field unset, for instance searching every experiment. So the field has to be
    present where MLflow reads it, and then every value in every source is authorized.

    Parameters:
        param: The snake_case field name.

    Returns:
        The distinct values, or ``[]`` when the source MLflow reads has no value.
    """
    try:
        get_request_param(param)
    except MlflowException:
        return []
    return all_source_values(param)


def names_only_caller(param: str, username: str) -> bool:
    """True if every value of ``param`` in any request source is ``username``.

    Used for fields MLflow stores as attribution (who did something). Compared
    case-insensitively after trimming, as usernames are.

    Parameters:
        param: The snake_case field name.
        username: The authenticated user.

    Returns:
        True when the field is absent or names only the caller.
    """
    caller = username.strip().lower()
    return all(str(value).strip().lower() == caller for value in all_source_values(param))
