"""Authorization for CreateModelVersion: the destination model and the version's source.

Artifact reads on a model version (``model-versions/get-artifact``, the download URI) are
gated on the version's registered model only. A version whose ``source`` points into
another experiment's artifacts would therefore expose them to anyone who can read the
registered model, so creating a version requires a grant on everything its ``source``,
``run_id`` and ``model_id`` point at. See :func:`validate_can_create_model_version`.
"""

from __future__ import annotations

import posixpath
import re
import urllib.parse
from typing import NamedTuple, Optional

from mlflow.exceptions import MlflowException
from mlflow.prompt.constants import IS_PROMPT_TAG_KEY
from mlflow.server.handlers import _get_model_registry_store
from mlflow.store.artifact.runs_artifact_repo import RunsArtifactRepository
from mlflow.store.artifact.utils.models import _parse_model_uri, get_model_name_and_version
from mlflow.utils.file_utils import local_file_uri_to_path
from mlflow.utils.uri import is_models_uri

from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.utils import all_source_values, effective_registered_model_permission, request_body_dict
from mlflow_oidc_auth.validators._referenced import (
    body_has_field,
    referenced_experiment_permission,
    referenced_logged_model,
    referenced_logged_model_permission,
    referenced_run,
    referenced_run_permission,
)
from mlflow_oidc_auth.validators.experiment import _experiment_id_from_artifact_path
from mlflow_oidc_auth.validators.registered_model import validate_can_update_registered_model

logger = get_logger()

# The placeholder sources MLflow's own clients send for a prompt version (the Python client
# and the MLflow UI send "dummy-source"; the registry store's prompt helper "prompt-template").
# A prompt version's source is not used to serve artifacts by those clients.
PROMPT_PLACEHOLDER_SOURCES = frozenset({"dummy-source", "prompt-template"})

# MLflow serves an http(s) proxied artifact location by splitting its path on this anchor
# (``_get_proxied_run_artifact_destination_path``).
_PROXY_ROUTE_ANCHOR = "/api/2.0/mlflow-artifacts/artifacts/"


class _SourceReferences(NamedTuple):
    registry_uris: list  # models:/<name>/<version|alias|stage|latest>
    run_ids: list  # runs:/<run_id>/...
    model_ids: list  # models:/<model_id>
    storage_uris: list  # any other location: must lie under a referenced run / logged model


def _has_relative_segment(source: str) -> bool:
    """True when the fully unquoted source has a ``..`` segment or a NUL (MLflow refuses both)."""
    while (unquoted := urllib.parse.unquote_plus(source)) != source:
        source = unquoted
    # urlsplit drops tab, CR and LF, so a segment split by them still reads as ".." later.
    source = re.sub(r"[\t\r\n]", "", source)
    return "\x00" in source or any(part == ".." for part in source.replace("\\", "/").split("/"))


def _proxied_artifact_path(source: str) -> Optional[str]:
    """The artifact-proxy path a proxied ``source`` names, or ``None`` if it is not proxied.

    Mirrors ``_get_proxied_run_artifact_destination_path``: an ``mlflow-artifacts`` URI's
    path, or the part of an http(s) URL's path after ``/api/2.0/mlflow-artifacts/artifacts/``.
    """
    parsed = urllib.parse.urlparse(source)
    scheme = parsed.scheme.lower()
    if scheme == "mlflow-artifacts":
        return parsed.path.lstrip("/")
    if scheme in ("http", "https") and _PROXY_ROUTE_ANCHOR in parsed.path:
        return parsed.path.split(_PROXY_ROUTE_ANCHOR)[1]
    return None


def _is_prompt_request() -> bool:
    """True when the request is for a prompt version, as MLflow's ``_is_prompt_request`` decides."""
    tags = request_body_dict().get("tags")
    return isinstance(tags, list) and any(isinstance(tag, dict) and tag.get("key") == IS_PROMPT_TAG_KEY for tag in tags)


def _classify_sources(sources: list, username: str, is_prompt: bool) -> Optional[_SourceReferences]:
    """Sort every ``source`` value by what it points at, checking proxied locations directly.

    Parameters:
        sources: Every ``source`` value the request carries.
        username: The authenticated user.
        is_prompt: Whether the request creates a prompt version.

    Returns:
        The references still to be checked, or ``None`` to deny (an unparseable source, a
        relative path segment, or a proxied location on an experiment the caller cannot
        read).
    """
    refs = _SourceReferences([], [], [], [])
    for value in sources:
        source = str(value)
        if _has_relative_segment(source):
            return None
        if is_prompt and source in PROMPT_PLACEHOLDER_SOURCES:
            continue
        try:
            if is_models_uri(source):
                parsed = _parse_model_uri(source)
                if parsed.name is not None:
                    refs.registry_uris.append(source)
                elif parsed.model_id:
                    refs.model_ids.append(parsed.model_id)
                else:
                    return None
                continue
            if urllib.parse.urlparse(source).scheme.lower() == "runs":
                refs.run_ids.append(RunsArtifactRepository.parse_runs_uri(source)[0])
                continue
        except (MlflowException, ValueError):
            return None
        proxied = _proxied_artifact_path(source)
        if proxied is not None:
            experiment_id = _experiment_id_from_artifact_path(proxied)
            if not referenced_experiment_permission(experiment_id, username).can_read:
                return None
            continue
        refs.storage_uris.append(source)
    return refs


def _source_model_version_model_id(registry_uri: str) -> Optional[str]:
    """The ``model_id`` of the model version a ``models:/<name>/...`` URI resolves to, if any.

    A version that cannot be resolved has no ``model_id`` to match, so any ``model_id`` in
    the request then needs UPDATE on its logged model (the stricter check).
    """
    registry_store = _get_model_registry_store()
    try:
        name, version = get_model_name_and_version(registry_store, registry_uri)
        return registry_store.get_model_version(name, version).model_id or None
    except MlflowException:
        logger.debug("Could not resolve the source model version of a copy")
        return None


def _location_key(uri: str) -> tuple[str, str, str]:
    """``(scheme, netloc, normalised path)`` for comparing storage locations."""
    parsed = urllib.parse.urlparse(uri)
    scheme = parsed.scheme.lower()
    if scheme in ("", "file") or len(scheme) == 1:  # a local path, a file: URI, or a Windows drive
        path = local_file_uri_to_path(uri).replace("\\", "/")
        return "file", "", posixpath.normpath(path) if path else ""
    return scheme, parsed.netloc, posixpath.normpath(parsed.path) if parsed.path else "/"


def is_under_location(source: str, root: str) -> bool:
    """True when ``source`` is ``root`` or lies beneath it, compared on path boundaries.

    Parameters:
        source: The model version source.
        root: A run's ``artifact_uri`` or a logged model's ``artifact_location``.

    Returns:
        Whether ``source`` is inside ``root``.
    """
    if not source or not root:
        return False
    s_scheme, s_netloc, s_path = _location_key(source)
    r_scheme, r_netloc, r_path = _location_key(root)
    if (s_scheme, s_netloc) != (r_scheme, r_netloc) or not r_path.startswith("/") or not s_path.startswith("/"):
        return False
    return s_path == r_path or s_path.startswith(r_path.rstrip("/") + "/")


def _artifact_roots(run_ids: list, model_ids: list) -> Optional[list[str]]:
    """The artifact roots of the given runs and logged models; ``None`` if one does not exist."""
    roots: list[str] = []
    for run_id in run_ids:
        run = referenced_run(run_id)
        if run is None:
            return None
        roots.append(run.info.artifact_uri)
    for model_id in model_ids:
        model = referenced_logged_model(model_id)
        if model is None:
            return None
        roots.append(model.artifact_location)
    return [root for root in roots if root]


def validate_can_create_model_version(username: str) -> bool:
    """Authorize CreateModelVersion on the destination model and on what the version points at.

    Mirrors, and in places extends, MLflow's own ``validate_can_create_model_version``.
    The caller needs UPDATE on the destination registered model, and for every ``source``
    value in the request:

    - ``models:/<name>/<version|alias|stage|latest>``: READ on that registered model.
      When every source is such a URI (a copy, as ``copy_model_version`` makes), the
      registered model is the access boundary: ``run_id`` is lineage metadata and is not
      checked, and a ``model_id`` equal to the source version's own ``model_id`` needs
      READ on that logged model. Any other ``model_id`` needs UPDATE on its logged model, because
      MLflow tags the logged model named by ``model_id`` with the new version.
    - ``models:/<model_id>``: READ on that logged model.
    - ``runs:/<run_id>/...``: READ on that run.
    - ``mlflow-artifacts:/...`` or an http(s) URL on the artifact proxy route: READ on the
      experiment the artifact path names (``<experiment_id>/...`` or
      ``workspaces/<ws>/<experiment_id>/...``). A path naming no existing experiment is
      denied.
    - A prompt version with MLflow's placeholder source (``dummy-source`` /
      ``prompt-template``): nothing more.
    - Any other location (``s3://``, ``gs://``, a local path, ...): it must lie under the
      artifact root of a ``run_id`` or ``model_id`` the request names. With neither id
      the request is refused (administrators are not checked).

    Outside the copy case, READ is required on every ``run_id`` and ``model_id``. A
    ``run_id`` / ``model_id`` that is present but empty, a source that cannot be parsed or
    has a ``..`` segment, and a referenced resource that does not exist are all denied.

    Parameters:
        username: The authenticated user.

    Returns:
        True when every check passes.
    """
    if not validate_can_update_registered_model(username):
        return False

    sources = all_source_values("source")
    refs = _classify_sources(sources, username, _is_prompt_request())
    if refs is None:
        return False

    for registry_uri in refs.registry_uris:
        if not effective_registered_model_permission(_parse_model_uri(registry_uri).name, username).permission.can_read:
            return False

    model_ids = [str(m) for m in all_source_values("model_id")]
    if body_has_field("model_id") and not model_ids:
        return False

    copy_only = bool(sources) and len(refs.registry_uris) == len(sources)
    if copy_only:
        lineage_ids = {mid for mid in (_source_model_version_model_id(uri) for uri in refs.registry_uris) if mid}
        return all(
            (
                referenced_logged_model_permission(model_id, username).can_read
                if model_id in lineage_ids
                else referenced_logged_model_permission(model_id, username).can_update
            )
            for model_id in dict.fromkeys(model_ids)
        )

    run_ids = [str(r) for r in all_source_values("run_id")]
    if body_has_field("run_id") and not run_ids:
        return False
    for run_id in dict.fromkeys([*run_ids, *refs.run_ids]):
        if not referenced_run_permission(run_id, username).can_read:
            return False
    for model_id in dict.fromkeys([*model_ids, *refs.model_ids]):
        if not referenced_logged_model_permission(model_id, username).can_read:
            return False

    if refs.storage_uris:
        roots = _artifact_roots(list(dict.fromkeys(run_ids)), list(dict.fromkeys(model_ids)))
        if not roots:
            logger.debug("Model version source is not under a referenced run or logged model; denying")
            return False
        if not all(any(is_under_location(source, root) for root in roots) for source in refs.storage_uris):
            logger.debug("Model version source is not under a referenced run or logged model; denying")
            return False
    return True
