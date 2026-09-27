import urllib.parse

from mlflow.exceptions import MlflowException
from mlflow.store.artifact.runs_artifact_repo import RunsArtifactRepository
from mlflow.store.artifact.utils.models import _parse_model_uri
from mlflow.utils.uri import is_models_uri

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.permissions import Permission, intersect_permissions
from mlflow_oidc_auth.validators._referenced import body_has_field, referenced_logged_model_permission, referenced_run_permission
from mlflow_oidc_auth.utils import (
    all_source_values,
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


def _model_version_source_references(sources: list) -> tuple[list[str], list[str], list[str]] | None:
    """Split ``source`` values into the registered models, runs and logged models they name.

    Parameters:
        sources: Every ``source`` value the request carries.

    Returns:
        ``(registered_model_names, run_ids, logged_model_ids)``, or ``None`` when a
        ``models:/`` or ``runs:/`` source cannot be parsed (deny).
    """
    names: list[str] = []
    run_ids: list[str] = []
    model_ids: list[str] = []
    for source in sources:
        source = str(source)
        try:
            if is_models_uri(source):
                parsed = _parse_model_uri(source)
                if parsed.name is not None:
                    names.append(parsed.name)
                elif parsed.model_id:
                    model_ids.append(parsed.model_id)
            elif urllib.parse.urlparse(source).scheme == "runs":
                run_ids.append(RunsArtifactRepository.parse_runs_uri(source)[0])
        except (MlflowException, ValueError):
            return None
    return names, run_ids, model_ids


def validate_can_create_model_version(username: str) -> bool:
    """Authorize CreateModelVersion on the destination model and on the version's source.

    Mirrors MLflow's own ``validate_can_create_model_version``. Artifact reads on a model
    version are gated on its registered model, so creating one must not reach artifacts
    the caller cannot already read. The caller needs:

    - UPDATE on the registered model the version is created in;
    - when ``source`` is ``models:/<name>/...``: READ on that registered model, which is
      then the artifact boundary, so ``run_id`` is lineage metadata and is not checked.
      This applies only when every ``source`` value in the request is such a URI;
    - otherwise READ on every ``run_id`` the request carries, and on the run a
      ``runs:/<run_id>/...`` source names;
    - in every case READ on every ``model_id`` the request carries, and on the logged
      model a ``models:/<model_id>`` source names. MLflow tags the logged model named by
      ``model_id`` with the new version, so it is checked even for a ``models:/<name>``
      source (MLflow's own plugin skips it there).

    A ``run_id`` / ``model_id`` key that is present but empty, a source that cannot be
    parsed, and a referenced run or logged model that does not exist are all denied.

    Parameters:
        username: The authenticated user.

    Returns:
        True when every check passes.
    """
    if not validate_can_update_registered_model(username):
        return False

    sources = all_source_values("source")
    references = _model_version_source_references(sources)
    if references is None:
        return False
    source_names, source_run_ids, source_model_ids = references

    if not all(effective_registered_model_permission(name, username).permission.can_read for name in source_names):
        return False
    model_ids = all_source_values("model_id")
    if body_has_field("model_id") and not model_ids:
        return False
    # The run exemption holds only when EVERY source value names a registered model;
    # a second source elsewhere in the request could be the one MLflow acts on.
    if not (sources and len(source_names) == len(sources)):
        run_ids = all_source_values("run_id")
        if body_has_field("run_id") and not run_ids:
            return False
        for run_id in dict.fromkeys(str(r) for r in [*run_ids, *source_run_ids]):
            if not referenced_run_permission(run_id, username).can_read:
                return False
    for model_id in dict.fromkeys(str(m) for m in [*model_ids, *source_model_ids]):
        if not referenced_logged_model_permission(model_id, username).can_read:
            return False
    return True
