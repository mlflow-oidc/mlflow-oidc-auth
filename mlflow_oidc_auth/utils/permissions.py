import re
from typing import Callable, Dict, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities import (
    ExperimentGroupRegexPermission,
    ExperimentRegexPermission,
    RegisteredModelGroupRegexPermission,
    RegisteredModelRegexPermission,
)
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import get_permission
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils.types import PermissionResult

logger = get_logger()


def _permission_prompt_sources_config(model_name: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda model_name=model_name, user=username: store.get_registered_model_permission(model_name, user).permission,
        "group": lambda model_name=model_name, user=username: store.get_user_groups_registered_model_permission(model_name, user).permission,
        "regex": lambda model_name=model_name, user=username: _get_registered_model_permission_from_regex(
            store.list_prompt_regex_permissions(user), model_name
        ),
        "group-regex": lambda model_name=model_name, user=username: _get_registered_model_group_permission_from_regex(
            store.list_group_prompt_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)), model_name
        ),
    }


def _permission_experiment_sources_config(experiment_id: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda experiment_id=experiment_id, user=username: store.get_experiment_permission(experiment_id, user).permission,
        "group": lambda experiment_id=experiment_id, user=username: store.get_user_groups_experiment_permission(experiment_id, user).permission,
        "regex": lambda experiment_id=experiment_id, user=username: _get_experiment_permission_from_regex(
            store.list_experiment_regex_permissions(user), experiment_id
        ),
        "group-regex": lambda experiment_id=experiment_id, user=username: _get_experiment_group_permission_from_regex(
            store.list_group_experiment_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)), experiment_id
        ),
    }


def _permission_registered_model_sources_config(model_name: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda model_name=model_name, user=username: store.get_registered_model_permission(model_name, user).permission,
        "group": lambda model_name=model_name, user=username: store.get_user_groups_registered_model_permission(model_name, user).permission,
        "regex": lambda model_name=model_name, user=username: _get_registered_model_permission_from_regex(
            store.list_registered_model_regex_permissions(user), model_name
        ),
        "group-regex": lambda model_name=model_name, user=username: _get_registered_model_group_permission_from_regex(
            store.list_group_registered_model_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)), model_name
        ),
    }


def _get_registered_model_permission_from_regex(regexes: List[RegisteredModelRegexPermission], model_name: str) -> str:
    for regex in regexes:
        if re.match(regex.regex, model_name):
            logger.debug(f"Regex permission found for model name {model_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}")
            return regex.permission
    raise MlflowException(
        f"model name {model_name}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def _get_experiment_permission_from_regex(regexes: List[ExperimentRegexPermission], experiment_id: str) -> str:
    experiment_name = _get_tracking_store().get_experiment(experiment_id).name
    for regex in regexes:
        if re.match(regex.regex, experiment_name):
            logger.debug(
                f"Regex permission found for experiment id {experiment_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}"
            )
            return regex.permission
    raise MlflowException(
        f"experiment id {experiment_id}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def _get_registered_model_group_permission_from_regex(regexes: List[RegisteredModelGroupRegexPermission], model_name: str) -> str:
    for regex in regexes:
        if re.match(regex.regex, model_name):
            logger.debug(f"Regex group permission found for model name {model_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}")
            return regex.permission
    raise MlflowException(
        f"model name {model_name}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def _get_experiment_group_permission_from_regex(regexes: List[ExperimentGroupRegexPermission], experiment_id: str) -> str:
    experiment_name = _get_tracking_store().get_experiment(experiment_id).name
    for regex in regexes:
        if re.match(regex.regex, experiment_name):
            logger.debug(
                f"Regex group permission found for experiment id {experiment_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}"
            )
            return regex.permission
    raise MlflowException(
        f"experiment id {experiment_id}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def effective_experiment_permission(experiment_id: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return get_permission_from_store_or_default(_permission_experiment_sources_config(experiment_id, user))


def effective_registered_model_permission(model_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return get_permission_from_store_or_default(_permission_registered_model_sources_config(model_name, user))


def effective_prompt_permission(prompt_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return get_permission_from_store_or_default(_permission_prompt_sources_config(prompt_name, user))


def can_read_experiment(experiment_id: str, user: str) -> bool:
    permission = effective_experiment_permission(experiment_id, user).permission
    return permission.can_read


def can_read_registered_model(model_name: str, user: str) -> bool:
    permission = effective_registered_model_permission(model_name, user).permission
    return permission.can_read


def can_manage_experiment(experiment_id: str, user: str) -> bool:
    permission = effective_experiment_permission(experiment_id, user).permission
    return permission.can_manage


def can_manage_registered_model(model_name: str, user: str) -> bool:
    permission = effective_registered_model_permission(model_name, user).permission
    return permission.can_manage


# TODO: check fi str can be replaced by Permission in function signature
def get_permission_from_store_or_default(PERMISSION_SOURCES_CONFIG: Dict[str, Callable[[], str]]) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources.

    This function iterates through permission sources in the order defined by
    PERMISSION_SOURCE_ORDER configuration, stopping at the first successful match.
    If no explicit permission is found, returns the default permission.

    Args:
        PERMISSION_SOURCES_CONFIG: Dictionary mapping source names to functions
                                 that retrieve permissions from those sources

    Returns:
        PermissionResult: Contains the permission and source type information

    Edge Cases:
        - Empty PERMISSION_SOURCES_CONFIG: Returns default permission with 'fallback' type
        - Invalid source in config: Logs warning and continues to next source
        - All sources fail: Returns default permission with 'fallback' type
        - MLflowException with non-RESOURCE_DOES_NOT_EXIST error: Re-raises the exception

    Note:
        The function follows the configured permission source priority order
        defined in config.PERMISSION_SOURCE_ORDER and stops at the first successful match.
    """
    for source_name in config.PERMISSION_SOURCE_ORDER:
        if source_name in PERMISSION_SOURCES_CONFIG:
            try:
                # Get the permission retrieval function from the configuration
                permission_func = PERMISSION_SOURCES_CONFIG[source_name]
                # Call the function to get the permission
                perm = permission_func()
                logger.debug(f"Permission found using source: {source_name}")
                return PermissionResult(get_permission(perm), source_name)
            except MlflowException as e:
                if e.error_code != ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
                    raise  # Re-raise exceptions other than RESOURCE_DOES_NOT_EXIST
                logger.debug(f"Permission not found using source {source_name}: {e}")
        else:
            logger.warning(f"Invalid permission source configured: {source_name}")

    # If no permission is found, use the default
    perm = config.DEFAULT_MLFLOW_PERMISSION
    logger.debug("Default permission used")
    return PermissionResult(get_permission(perm), "fallback")
