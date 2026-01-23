from mlflow_oidc_auth.permissions import Permission
from mlflow_oidc_auth.utils import effective_scorer_permission, get_request_param


def _get_permission_from_scorer_name(username: str) -> Permission:
    experiment_id = get_request_param("experiment_id")
    name = get_request_param("name")
    return effective_scorer_permission(experiment_id=experiment_id, scorer_name=name, user=username).permission


def _get_permission_from_scorer_permission_request(username: str) -> Permission:
    experiment_id = get_request_param("experiment_id")
    scorer_name = get_request_param("scorer_name")
    return effective_scorer_permission(experiment_id=experiment_id, scorer_name=scorer_name, user=username).permission


def validate_can_read_scorer(username: str):
    return _get_permission_from_scorer_name(username).can_read


def validate_can_update_scorer(username: str):
    return _get_permission_from_scorer_name(username).can_update


def validate_can_delete_scorer(username: str):
    return _get_permission_from_scorer_name(username).can_delete


def validate_can_manage_scorer(username: str):
    return _get_permission_from_scorer_name(username).can_manage


def validate_can_manage_scorer_permission(username: str):
    return _get_permission_from_scorer_permission_request(username).can_manage
