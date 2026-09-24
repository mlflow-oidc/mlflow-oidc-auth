from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.permissions import Permission, intersect_permissions
from mlflow_oidc_auth.utils import all_source_values, effective_scorer_permission, get_request_param_values
from mlflow_oidc_auth.validators._experiment_scope import permission_on_all_experiments


def _scorer_permission(username: str, name_field: str) -> Permission:
    # A scorer is keyed by (experiment_id, name), and either half may be named with
    # different values in different request sources (issue #285). Authorize every
    # combination the request can resolve to; the caller must hold the capability on all.
    experiment_ids = get_request_param_values("experiment_id")
    names = get_request_param_values(name_field)
    return intersect_permissions(
        effective_scorer_permission(experiment_id=experiment_id, scorer_name=name, user=username).permission
        for experiment_id in experiment_ids
        for name in names
    )


def _get_permission_from_scorer_name(username: str) -> Permission:
    return _scorer_permission(username, "name")


def _get_permission_from_scorer_permission_request(username: str) -> Permission:
    return _scorer_permission(username, "scorer_name")


def validate_can_read_scorer(username: str) -> bool:
    return _get_permission_from_scorer_name(username).can_read


def validate_can_update_scorer(username: str) -> bool:
    return _get_permission_from_scorer_name(username).can_update


def validate_can_delete_scorer(username: str) -> bool:
    return _get_permission_from_scorer_name(username).can_delete


def validate_can_manage_scorer(username: str) -> bool:
    return _get_permission_from_scorer_name(username).can_manage


def validate_can_manage_scorer_permission(username: str) -> bool:
    return _get_permission_from_scorer_permission_request(username).can_manage


def validate_can_update_online_scoring_config(username: str) -> bool:
    """UPDATE on the experiment of the scorer whose online configuration is written.

    ``PUT scorers/online-config`` is a plain JSON route keyed by ``experiment_id`` + ``name``;
    every ``experiment_id`` the request carries must be writable, and one is required.
    """
    return permission_on_all_experiments(all_source_values("experiment_id"), username).can_update


def validate_can_read_online_scoring_configs(username: str) -> bool:
    """READ on the experiment of every configuration the requested scorer ids resolve to.

    MLflow returns the stored configurations for ``scorer_ids``; each carries the experiment
    it belongs to. A request naming no scorer id is refused.
    """
    scorer_ids = [str(s) for s in all_source_values("scorer_ids")]
    if not scorer_ids:
        return False
    configs = _get_tracking_store().get_online_scoring_configs(scorer_ids)
    return all(permission_on_all_experiments([config.experiment_id], username).can_read for config in configs)
