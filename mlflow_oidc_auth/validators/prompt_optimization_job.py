"""Validators for prompt optimization job operations.

Prompt optimization jobs inherit permissions from their parent experiment.
The job_id is resolved to an experiment_id via the job's stored params.

Creating a job also acts on the resources the request names: the job registers the optimized
template as a new version of the source prompt, so UPDATE is required on that prompt, and it
reads the training dataset, so READ is required on every experiment the dataset is linked to.
"""

import json
import re
from typing import Any

from mlflow.server.jobs import get_job
from mlflow.store.artifact.utils.models import _parse_model_uri

from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import Permission
from mlflow_oidc_auth.utils import (
    all_source_values,
    effective_experiment_permission,
    effective_prompt_permission,
    get_url_param,
    request_body_dict,
)
from mlflow_oidc_auth.validators._experiment_scope import permission_on_all_experiments
from mlflow_oidc_auth.validators.dataset import dataset_experiment_ids
from mlflow_oidc_auth.validators.experiment import validate_can_update_experiment

logger = get_logger()

# prompts:/<name>/<version> or prompts:/<name>@<alias>
_PROMPT_URI = re.compile(r"^prompts:/(?P<name>[^/@]+)(?:/[^/@]+|@[^/@]+)$")


def can_update_prompt_uri(prompt_uri: Any, username: str) -> bool:
    """UPDATE on the prompt a ``prompts:/`` URI names.

    Parameters:
        prompt_uri: ``prompts:/<name>/<version>`` or ``prompts:/<name>@<alias>``.
        username: The caller.

    Returns:
        True only for a well-formed URI naming a prompt the caller can update; False for
        anything else, including a lookup error.
    """
    if not isinstance(prompt_uri, str):
        return False
    match = _PROMPT_URI.match(prompt_uri.strip())
    if match is None:
        return False
    # Authorize the name MLflow will load, not the raw text: MLflow parses prompt URIs with
    # urlparse, which drops some characters (tab, CR, LF). Refuse any URI where the two differ.
    try:
        parsed_name = _parse_model_uri(prompt_uri.strip(), scheme="prompts").name
    except Exception:
        return False
    if parsed_name != match.group("name"):
        return False
    try:
        return bool(effective_prompt_permission(parsed_name, username).permission.can_update)
    except Exception:
        logger.debug("Prompt permission lookup failed")
        return False


def can_read_dataset_experiments(dataset_id: Any, username: str) -> bool:
    """READ on every experiment an evaluation dataset is linked to.

    Parameters:
        dataset_id: The evaluation dataset id.
        username: The caller.

    Returns:
        False for a dataset that does not exist, is linked to no experiment, or cannot be
        looked up.
    """
    if isinstance(dataset_id, bool) or not isinstance(dataset_id, (str, int)) or not str(dataset_id).strip():
        return False
    try:
        experiment_ids = dataset_experiment_ids(str(dataset_id).strip())
        return bool(experiment_ids) and permission_on_all_experiments(experiment_ids, username).can_read
    except Exception:
        logger.debug("Dataset lookup failed")
        return False


def _get_permission_from_prompt_optimization_job_id(username: str) -> Permission:
    """Resolve a prompt optimization job's permission from its parent experiment.

    Extracts the job_id from the Flask request, fetches the job entity,
    parses the experiment_id from the job's params JSON, then returns
    the effective experiment permission for the given user.

    Parameters:
        username: The authenticated username.

    Returns:
        The effective Permission for the job's parent experiment.
    """
    # job_id is a URL path parameter (/prompt-optimization/jobs/<job_id>), which is
    # the identifier MLflow itself dispatches on. Reading it from the query/body
    # instead would let a request authorize one job (in the body) while MLflow acts
    # on the job named in the path (issue #270 cross-source bypass).
    job_id = get_url_param("job_id")
    job_entity = get_job(job_id)
    params = json.loads(job_entity.params)
    experiment_id = params.get("experiment_id")
    return effective_experiment_permission(experiment_id, username).permission


def validate_can_read_prompt_optimization_job(username: str) -> bool:
    """Validate the user can read a prompt optimization job."""
    return _get_permission_from_prompt_optimization_job_id(username).can_read


def validate_can_update_prompt_optimization_job(username: str) -> bool:
    """Validate the user can update (cancel) a prompt optimization job."""
    return _get_permission_from_prompt_optimization_job_id(username).can_update


def validate_can_delete_prompt_optimization_job(username: str) -> bool:
    """Validate the user can delete a prompt optimization job."""
    return _get_permission_from_prompt_optimization_job_id(username).can_delete


def _config_dataset_ids() -> list | None:
    """Every dataset id in the body's ``config`` (both proto JSON spellings), or None if the
    ``config`` present is not an object."""
    config = request_body_dict().get("config")
    if config is None:
        return []
    if not isinstance(config, dict):
        return None
    return [config[key] for key in ("dataset_id", "datasetId") if config.get(key) not in (None, "")]


def validate_can_create_prompt_optimization_job(username: str) -> bool:
    """UPDATE on the experiment, UPDATE on the source prompt, READ on the dataset's experiments.

    MLflow reads ``source_prompt_uri`` and ``config.dataset_id`` from the JSON body. Every
    source prompt URI the request carries, in any source, is authorized; a request naming
    none, or one that is not a ``prompts:/`` URI, is refused. A dataset that cannot be
    resolved is refused.
    """
    if not validate_can_update_experiment(username):
        return False
    prompt_uris = all_source_values("source_prompt_uri")
    if not prompt_uris or not all(can_update_prompt_uri(uri, username) for uri in prompt_uris):
        return False
    dataset_ids = _config_dataset_ids()
    if dataset_ids is None:
        return False
    return all(can_read_dataset_experiments(dataset_id, username) for dataset_id in dataset_ids)
