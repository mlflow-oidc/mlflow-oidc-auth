from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.permissions import Permission, intersect_permissions
from mlflow_oidc_auth.utils import all_source_values, effective_scorer_permission, get_request_param_values
from mlflow_oidc_auth.validators._experiment_scope import permission_on_all_experiments
from mlflow_oidc_auth.validators.experiment import validate_can_update_experiment


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


def scorer_has_versions(experiment_id: str, name: str) -> bool:
    """Whether MLflow still holds at least one version of the scorer.

    A scorer record outlives its versions when they are deleted one at a time, so the
    record alone is not existence: ``get_scorer`` without a version raises
    RESOURCE_DOES_NOT_EXIST once none is left. Any other failure answers True, which
    keeps both callers on their stricter path (require scorer UPDATE; keep grants).

    Parameters:
        experiment_id: The scorer's experiment.
        name: The scorer name.

    Returns:
        False only when MLflow reports the scorer (or its experiment) does not exist.
    """
    try:
        _get_tracking_store().get_scorer(str(experiment_id), str(name))
    except MlflowException as e:
        return e.error_code != ErrorCode.Name(RESOURCE_DOES_NOT_EXIST)
    except Exception:
        return True
    return True


# Sources that name this exact scorer. A regex grant also matches names nobody has
# registered yet, so it does not by itself gate the creation of a new one.
_EXACT_SCORER_GRANT_KINDS = frozenset({"user", "group"})


def _can_register(experiment_id: str, name: str, username: str) -> bool:
    result = effective_scorer_permission(experiment_id=str(experiment_id), scorer_name=str(name), user=username)
    if result.kind in _EXACT_SCORER_GRANT_KINDS or scorer_has_versions(experiment_id, name):
        return result.permission.can_update
    return True


def validate_can_register_scorer(username: str) -> bool:
    """UPDATE on the experiment; UPDATE on the scorer too when it exists or is granted.

    ``RegisterScorer`` on an existing (experiment_id, name) appends a version that becomes
    the scorer's current definition, so it is an update of that scorer and scorer-level
    grants apply as they do to every other scorer write. A user or group grant on the
    name binds even before the first version exists, so a grant set up ahead of creation
    cannot be stepped around by registering first. Otherwise a new name needs only the
    experiment permission. Every experiment id and name the request carries, in any
    source, is checked.
    """
    if not validate_can_update_experiment(username):
        return False
    return all(_can_register(e, n, username) for e in all_source_values("experiment_id") for n in all_source_values("name"))


def validate_can_list_scorers(username: str) -> bool:
    """READ on the experiment when ``ListScorers`` names one; otherwise any authenticated user.

    ``ListScorers`` takes an optional ``experiment_id``. Without one MLflow lists the scorers
    of every active experiment, and the after-request filter removes each scorer the caller
    cannot read, so the request itself is allowed. When an experiment id is present in any
    request source, READ is required on every experiment named, as before.

    Parameters:
        username: The caller.

    Returns:
        True if the request may proceed.
    """
    if not all_source_values("experiment_id"):
        return True
    return permission_on_all_experiments(get_request_param_values("experiment_id"), username).can_read


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
    """UPDATE on the experiment AND on the scorer whose online configuration is written.

    ``PUT scorers/online-config`` is a plain JSON route keyed by ``experiment_id`` + ``name``.
    Every experiment id and every scorer name the request carries, in any source, is
    checked, and both are required. Scorer-level grants apply as they do to GetScorer.
    """
    experiment_ids = all_source_values("experiment_id")
    names = all_source_values("name")
    if not names or not permission_on_all_experiments(experiment_ids, username).can_update:
        return False
    return all(
        effective_scorer_permission(experiment_id=str(e), scorer_name=str(n), user=username).permission.can_update for e in experiment_ids for n in names
    )


def validate_can_read_online_scoring_configs(username: str) -> bool:
    """READ on the experiment AND on the scorer of every configuration the ids resolve to.

    MLflow returns the stored configurations for ``scorer_ids``; each carries its scorer id
    and experiment. The scorer's name (needed for scorer-level grants) is looked up among
    that experiment's scorers; a configuration whose scorer cannot be found is refused, as
    is a request naming no scorer id.
    """
    scorer_ids = [str(s) for s in all_source_values("scorer_ids")]
    if not scorer_ids:
        return False
    tracking_store = _get_tracking_store()
    names_by_experiment: dict = {}
    for config in tracking_store.get_online_scoring_configs(scorer_ids):
        experiment_id = str(config.experiment_id)
        if not permission_on_all_experiments([experiment_id], username).can_read:
            return False
        if experiment_id not in names_by_experiment:
            names_by_experiment[experiment_id] = {str(v.scorer_id): v.scorer_name for v in tracking_store.list_scorers(experiment_id) if v.scorer_id}
        name = names_by_experiment[experiment_id].get(str(config.scorer_id))
        if name is None or not effective_scorer_permission(experiment_id=experiment_id, scorer_name=name, user=username).permission.can_read:
            return False
    return True
