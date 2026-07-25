import re

from flask import request
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.permissions import NO_PERMISSIONS, Permission, get_permission
from mlflow_oidc_auth.utils import (
    effective_experiment_permission,
    effective_new_experiment_permission,
    get_experiment_id,
    get_request_param,
)


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


_EXPERIMENT_ID_PATTERN = re.compile(r"^(\d+)/")
# Workspace paths are structured: workspaces/{workspace-name}/{experiment-id}/...
# where the workspace name can be alphanumeric with an optional single hyphen.
_WORKSPACES_EXPERIMENT_ID_PATTERN = re.compile(r"^(workspaces)/([\w-]+)/(\d+)/")


def _get_experiment_id_from_view_args():
    # The artifact proxy routes encode experiment_id as the first path segment
    # of the artifact_path (e.g. "123/artifacts/model.pkl").  This cannot be
    # replaced with get_request_param("artifact_path") because we need to
    # *parse* the experiment_id out of the composite path value, not just read
    # the parameter verbatim.
    experiment_id, _ = _parse_artifact_path()
    return experiment_id


def _parse_artifact_path() -> tuple[str | None, str | None]:
    """Return ``(experiment_id, workspace)`` parsed from the artifact proxy path.

    Workspace-scoped artifact paths carry the workspace themselves
    ("workspaces/{name}/{experiment_id}/..."), which matters because the artifact
    proxy is the one authenticated path where the workspace is NOT available from
    the ``X-MLFLOW-WORKSPACE`` header — MLflow's ``http_artifact_repo`` does not
    send it (issue #236). ``workspace`` is None for non-workspace paths.
    """
    view_args = request.view_args
    if view_args is not None and (artifact_path := view_args.get("artifact_path")):
        if m := _EXPERIMENT_ID_PATTERN.match(artifact_path):
            return m.group(1), None
        if m := _WORKSPACES_EXPERIMENT_ID_PATTERN.match(artifact_path):
            # Group 1: literal "workspaces", Group 2: {workspace_name}, Group 3: experiment-id
            return m.group(3), m.group(2)
    return None, None


def _get_permission_from_experiment_id_artifact_proxy(username: str) -> Permission:
    experiment_id, path_workspace = _parse_artifact_path()
    if not experiment_id:
        return get_permission(config.DEFAULT_MLFLOW_PERMISSION)

    result = effective_experiment_permission(experiment_id, username)

    # Apply the workspace fallback using the workspace named in the PATH.
    #
    # Everywhere else the workspace arrives in the X-MLFLOW-WORKSPACE header, so
    # resolve_permission's own fallback covers it. MLflow's proxied-artifact client
    # does not send that header, so without this a user whose only grant is on the
    # workspace fell through to DEFAULT_MLFLOW_PERMISSION and got 403 on upload
    # (issue #236). The workspace is taken from the same path segment the
    # experiment_id is taken from, and is the workspace MLflow will itself resolve
    # the storage location from, so the two checks cannot disagree.
    if result.kind == "fallback" and config.MLFLOW_ENABLE_WORKSPACES and path_workspace:
        from mlflow_oidc_auth.bridge.user import get_request_workspace
        from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached

        if not get_request_workspace():
            ws_perm = get_workspace_permission_cached(username, path_workspace)
            # Deny when the user holds nothing on the workspace, matching
            # _apply_workspace_fallback's "workspace-deny" rather than silently
            # falling back to the global default.
            return ws_perm if ws_perm is not None else NO_PERMISSIONS

    return result.permission


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
