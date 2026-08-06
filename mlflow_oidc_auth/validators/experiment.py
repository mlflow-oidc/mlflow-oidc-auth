import posixpath

from flask import request
from mlflow.server.handlers import _get_tracking_store
from mlflow.utils.uri import validate_path_is_safe

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import Permission, get_permission
from mlflow_oidc_auth.utils import (
    effective_experiment_permission,
    effective_new_experiment_permission,
    get_experiment_id,
    get_request_param,
)

logger = get_logger()


def _get_permission_from_experiment_id(username: str) -> Permission:
    experiment_id = get_experiment_id()
    return effective_experiment_permission(experiment_id, username).permission


def _get_permission_from_experiment_name(username: str) -> Permission:
    experiment_name = get_request_param("experiment_name")
    store_exp = _get_tracking_store().get_experiment_by_name(experiment_name)
    if store_exp is None:
        # The experiment does not exist. This helper only gates read-by-name, so we
        # let the request proceed and MLflow return its own 404 (the UI relies on 404,
        # not 403, for a missing experiment). Do NOT reuse this helper for a mutating
        # or creation check — granting MANAGE on a non-existent name would fail open.
        return get_permission("MANAGE")
    return effective_experiment_permission(store_exp.experiment_id, username).permission


def _experiment_id_from_artifact_path(artifact_path: str):
    """Parse the experiment id out of a composite artifact path.

    The value is normalized through MLflow's OWN ``validate_path_is_safe``, which is
    exactly what the artifact handlers run before serving. Calling anything less than
    that whole function drifts from what MLflow acts on, and every step matters:

      1. ``_decode`` unquotes REPEATEDLY, whereas werkzeug percent-decodes a URL only
         once. Parsing the once-decoded value diverged: "%2531%2532/r/artifacts" reaches
         us as "%31%32/r/artifacts" (no match -> DEFAULT_MLFLOW_PERMISSION, i.e. allow on
         the shipped MANAGE default) while MLflow resolves it to "12/r/artifacts" and
         serves experiment 12's artifacts.
      2. ``_escape_control_characters``.
      3. ``local_file_uri_to_path`` when the value ``is_file_uri`` — so MLflow strips a
         "file:" scheme and serves "file:12/r/artifacts" as "12/r/artifacts". Calling
         only ``_decode`` left that unresolved and fell back to the MANAGE default, which
         reopened the same cross-tenant read/write/delete this function exists to close.
         "FILE:" and "%66ile:" work too, since the scheme test runs after decoding.

    ``validate_path_is_safe`` RAISES for the paths MLflow refuses outright ("..", "#").
    Those fall through to the raw value below, which is safe: MLflow rejects such a
    request with 400 before any artifact handler runs (issue #283).
    """
    try:
        artifact_path = validate_path_is_safe(artifact_path)
    except Exception:
        # Never fail the authorization check on a parsing helper; the raw value is still
        # normalized and parsed below, and MLflow rejects anything it cannot normalize
        # itself. Logged rather than silent so a future MLflow that changes this helper
        # does not quietly degrade the check.
        logger.warning("Could not normalize artifact path for authorization; parsing the raw value")

    # Match on NORMALIZED SEGMENTS rather than an anchored regex over the raw string.
    #
    # The regexes required a trailing slash after the id ("^(\d+)/"), so every path that
    # names an experiment ROOT — "12", "12/", "12//", "12/.",  "workspaces/ws/12" — failed
    # to resolve and fell back to DEFAULT_MLFLOW_PERMISSION, which allows on the shipped
    # MANAGE default. That is the most dangerous shape there is: DELETE on an experiment
    # root removes the whole artifact tree. A leading "./" defeated them the same way.
    # Splitting the normalized path handles every variant uniformly (issue #283).
    #
    # ".." is deliberately NOT resolved here — MLflow's validate_path_is_safe rejects it
    # outright, so such a request is never served.
    segments = [s for s in posixpath.normpath(artifact_path).split("/") if s and s != "."]
    if not segments:
        return None

    if segments[0] == "workspaces":
        # workspaces/{workspace_name}/{experiment_id}/...
        if len(segments) >= 3 and segments[2].isdigit():
            return segments[2]
        return None

    return segments[0] if segments[0].isdigit() else None


def _get_experiment_id_from_view_args():
    # The artifact proxy routes encode experiment_id as the first path segment
    # of the artifact_path (e.g. "123/artifacts/model.pkl").  This cannot be
    # replaced with get_request_param("artifact_path") because we need to
    # *parse* the experiment_id out of the composite path value, not just read
    # the parameter verbatim.
    view_args = request.view_args
    if view_args and (artifact_path := view_args.get("artifact_path")):
        return _experiment_id_from_artifact_path(artifact_path)

    # The LIST route (GET /mlflow-artifacts/artifacts) has no path converter, so it
    # carries no artifact_path view arg — MLflow's client passes the location in the
    # `path` QUERY parameter instead (http_artifact_repo.list_artifacts). Without this
    # the experiment could not be resolved and resolution fell back to
    # DEFAULT_MLFLOW_PERMISSION: fail-open on the shipped MANAGE default, and a 403 for
    # the rightful owner under a hardened default (issue #283).
    if query_path := request.args.get("path"):
        return _experiment_id_from_artifact_path(query_path)
    return None


def _get_permission_from_experiment_id_artifact_proxy(username: str) -> Permission:
    if experiment_id := _get_experiment_id_from_view_args():
        return effective_experiment_permission(experiment_id, username).permission
    return get_permission(config.DEFAULT_MLFLOW_PERMISSION)


def validate_can_read_experiment(username: str) -> bool:
    return _get_permission_from_experiment_id(username).can_read


def validate_can_read_experiment_by_name(username: str) -> bool:
    return _get_permission_from_experiment_name(username).can_read


def validate_can_update_experiment(username: str) -> bool:
    return _get_permission_from_experiment_id(username).can_update


def validate_can_delete_experiment(username: str) -> bool:
    return _get_permission_from_experiment_id(username).can_delete


def validate_can_manage_experiment(username: str) -> bool:
    return _get_permission_from_experiment_id(username).can_manage


def validate_can_read_experiment_artifact_proxy(username: str) -> bool:
    return _get_permission_from_experiment_id_artifact_proxy(username).can_read


def validate_can_update_experiment_artifact_proxy(username: str) -> bool:
    return _get_permission_from_experiment_id_artifact_proxy(username).can_update


def validate_can_delete_experiment_artifact_proxy(username: str) -> bool:
    return _get_permission_from_experiment_id_artifact_proxy(username).can_delete


def validate_can_read_experiments_from_experiment_ids(username: str) -> bool:
    """Validate READ permission for requests that include an experiment_ids list.

    proto-JSON accepts both ``experiment_ids`` and ``experimentIds`` and resolves a body
    carrying both to the last one (caller-controlled), so authorize the union of both
    spellings — a body cannot hide an unreadable experiment under the spelling we skip.
    """
    experiment_ids = []

    if request.method == "POST" and request.is_json:
        data = request.get_json(silent=True) or {}
        for key in ("experiment_ids", "experimentIds"):
            value = data.get(key)
            if isinstance(value, list):
                experiment_ids += value
    else:
        experiment_ids = request.args.getlist("experiment_ids")

    for experiment_id in experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True


def validate_can_update_experiment_from_experiment_id(username: str) -> bool:
    """Validate UPDATE permission using an explicit experiment_id parameter."""
    experiment_id = get_request_param("experiment_id")
    return effective_experiment_permission(experiment_id, username).permission.can_update


def validate_can_create_experiment(username: str) -> bool:
    """Authorize CreateExperiment when RESTRICT_RESOURCE_CREATION is enabled.

    No-op (allow) unless the flag is set. When set, the user needs EDIT+ for the
    new experiment name, resolved from name regex / group-regex with a workspace
    fallback. This composes with the workspace creation gate in before_request_hook:
    both must pass, so enabling workspaces never grants more than either check alone.
    """
    if not config.RESTRICT_RESOURCE_CREATION:
        return True
    experiment_name = get_request_param("name")
    return effective_new_experiment_permission(experiment_name, username).permission.can_update
