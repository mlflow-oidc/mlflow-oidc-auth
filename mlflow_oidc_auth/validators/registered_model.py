from mlflow_oidc_auth.permissions import Permission
from mlflow_oidc_auth.utils import effective_registered_model_permission, effective_experiment_permission, get_model_name, get_model_id
from mlflow.server.handlers import _get_tracking_store


def _get_permission_from_registered_model_name(username: str) -> Permission:
    model_name = get_model_name()
    return effective_registered_model_permission(model_name, username).permission


def _get_permission_from_model_id(username: str) -> Permission:
    # logged model permissions inherit from parent resource (experiment)
    model_id = get_model_id()
    model = _get_tracking_store().get_logged_model(model_id)
    experiment_id = model.experiment_id
    return effective_experiment_permission(experiment_id, username).permission


def validate_can_read_registered_model(username: str):
    return _get_permission_from_registered_model_name(username).can_read


def validate_can_update_registered_model(username: str):
    return _get_permission_from_registered_model_name(username).can_update


def validate_can_delete_registered_model(username: str):
    return _get_permission_from_registered_model_name(username).can_delete


def validate_can_manage_registered_model(username: str):
    return _get_permission_from_registered_model_name(username).can_manage


def validate_can_read_logged_model(username: str):
    return _get_permission_from_model_id(username).can_read


def validate_can_update_logged_model(username: str):
    return _get_permission_from_model_id(username).can_update


def validate_can_delete_logged_model(username: str):
    return _get_permission_from_model_id(username).can_delete


def validate_can_manage_logged_model(username: str):
    return _get_permission_from_model_id(username).can_manage
