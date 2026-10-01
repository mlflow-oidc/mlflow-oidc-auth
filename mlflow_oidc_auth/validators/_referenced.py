"""Helpers for resources a request references rather than targets.

Some requests act on one resource but draw on another: a model version is created from a
run or a logged model, a metric is logged against a logged model, a gateway model
definition uses a secret. The caller must hold a grant on the referenced resource too,
matching MLflow's own auth plugin.

Everything here fails closed. A referenced run or logged model that does not exist yields
``NO_PERMISSIONS`` (a 403, the same answer as a resource the caller cannot see, so the
response does not reveal which ids exist).
"""

from __future__ import annotations

from typing import Any

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import NO_PERMISSIONS, Permission
from mlflow_oidc_auth.utils import effective_experiment_permission, get_run_experiment_id, request_body_dict
from mlflow_oidc_auth.validators.experiment import get_artifact_experiment

logger = get_logger()


def _is_not_found(error: MlflowException) -> bool:
    return error.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST)


def referenced_run(run_id: str):
    """The referenced run, or ``None`` when it does not exist.

    Parameters:
        run_id: The run the request references.

    Returns:
        The run entity, or ``None``.

    Raises:
        MlflowException: For any tracking-store error other than "does not exist".
    """
    try:
        return _get_tracking_store().get_run(str(run_id))
    except MlflowException as e:
        if _is_not_found(e):
            logger.debug("Referenced run could not be resolved; denying")
            return None
        raise


def referenced_logged_model(model_id: str):
    """The referenced logged model, or ``None`` when it does not exist.

    Parameters:
        model_id: The logged model the request references.

    Returns:
        The logged model entity, or ``None``.

    Raises:
        MlflowException: For any tracking-store error other than "does not exist".
    """
    try:
        return _get_tracking_store().get_logged_model(str(model_id))
    except MlflowException as e:
        if _is_not_found(e):
            logger.debug("Referenced logged model could not be resolved; denying")
            return None
        raise


def referenced_run_permission(run_id: str, username: str) -> Permission:
    """The permission ``username`` holds on the experiment of a referenced run.

    Reads only the run's experiment id, not the whole run (``get_run_experiment_id``).

    Parameters:
        run_id: The run the request references.
        username: The authenticated user.

    Returns:
        The experiment permission, or ``NO_PERMISSIONS`` when the run does not exist.

    Raises:
        MlflowException: For any tracking-store error other than "does not exist".
    """
    try:
        experiment_id = get_run_experiment_id(_get_tracking_store(), str(run_id))
    except MlflowException as e:
        if _is_not_found(e):
            logger.debug("Referenced run could not be resolved; denying")
            return NO_PERMISSIONS
        raise
    return effective_experiment_permission(experiment_id, username).permission


def referenced_logged_model_permission(model_id: str, username: str) -> Permission:
    """The permission ``username`` holds on the experiment of a referenced logged model.

    Parameters:
        model_id: The logged model the request references.
        username: The authenticated user.

    Returns:
        The experiment permission, or ``NO_PERMISSIONS`` when the model does not exist.
    """
    model = referenced_logged_model(model_id)
    if model is None:
        return NO_PERMISSIONS
    return effective_experiment_permission(model.experiment_id, username).permission


def referenced_experiment_permission(experiment_id: str, username: str) -> Permission:
    """The permission ``username`` holds on a referenced experiment that must exist.

    Unlike a plain permission lookup, an id with no experiment behind it (or a
    non-canonical id such as ``"012"``) yields ``NO_PERMISSIONS`` rather than
    ``DEFAULT_MLFLOW_PERMISSION``.

    Parameters:
        experiment_id: The experiment the request references.
        username: The authenticated user.

    Returns:
        The experiment permission, or ``NO_PERMISSIONS``.
    """
    if experiment_id is None or get_artifact_experiment(str(experiment_id)) is None:
        return NO_PERMISSIONS
    return effective_experiment_permission(str(experiment_id), username).permission


def _spellings(field: str) -> tuple[str, ...]:
    from mlflow_oidc_auth.hooks.dual_spelling_guard import _snake_to_camel

    return tuple(dict.fromkeys((field, _snake_to_camel(field))))


def _as_items(value: Any) -> list:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def nested_body_values(container_field: str, item_field: str) -> list:
    """Every distinct non-empty ``item_field`` inside the body's ``container_field``.

    ``container_field`` may hold one message (a dict) or a repeated message (a list of
    dicts). Both the snake_case and the lowerCamelCase spelling of each field are read, as
    MLflow's proto parser accepts either, so a value cannot be hidden under one spelling.

    Parameters:
        container_field: The snake_case name of the (repeated) message field.
        item_field: The snake_case name of the scalar field inside each message.

    Returns:
        Distinct values, in body order.
    """
    body = request_body_dict()
    values: dict[str, Any] = {}
    for container_key in _spellings(container_field):
        for item in _as_items(body.get(container_key)):
            for item_key in _spellings(item_field):
                value = item.get(item_key)
                if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).strip():
                    values.setdefault(str(value), value)
    return list(values.values())


def body_has_field(field: str) -> bool:
    """True when the request body sets ``field`` under either spelling, even to ``""``.

    A JSON ``null`` counts as absent, as it does for MLflow's proto parser.

    Parameters:
        field: The snake_case field name.

    Returns:
        Whether the body sets the field.
    """
    body = request_body_dict()
    return any(body.get(key) is not None for key in _spellings(field))
