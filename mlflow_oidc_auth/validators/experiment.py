import posixpath
from urllib.parse import urlparse

from flask import request
from mlflow.server.handlers import _get_tracking_store
from mlflow.utils.uri import validate_path_is_safe

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import NO_PERMISSIONS, Permission, get_permission
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
    segments = _artifact_path_segments(artifact_path)
    if not segments:
        return None

    if segments[0] == "workspaces":
        # workspaces/{workspace_name}/{experiment_id}/...
        if len(segments) >= 3 and segments[2].isdigit():
            return segments[2]
        return None

    if segments[0].isdigit():
        return segments[0]

    # The artifact root may carry a PREFIX, in which case the experiment id is not the
    # first segment. `--default-artifact-root mlflow-artifacts:/mlartifacts` makes every
    # run's proxy path "mlartifacts/{experiment_id}/{run_id}/artifacts/...", and a
    # per-experiment or per-workspace artifact_location can add an arbitrary prefix too.
    # Anchoring on segment 0 resolves nothing for those deployments (issue #289).
    return _experiment_id_via_run_lookup(segments)


def _experiment_id_via_run_lookup(segments: list):
    """Ask the store which experiment owns this path, instead of guessing from position.

    An earlier attempt read the experiment id positionally — two segments before the first
    ``artifacts`` component — on the theory that MLflow always lays a run's artifacts out
    as ``<root...>/{experiment_id}/{run_id}/artifacts/...``. The path is entirely
    caller-controlled and MLflow serves it verbatim relative to the artifacts destination,
    so trusting a position in it is trusting the attacker. Both directions were reachable:

      * ``mlartifacts/7/3/runX/artifacts/evil.txt`` — a caller holding a grant on
        experiment 3 and nothing else supplies both the ``artifacts`` component and the
        digit two before it, so the check passes on experiment 3 while MLflow writes the
        bytes inside experiment 7's tree.
      * an ``artifact_location`` whose last segment is digits (``mlflow-artifacts:/teams/12``)
        made every path under it resolve to "12" — denying the rightful owner and granting
        whoever holds experiment 12.

    So resolve it authoritatively. The component before the ``artifacts`` marker is the run
    id; the store knows which experiment that run belongs to and where its artifacts
    actually live. The request is only attributed to that experiment when it genuinely
    falls INSIDE the run's own artifact location — which is what makes an injected digit,
    or a real run id spliced under someone else's prefix, resolve to nothing.

    Returning None here does not deny by itself; it falls through to the caller's handling
    for an unresolvable path (see _get_permission_from_experiment_id_artifact_proxy), so a
    layout this cannot decompose behaves exactly as it did before any of this work.
    """
    index = _first_artifacts_marker(segments)
    if index is None or index < 1:
        return None

    try:
        run = _get_tracking_store().get_run(segments[index - 1])
    except Exception:
        # No such run, or the store is unhappy. Not something to authorize on.
        return None

    owner_segments = _proxy_path_segments(getattr(run.info, "artifact_uri", None))
    if not owner_segments or segments[: len(owner_segments)] != owner_segments:
        # The request is not inside this run's artifact tree, so the run tells us nothing
        # about who owns the bytes MLflow would serve.
        return None
    return run.info.experiment_id


def _proxy_path_segments(artifact_uri):
    """The proxy-relative components of an ``mlflow-artifacts:`` URI, or None.

    A run stored anywhere else (s3:, file:, ...) is not served through this proxy, so its
    location cannot corroborate a proxy request.
    """
    if not artifact_uri:
        return None
    parsed = urlparse(str(artifact_uri))
    if parsed.scheme != "mlflow-artifacts":
        return None
    return _artifact_path_segments(parsed.path)


def _artifact_path_segments(artifact_path: str) -> list:
    """Decode exactly as MLflow does, then split into meaningful path components.

    The decode lives HERE, in the one place both the experiment-id parser and the
    root-scope check go through, so the two can never disagree about what a path says.
    Keeping them separate is precisely how "%2e" slipped past the root check while
    resolving to "." for MLflow — the same parse-it-two-ways bug this module exists to
    prevent.
    """
    try:
        artifact_path = validate_path_is_safe(artifact_path)
    except Exception:
        # Never fail the authorization check on a parsing helper; the raw value is still
        # normalized below, and MLflow rejects anything it cannot normalize itself. Logged
        # rather than silent so a future MLflow that changes this helper does not quietly
        # degrade the check.
        logger.warning("Could not normalize artifact path for authorization; parsing the raw value")
    return [s for s in posixpath.normpath(artifact_path).split("/") if s and s != "."]


def _first_artifacts_marker(segments: list):
    """Index of the first component that is exactly ``artifacts``, or None.

    Matched as a whole component so an artifact root merely CONTAINING the word (say
    ``my-artifacts/``) is not mistaken for the run's artifact directory.
    """
    for index, segment in enumerate(segments):
        if segment == "artifacts":
            return index
    return None


def _artifact_request_targets_the_whole_root(artifact_path: str) -> bool:
    """True when the path names the shared artifact ROOT rather than anything within it.

    These are the shapes where MLflow acts on EVERY tenant's data at once, so they can
    never be authorized by a per-experiment permission:

      * "", ".", "%2e", "./.", ".//"   -> the proxy root itself. DELETE here reaches
        ``delete_artifacts(".")``, which recursively empties every experiment's artifacts;
        GET returns a listing that enumerates every experiment id on the server.
      * "workspaces" / "workspaces/<ws>" -> a whole workspace, i.e. a whole tenant.

    Deliberately narrow. A path that merely fails to RESOLVE (an artifact root with a
    prefix we cannot decompose) is not root-scoped and must not be denied on that basis —
    see _get_permission_from_experiment_id_artifact_proxy.
    """
    segments = _artifact_path_segments(artifact_path)
    if not segments:
        return True
    return segments[0] == "workspaces" and len(segments) <= 2


def _artifact_path_from_request():
    """The artifact path this request acts on, or None if it names none.

    The proxy routes carry it as a path converter; the LIST route
    (GET /mlflow-artifacts/artifacts) has no converter and MLflow's client passes the
    location in the ``path`` QUERY parameter instead (http_artifact_repo.list_artifacts).
    """
    view_args = request.view_args
    if view_args and (artifact_path := view_args.get("artifact_path")):
        return artifact_path
    return request.args.get("path")


def _get_experiment_id_from_view_args():
    # The artifact proxy routes encode experiment_id inside the composite artifact_path
    # (e.g. "123/artifacts/model.pkl"). This cannot be replaced with
    # get_request_param("artifact_path") because we need to *parse* the experiment_id out
    # of the value, not read the parameter verbatim.
    artifact_path = _artifact_path_from_request()
    if artifact_path is None:
        return None
    return _experiment_id_from_artifact_path(artifact_path)


def _get_permission_from_experiment_id_artifact_proxy(username: str) -> Permission:
    """Resolve the permission for an artifact-proxy request.

    Three outcomes, and the distinction between the last two matters a great deal:

    1. The path names an experiment -> the permission store decides. This now works for a
       prefixed artifact root as well, by anchoring on the "artifacts" marker rather than
       on segment 0.

    2. The path names the shared ROOT (``.``, ``%2e``, an empty ``?path=``, or
       ``workspaces/<ws>``) -> DENY. MLflow acts on every tenant's data at once for these,
       so no per-experiment permission can authorize them, and the previous fallback to
       ``config.DEFAULT_MLFLOW_PERMISSION`` — which ships as MANAGE — made them ALLOW for
       any authenticated user with no grants at all (issue #289). ``DELETE
       /mlflow-artifacts/artifacts/.`` reaches ``delete_artifacts(".")`` and recursively
       empties every experiment's artifacts; the GET enumerates every experiment id.

    3. The path names something we cannot decompose -> fall back to the configured
       default, exactly as before. This branch exists because denying here caused a total
       outage: an artifact root with a prefix this parser cannot break down (a
       per-experiment ``artifact_location``, or a per-workspace ``default_artifact_root``,
       which this plugin's own workspace API exposes) yields paths like
       ``team-a/proj/{run_id}/artifacts``. Denying those refuses every read, write and
       delete for the user who legitimately holds MANAGE, and because the store is never
       consulted NO grant can restore access — only the admin bypass. Failing closed on a
       path we merely failed to PARSE is not a security win, it is an outage.

    So the fail-closed behaviour is deliberately scoped to the shapes that are provably
    root-scoped, not to everything unresolvable. Case 3 is no worse than before this
    change; cases 1 and 2 are both strictly better.

    This does NOT change ``DEFAULT_MLFLOW_PERMISSION`` globally (see #80).
    """
    if experiment_id := _get_experiment_id_from_view_args():
        return effective_experiment_permission(experiment_id, username).permission

    artifact_path = _artifact_path_from_request()
    if artifact_path is None or _artifact_request_targets_the_whole_root(artifact_path):
        logger.warning(
            "Denying artifact-proxy request for %s: path %r targets the shared artifact root, " "which no per-experiment permission can grant",
            username,
            artifact_path,
        )
        return NO_PERMISSIONS

    logger.warning(
        "Could not resolve an experiment from artifact path %r; falling back to the configured "
        "default permission. If this is a prefixed artifact root, the prefix is not one this "
        "parser recognises.",
        artifact_path,
    )
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
