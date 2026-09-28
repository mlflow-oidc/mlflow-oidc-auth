"""Validators for MLflow evaluation datasets (``/api/3.0/mlflow/datasets/*``).

An evaluation dataset has no permission record of its own. It is linked to zero or more
experiments (``get_dataset_experiment_ids``) and inherits their permissions: the caller must
hold the capability on EVERY linked experiment. A dataset linked to no experiment, or one
that does not exist, resolves to ``NO_PERMISSIONS`` and is therefore admin-only.
"""

from __future__ import annotations

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.permissions import NO_PERMISSIONS, Permission, intersect_permissions
from mlflow_oidc_auth.utils import get_request_param_values
from mlflow_oidc_auth.validators._experiment_scope import permission_on_all_experiments, values_mlflow_also_reads


def dataset_experiment_ids(dataset_id: str) -> list[str]:
    """The experiments ``dataset_id`` is linked to; empty if none or if it does not exist.

    Parameters:
        dataset_id: The evaluation dataset id.

    Returns:
        The linked experiment ids as strings.

    Raises:
        MlflowException: For any store error other than "does not exist".
    """
    try:
        return [str(e) for e in _get_tracking_store().get_dataset_experiment_ids(dataset_id)]
    except MlflowException as e:
        if e.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
            return []
        raise


def _dataset_permission(username: str) -> Permission:
    # Every dataset id the request names (the path parameter MLflow dispatches on, plus any
    # other value in the query string or body), each resolved through its linked experiments.
    permissions = []
    for dataset_id in get_request_param_values("dataset_id"):
        experiment_ids = dataset_experiment_ids(str(dataset_id))
        if not experiment_ids:
            return NO_PERMISSIONS
        permissions.append(permission_on_all_experiments(experiment_ids, username))
    return intersect_permissions(permissions)


def _body_experiments_permission(username: str) -> Permission:
    # ``experiment_ids`` is optional to MLflow, so it must be present where MLflow reads it;
    # then every value in every source is authorized. None means NO_PERMISSIONS.
    return permission_on_all_experiments(values_mlflow_also_reads("experiment_ids"), username)


def validate_can_read_dataset(username: str) -> bool:
    """READ on every experiment the dataset is linked to."""
    return _dataset_permission(username).can_read


def validate_can_update_dataset(username: str) -> bool:
    """UPDATE on every experiment the dataset is linked to (tags, records)."""
    return _dataset_permission(username).can_update


def validate_can_delete_dataset(username: str) -> bool:
    """DELETE on every experiment the dataset is linked to."""
    return _dataset_permission(username).can_delete


def validate_can_create_dataset(username: str) -> bool:
    """UPDATE on every experiment named in ``experiment_ids``; at least one is required."""
    return _body_experiments_permission(username).can_update


def validate_can_search_evaluation_datasets(username: str) -> bool:
    """READ on every experiment the search is scoped to; an unscoped search is refused.

    The response is additionally filtered in ``after_request`` to datasets whose linked
    experiments are all readable, because a dataset can be linked to more than one.
    """
    return _body_experiments_permission(username).can_read


def validate_can_link_dataset_experiments(username: str) -> bool:
    """UPDATE on the dataset's experiments AND on every experiment added or removed."""
    return _dataset_permission(username).can_update and _body_experiments_permission(username).can_update
