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
from mlflow_oidc_auth.utils import effective_experiment_permission, request_body_dict

logger = get_logger()


def _is_not_found(error: MlflowException) -> bool:
    return error.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST)


def referenced_run_permission(run_id: str, username: str) -> Permission:
    """The permission ``username`` holds on the experiment of a referenced run.

    Parameters:
        run_id: The run the request references.
        username: The authenticated user.

    Returns:
        The experiment permission, or ``NO_PERMISSIONS`` when the run does not exist.

    Raises:
        MlflowException: For any tracking-store error other than "does not exist".
    """
    try:
        run = _get_tracking_store().get_run(str(run_id))
    except MlflowException as e:
        if _is_not_found(e):
            logger.debug("Referenced run could not be resolved; denying")
            return NO_PERMISSIONS
        raise
    return effective_experiment_permission(run.info.experiment_id, username).permission


def referenced_logged_model_permission(model_id: str, username: str) -> Permission:
    """The permission ``username`` holds on the experiment of a referenced logged model.

    Parameters:
        model_id: The logged model the request references.
        username: The authenticated user.

    Returns:
        The experiment permission, or ``NO_PERMISSIONS`` when the model does not exist.

    Raises:
        MlflowException: For any tracking-store error other than "does not exist".
    """
    try:
        model = _get_tracking_store().get_logged_model(str(model_id))
    except MlflowException as e:
        if _is_not_found(e):
            logger.debug("Referenced logged model could not be resolved; denying")
            return NO_PERMISSIONS
        raise
    return effective_experiment_permission(model.experiment_id, username).permission


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
