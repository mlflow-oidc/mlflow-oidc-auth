from flask import request
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.permissions import Permission
from mlflow_oidc_auth.utils import effective_registered_model_permission, effective_experiment_permission, get_username, get_model_name, get_model_id, get_is_admin
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
    """Validate permission for a specific registered model (requires model_name)."""
    return _get_permission_from_registered_model_name().can_manage


def validate_can_list_user_registered_model_permissions():
    """Validate permission to list registered model permissions for a user.
    
    This is for LIST endpoints like:
    - GET /api/2.0/mlflow/permissions/users/<username>/registered-models
    - GET /api/2.0/mlflow/permissions/users/<username>/prompts
    
    Returns True if:
    - User is admin, OR
    - User is requesting their own permissions
    """
    username = get_username()
    requested_user = request.view_args.get('username')
    return get_is_admin() or username == requested_user


def validate_can_read_logged_model():
    return _get_permission_from_model_id().can_read


def validate_can_update_logged_model():
    return _get_permission_from_model_id().can_update


def validate_can_delete_logged_model():
    return _get_permission_from_model_id().can_delete


def validate_can_manage_logged_model():
    return _get_permission_from_model_id().can_manage
