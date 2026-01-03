import re

from flask import request
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.permissions import Permission, get_permission
from mlflow_oidc_auth.utils import effective_experiment_permission, get_experiment_id, get_request_param


def _get_permission_from_experiment_id(username: str) -> Permission:
    experiment_id = get_experiment_id()
    return effective_experiment_permission(experiment_id, username).permission


def _get_permission_from_experiment_name(username: str) -> Permission:
    experiment_name = get_request_param("experiment_name")
    store_exp = _get_tracking_store().get_experiment_by_name(experiment_name)
    if store_exp is None:
        # experiment is not exist, need return all permissions
        return get_permission("MANAGE")
    return effective_experiment_permission(store_exp.experiment_id, username).permission


_EXPERIMENT_ID_PATTERN = re.compile(r"^(\d+)/")


def _get_experiment_id_from_view_args():
    # TODO: check it with get_request_param("artifact_path") to replace
    view_args = request.view_args
    if view_args is not None and (artifact_path := view_args.get("artifact_path")):
        if m := _EXPERIMENT_ID_PATTERN.match(artifact_path):
            return m.group(1)
    return None


def _get_permission_from_experiment_id_artifact_proxy(username: str) -> Permission:
    if experiment_id := _get_experiment_id_from_view_args():
        return effective_experiment_permission(experiment_id, username).permission
    return get_permission(config.DEFAULT_MLFLOW_PERMISSION)


def validate_can_read_experiment(username: str):
    return _get_permission_from_experiment_id(username).can_read


def validate_can_read_experiment_by_name(username: str):
    return _get_permission_from_experiment_name(username).can_read


def validate_can_update_experiment(username: str):
    return _get_permission_from_experiment_id(username).can_update


def validate_can_delete_experiment(username: str):
    return _get_permission_from_experiment_id(username).can_delete


def validate_can_manage_experiment(username: str):
    return _get_permission_from_experiment_id(username).can_manage


def validate_can_read_experiment_artifact_proxy(username: str):
    return _get_permission_from_experiment_id_artifact_proxy(username).can_read


def validate_can_update_experiment_artifact_proxy(username: str):
    return _get_permission_from_experiment_id_artifact_proxy(username).can_update


def validate_can_delete_experiment_artifact_proxy(username: str):
    return _get_permission_from_experiment_id_artifact_proxy(username).can_delete


def validate_can_read_experiments_from_experiment_ids(username: str) -> bool:
    """Validate READ permission for requests that include an experiment_ids list."""
    experiment_ids = []

    if request.method == "POST" and request.is_json:
        data = request.get_json(silent=True) or {}
        experiment_ids = data.get("experiment_ids", []) or []
    else:
        experiment_ids = request.args.getlist("experiment_ids")

    for experiment_id in experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True


def validate_can_update_experiment_from_experiment_id(username: str) -> bool:
    """Validate UPDATE permission using an explicit experiment_id parameter."""
    experiment_id = get_request_param("experiment_id")
    return effective_experiment_permission(experiment_id, username).permission.can_update
