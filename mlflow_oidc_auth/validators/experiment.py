import posixpath
from typing import Optional

from flask import request
from mlflow.server.handlers import _get_tracking_store
from mlflow.utils.uri import validate_path_is_safe

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import NO_PERMISSIONS, Permission, get_permission, intersect_permissions
from mlflow_oidc_auth.utils import (
    all_source_values,
    effective_experiment_permission,
    effective_new_experiment_permission,
    get_experiment_ids,
    get_request_param_values,
)

logger = get_logger()


def _get_permission_from_experiment_id(username: str) -> Permission:
    # Every experiment the request names, in any source — not only the one MLflow reads
    # (issue #285). A caller holds a capability only if it holds it on all of them.
    return intersect_permissions(effective_experiment_permission(experiment_id, username).permission for experiment_id in get_experiment_ids())


def _permission_for_experiment_name(experiment_name: str, username: str) -> Permission:
    store_exp = _get_tracking_store().get_experiment_by_name(experiment_name)
    if store_exp is None:
        # The experiment does not exist. This helper only gates read-by-name, so we
        # let the request proceed and MLflow return its own 404 (the UI relies on 404,
        # not 403, for a missing experiment). Do NOT reuse this helper for a mutating
        # or creation check — granting MANAGE on a non-existent name would fail open.
        return get_permission("MANAGE")
    return effective_experiment_permission(store_exp.experiment_id, username).permission


def _get_permission_from_experiment_name(username: str) -> Permission:
    return intersect_permissions(_permission_for_experiment_name(name, username) for name in get_request_param_values("experiment_name"))


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
    segments = _artifact_path_segments(artifact_path)
    if not segments:
        return None

    if segments[0] == "workspaces":
        # workspaces/{workspace_name}/{experiment_id}/...
        if len(segments) >= 3 and segments[2].isdigit():
            return segments[2]
        return None

    return segments[0] if segments[0].isdigit() else None


def _artifact_path_segments(artifact_path: str) -> list:
    """The normalized, non-empty segments of an artifact path, exactly as MLflow reads it.

    See :func:`_experiment_id_from_artifact_path` for why MLflow's own
    ``validate_path_is_safe`` is the normalizer.
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
    return [s for s in posixpath.normpath(artifact_path).split("/") if s and s != "."]


def _artifact_root_workspace(artifact_path: str) -> tuple[bool, Optional[str]]:
    """Whether ``artifact_path`` names the artifact ROOT, and the workspace it names if any.

    The root is every shape that normalizes to no segment at all — ``""``, ``"."``,
    ``"%2e"``, ``"./."``, ``".//"`` — plus ``workspaces/<ws>``, which is the root of one
    workspace's artifact tree (and what MLflow itself rewrites the root to for a
    non-default workspace). The root holds one directory per EXPERIMENT, across
    tenants, so it is never authorized as if it were an experiment's own tree.

    A path MLflow refuses outright (``..``, ``#``) is not a root: MLflow answers 400.
    """
    try:
        validate_path_is_safe(artifact_path)
    except Exception:
        return False, None
    segments = _artifact_path_segments(artifact_path)
    if not segments:
        return True, None
    if len(segments) == 2 and segments[0] == "workspaces":
        return True, segments[1]
    return False, None


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
    """The caller's permission on the experiment an artifact-proxy request names.

    A path from which no experiment resolves — the artifact root (``.``, ``%2e``,
    ``./.``, ``.//``, empty), ``workspaces/<ws>``, ``models/...``, any non-numeric first
    segment — yields ``NO_PERMISSIONS`` (issue #289). It used to yield
    ``DEFAULT_MLFLOW_PERMISSION``, which ships as MANAGE, so "could not work out which
    experiment this is" meant "allow": ``DELETE .../artifacts/.`` reached
    ``delete_artifacts(".")`` and recursively emptied every experiment's artifacts.
    """
    if experiment_id := _get_experiment_id_from_view_args():
        return effective_experiment_permission(experiment_id, username).permission
    logger.warning(f"Denying artifact-proxy {request.method} {request.path}: no experiment resolves from the artifact path")
    return NO_PERMISSIONS


_ARTIFACT_LIST_ROUTE_SUFFIX = "/mlflow-artifacts/artifacts"


def _is_artifact_list_request() -> bool:
    """True for the argument-less LIST route (``GET /mlflow-artifacts/artifacts?path=``)."""
    rule = request.url_rule
    return rule is not None and rule.rule.endswith(_ARTIFACT_LIST_ROUTE_SUFFIX)


def _artifact_list_paths() -> list:
    """Every location the LIST route may list — the union of what the request carries.

    MLflow reads ``path`` from the query string only when the method is literally GET
    and the query string is non-empty; otherwise (a HEAD, or a bare GET) it parses the
    body, which the dual-spelling guard has already required to be empty, so ``path``
    is unset and it lists the ROOT. Authorize both: every ``path`` value, and the root
    whenever MLflow may list it. ``""`` stands for the root.
    """
    paths = list(request.args.getlist("path"))
    if request.method != "GET" or not request.args or not paths:
        paths.append("")
    return paths


def is_artifact_root_listing() -> Optional[list]:
    """For a LIST request that may list an artifact root, the roots it may list.

    Returns ``None`` for any other request. Each entry is the workspace a
    ``workspaces/<ws>`` root names, or ``None`` for the plain root. Used by the
    after-request filter, which trims such a listing to experiments the caller may read.
    """
    if not _is_artifact_list_request():
        return None
    roots = [workspace for is_root, workspace in map(_artifact_root_workspace, _artifact_list_paths()) if is_root]
    return roots or None


def _can_list_artifacts(username: str) -> bool:
    """Authorize the LIST route: READ on every experiment it names; roots are filtered.

    A root location (the artifact root or ``workspaces/<ws>``) is allowed here because
    listing it is a legitimate operation — but its response is trimmed after the request
    to the experiments the caller can READ (``hooks/after_request.py``), so it no longer
    enumerates every tenant's experiment ids (issue #289). Any other location must
    resolve to an experiment the caller can READ; one that resolves to none is denied.
    """
    for path in _artifact_list_paths():
        if _artifact_root_workspace(path)[0]:
            continue
        experiment_id = _experiment_id_from_artifact_path(path)
        if experiment_id is None:
            logger.warning(f"Denying artifact list for {username}: no experiment resolves from the requested path")
            return False
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True


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
    if _is_artifact_list_request():
        return _can_list_artifacts(username)
    return _get_permission_from_experiment_id_artifact_proxy(username).can_read


def validate_can_update_experiment_artifact_proxy(username: str) -> bool:
    return _get_permission_from_experiment_id_artifact_proxy(username).can_update


def validate_can_delete_experiment_artifact_proxy(username: str) -> bool:
    return _get_permission_from_experiment_id_artifact_proxy(username).can_delete


def validate_can_read_experiments_from_experiment_ids(username: str) -> bool:
    """Validate READ permission for requests that include an experiment_ids list.

    Every id in the query string AND the body is authorized. proto-JSON accepts both ``experiment_ids`` and ``experimentIds`` and resolves a body
    carrying both to the last one (caller-controlled), so authorize the union of both
    spellings — a body cannot hide an unreadable experiment under the spelling we skip.
    """
    # MLflow reads the body on a POST and the query string on a GET; authorize both, so
    # neither can carry an experiment the other hides (issue #285).
    experiment_ids = all_source_values("experiment_ids")

    for experiment_id in experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True


def validate_can_update_experiment_from_experiment_id(username: str) -> bool:
    """Validate UPDATE permission using an explicit experiment_id parameter."""
    return all(effective_experiment_permission(e, username).permission.can_update for e in get_request_param_values("experiment_id"))


def validate_can_create_experiment(username: str) -> bool:
    """Authorize CreateExperiment when RESTRICT_RESOURCE_CREATION is enabled.

    No-op (allow) unless the flag is set. When set, the user needs EDIT+ for the
    new experiment name, resolved from name regex / group-regex with a workspace
    fallback. This composes with the workspace creation gate in before_request_hook:
    both must pass, so enabling workspaces never grants more than either check alone.
    """
    if not config.RESTRICT_RESOURCE_CREATION:
        return True
    return all(effective_new_experiment_permission(name, username).permission.can_update for name in get_request_param_values("name"))
