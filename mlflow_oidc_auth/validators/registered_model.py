from mlflow_oidc_auth.permissions import Permission
from mlflow_oidc_auth.utils import effective_registered_model_permission, effective_new_registered_model_permission, effective_experiment_permission, get_model_name, get_model_id, get_request_param
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


def _get_permission_from_model_version(username: str) -> Permission:
    """
    Get permission for model version artifacts.
    Model versions inherit permissions from their registered model.
    """
    return _get_permission_from_registered_model_name(username)


def _get_permission_from_trace_request_id(username: str) -> Permission:
    """
    Get permission for trace artifacts.
    Traces inherit permissions from their parent run/experiment.
    """
    request_id = get_request_param("request_id")
    # Get the trace to find its experiment
    trace = _get_tracking_store().get_trace_info(request_id)
    experiment_id = trace.experiment_id

    return effective_experiment_permission(experiment_id, username).permission


def validate_can_create_registered_model(username: str):
    model_name = get_model_name()
    return effective_new_registered_model_permission(model_name, username).permission.can_update


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


def validate_can_read_model_version_artifact(username: str):
    """Checks READ permission on model version artifacts."""
    return _get_permission_from_model_version(username).can_read


def validate_can_read_trace_artifact(username: str):
    """Checks READ permission on trace artifacts."""
    return _get_permission_from_trace_request_id(username).can_read
