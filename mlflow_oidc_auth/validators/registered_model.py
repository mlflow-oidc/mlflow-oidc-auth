from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.permissions import Permission, intersect_permissions
from mlflow_oidc_auth.utils import (
    effective_registered_model_permission,
    effective_new_registered_model_permission,
    effective_experiment_permission,
    get_model_names,
    get_model_ids,
    get_request_param_values,
)
from mlflow.server.handlers import _get_tracking_store


def _get_permission_from_registered_model_name(username: str) -> Permission:
    # Every model the request names, in any source (issue #285): a caller holds a
    # capability only if it holds it on all of them.
    return intersect_permissions(effective_registered_model_permission(name, username).permission for name in get_model_names())


def _permission_for_logged_model(model_id: str, username: str) -> Permission:
    # logged model permissions inherit from parent resource (experiment)
    model = _get_tracking_store().get_logged_model(model_id)
    return effective_experiment_permission(model.experiment_id, username).permission


def _get_permission_from_model_id(username: str) -> Permission:
    return intersect_permissions(_permission_for_logged_model(model_id, username) for model_id in get_model_ids())


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
    store = _get_tracking_store()
    return intersect_permissions(
        effective_experiment_permission(store.get_trace_info(request_id).experiment_id, username).permission
        for request_id in get_request_param_values("request_id")
    )


def validate_can_read_registered_model(username: str) -> bool:
    return _get_permission_from_registered_model_name(username).can_read


def validate_can_update_registered_model(username: str) -> bool:
    return _get_permission_from_registered_model_name(username).can_update


def validate_can_delete_registered_model(username: str) -> bool:
    return _get_permission_from_registered_model_name(username).can_delete


def validate_can_manage_registered_model(username: str) -> bool:
    return _get_permission_from_registered_model_name(username).can_manage


def validate_can_read_logged_model(username: str) -> bool:
    return _get_permission_from_model_id(username).can_read


def validate_can_update_logged_model(username: str) -> bool:
    return _get_permission_from_model_id(username).can_update


def validate_can_delete_logged_model(username: str) -> bool:
    return _get_permission_from_model_id(username).can_delete


def validate_can_manage_logged_model(username: str) -> bool:
    return _get_permission_from_model_id(username).can_manage


def validate_can_read_model_version_artifact(username: str) -> bool:
    """Checks READ permission on model version artifacts."""
    return _get_permission_from_model_version(username).can_read


def validate_can_read_trace_artifact(username: str) -> bool:
    """Checks READ permission on trace artifacts."""
    return _get_permission_from_trace_request_id(username).can_read


def validate_can_create_registered_model(username: str) -> bool:
    """Authorize CreateRegisteredModel when RESTRICT_RESOURCE_CREATION is enabled.

    No-op (allow) unless the flag is set. When set, the user needs EDIT+ for the
    new model name, resolved from name regex / group-regex with a workspace fallback.
    """
    if not config.RESTRICT_RESOURCE_CREATION:
        return True
    return all(effective_new_registered_model_permission(name, username).permission.can_update for name in get_model_names())
