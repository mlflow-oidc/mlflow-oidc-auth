import re

from flask import request
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.permissions import Permission, get_permission
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import get_experiment_id, get_permission_from_store_or_default, get_request_param, get_username


def _get_permission_from_experiment_id() -> Permission:
    experiment_id = get_experiment_id()
    username = get_username()
    return get_permission_from_store_or_default(
        lambda: store.get_experiment_permission(experiment_id, username).permission,
        lambda: store.get_user_groups_experiment_permission(experiment_id, username).permission,
    ).permission


def _get_permission_from_experiment_name() -> Permission:
    experiment_name = get_request_param("experiment_name")
    store_exp = _get_tracking_store().get_experiment_by_name(experiment_name)
    if store_exp is None:
        # TODO: refactor to avoid panic during rename experiment
        raise MlflowException(
            f"Could not find experiment with name {experiment_name}",
            error_code=RESOURCE_DOES_NOT_EXIST,
        )
    username = get_username()
    return get_permission_from_store_or_default(
        lambda: store.get_experiment_permission(store_exp.experiment_id, username).permission,
        lambda: store.get_user_groups_experiment_permission(store_exp.experiment_id, username).permission,
    ).permission


_EXPERIMENT_ID_PATTERN = re.compile(r"^(\d+)/")


def _get_experiment_id_from_view_args():
    # TODO: check it with get_request_param("artifact_path") to replace
    if artifact_path := request.view_args.get("artifact_path"):
        if m := _EXPERIMENT_ID_PATTERN.match(artifact_path):
            return m.group(1)
    return None


def _get_permission_from_experiment_id_artifact_proxy() -> Permission:
    if experiment_id := _get_experiment_id_from_view_args():
        username = get_username()
        return get_permission_from_store_or_default(
            lambda: store.get_experiment_permission(experiment_id, username).permission,
            lambda: store.get_user_groups_experiment_permission(experiment_id, username).permission,
        ).permission
    return get_permission(config.DEFAULT_MLFLOW_PERMISSION)


def validate_can_read_experiment():
    return _get_permission_from_experiment_id().can_read


def validate_can_read_experiment_by_name():
    return _get_permission_from_experiment_name().can_read


def validate_can_update_experiment():
    return _get_permission_from_experiment_id().can_update


def validate_can_delete_experiment():
    return _get_permission_from_experiment_id().can_delete


def validate_can_manage_experiment():
    return _get_permission_from_experiment_id().can_manage


def validate_can_read_experiment_artifact_proxy():
    return _get_permission_from_experiment_id_artifact_proxy().can_read


def validate_can_update_experiment_artifact_proxy():
    return _get_permission_from_experiment_id_artifact_proxy().can_update


def validate_can_delete_experiment_artifact_proxy():
    return _get_permission_from_experiment_id_artifact_proxy().can_manage
