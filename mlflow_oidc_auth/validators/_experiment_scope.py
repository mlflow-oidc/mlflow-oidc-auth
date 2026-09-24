"""Shared helpers for resources whose permission is inherited from an experiment.

Every helper here fails closed: an empty set of experiments, or a referenced resource that
cannot be resolved, yields ``NO_PERMISSIONS``, never ``DEFAULT_MLFLOW_PERMISSION``.
"""

from __future__ import annotations

from typing import Iterable

from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.permissions import NO_PERMISSIONS, Permission, intersect_permissions
from mlflow_oidc_auth.utils import effective_experiment_permission


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
