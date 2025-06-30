from mlflow_oidc_auth.permissions import Permission
from mlflow_oidc_auth.utils import effective_registered_model_permission, effective_experiment_permission, get_username, get_model_name, get_model_id
from mlflow.server.handlers import _get_tracking_store


def _get_permission_from_registered_model_name() -> Permission:
    model_name = get_model_name()
    username = get_username()
    return effective_registered_model_permission(model_name, username).permission


def _get_permission_from_model_id() -> Permission:
    # logged model permissions inherit from parent resource (experiment)
    model_id = get_model_id()
    model = _get_tracking_store().get_logged_model(model_id)
    experiment_id = model.experiment_id
    username = get_username()
    return effective_experiment_permission(experiment_id, username).permission


def validate_can_read_registered_model():
    return _get_permission_from_registered_model_name().can_read


def validate_can_update_registered_model():
    return _get_permission_from_registered_model_name().can_update


def validate_can_delete_registered_model():
    return _get_permission_from_registered_model_name().can_delete


def validate_can_manage_registered_model():
    return _get_permission_from_registered_model_name().can_manage


def validate_can_read_logged_model():
    return _get_permission_from_model_id().can_read


def validate_can_update_logged_model():
    return _get_permission_from_model_id().can_update


def validate_can_delete_logged_model():
    return _get_permission_from_model_id().can_delete


def validate_can_manage_logged_model():
    return _get_permission_from_model_id().can_manage
