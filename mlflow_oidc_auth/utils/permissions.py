import re
from typing import Callable, Dict, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities import (
    ExperimentGroupRegexPermission,
    ExperimentRegexPermission,
    GatewayEndpointGroupRegexPermission,
    GatewayEndpointRegexPermission,
    GatewayModelDefinitionGroupRegexPermission,
    GatewayModelDefinitionRegexPermission,
    GatewaySecretGroupRegexPermission,
    GatewaySecretRegexPermission,
    RegisteredModelGroupRegexPermission,
    RegisteredModelRegexPermission,
    ScorerGroupRegexPermission,
    ScorerRegexPermission,
)
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import PermissionResult
from mlflow_oidc_auth.permissions import get_permission
from mlflow_oidc_auth.store import store

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


def _permission_scorer_sources_config(experiment_id: str, scorer_name: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda experiment_id=experiment_id, scorer_name=scorer_name, user=username: store.get_scorer_permission(
            experiment_id, scorer_name, user
        ).permission,
        "group": lambda experiment_id=experiment_id, scorer_name=scorer_name, user=username: store.get_user_groups_scorer_permission(
            experiment_id, scorer_name, user
        ).permission,
        "regex": lambda scorer_name=scorer_name, user=username: _get_scorer_permission_from_regex(store.list_scorer_regex_permissions(user), scorer_name),
        "group-regex": lambda scorer_name=scorer_name, user=username: _get_scorer_group_permission_from_regex(
            store.list_group_scorer_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)), scorer_name
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


def _get_scorer_permission_from_regex(regexes: List[ScorerRegexPermission], scorer_name: str) -> str:
    for regex in regexes:
        if re.match(regex.regex, scorer_name):
            logger.debug(f"Regex permission found for scorer {scorer_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}")
            return regex.permission
    raise MlflowException(
        f"scorer name {scorer_name}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def _get_scorer_group_permission_from_regex(regexes: List[ScorerGroupRegexPermission], scorer_name: str) -> str:
    for regex in regexes:
        if re.match(regex.regex, scorer_name):
            logger.debug(f"Regex group permission found for scorer {scorer_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}")
            return regex.permission
    raise MlflowException(
        f"scorer name {scorer_name}",
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


def effective_scorer_permission(experiment_id: str, scorer_name: str, user: str) -> PermissionResult:
    """Resolve effective permission for a scorer.

    This mirrors the behavior of `effective_experiment_permission` / `effective_registered_model_permission`
    but uses scorer-specific permission sources.
    """

    return get_permission_from_store_or_default(_permission_scorer_sources_config(experiment_id, scorer_name, user))


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


def can_manage_scorer(experiment_id: str, scorer_name: str, user: str) -> bool:
    """Check if a user can manage a scorer.

    Scorers are scoped to an experiment. This uses the effective scorer permission
    resolution (user/group/regex/fallback) and checks the MANAGE bit.
    """

    permission = effective_scorer_permission(experiment_id, scorer_name, user).permission
    return permission.can_manage


def _permission_gateway_endpoint_sources_config(gateway_name: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda gateway_name=gateway_name, user=username: store.get_gateway_endpoint_permission(gateway_name, user).permission,
        "group": lambda gateway_name=gateway_name, user=username: store.get_user_groups_gateway_endpoint_permission(gateway_name, user).permission,
        "regex": lambda gateway_name=gateway_name, user=username: _get_gateway_endpoint_permission_from_regex(
            store.list_gateway_endpoint_regex_permissions(user), gateway_name
        ),
        "group-regex": lambda gateway_name=gateway_name, user=username: _get_gateway_endpoint_group_permission_from_regex(
            store.list_group_gateway_endpoint_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)), gateway_name
        ),
    }


def _get_gateway_endpoint_permission_from_regex(regexes: List[GatewayEndpointRegexPermission], gateway_name: str) -> str:
    for regex in regexes:
        if re.match(regex.regex, gateway_name):
            logger.debug(f"Regex permission found for gateway {gateway_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}")
            return regex.permission
    raise MlflowException(
        f"gateway name {gateway_name}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def _get_gateway_endpoint_group_permission_from_regex(regexes: List[GatewayEndpointGroupRegexPermission], gateway_name: str) -> str:
    for regex in regexes:
        if re.match(regex.regex, gateway_name):
            logger.debug(f"Regex group permission found for gateway {gateway_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}")
            return regex.permission
    raise MlflowException(
        f"gateway name {gateway_name}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def effective_gateway_endpoint_permission(gateway_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return get_permission_from_store_or_default(_permission_gateway_endpoint_sources_config(gateway_name, user))


def can_read_gateway_endpoint(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_endpoint_permission(gateway_name, user).permission
    return permission.can_read


def can_use_gateway_endpoint(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_endpoint_permission(gateway_name, user).permission
    return permission.can_use


def can_update_gateway_endpoint(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_endpoint_permission(gateway_name, user).permission
    return permission.can_update


def can_manage_gateway_endpoint(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_endpoint_permission(gateway_name, user).permission
    return permission.can_manage


def _get_gateway_secret_permission_from_regex(regexes: List[GatewaySecretRegexPermission], gateway_name: str) -> str:
    for regex in regexes:
        if re.match(regex.regex, gateway_name):
            logger.debug(f"Regex permission found for gateway secret {gateway_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}")
            return regex.permission
    raise MlflowException(
        f"gateway name {gateway_name}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def _get_gateway_secret_group_permission_from_regex(regexes: List[GatewaySecretGroupRegexPermission], gateway_name: str) -> str:
    for regex in regexes:
        if re.match(regex.regex, gateway_name):
            logger.debug(
                f"Regex group permission found for gateway secret {gateway_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}"
            )
            return regex.permission
    raise MlflowException(
        f"gateway name {gateway_name}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def _permission_gateway_secret_sources_config(gateway_name: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda gateway_name=gateway_name, user=username: store.get_gateway_secret_permission(gateway_name, user).permission,
        "group": lambda gateway_name=gateway_name, user=username: store.get_user_groups_gateway_secret_permission(gateway_name, user).permission,
        "regex": lambda gateway_name=gateway_name, user=username: _get_gateway_secret_permission_from_regex(
            store.list_gateway_secret_regex_permissions(user), gateway_name
        ),
        "group-regex": lambda gateway_name=gateway_name, user=username: _get_gateway_secret_group_permission_from_regex(
            store.list_group_gateway_secret_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)), gateway_name
        ),
    }


def effective_gateway_secret_permission(gateway_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return get_permission_from_store_or_default(_permission_gateway_secret_sources_config(gateway_name, user))


def can_read_gateway_secret(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_secret_permission(gateway_name, user).permission
    return permission.can_read


def can_use_gateway_secret(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_secret_permission(gateway_name, user).permission
    return permission.can_use


def can_update_gateway_secret(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_secret_permission(gateway_name, user).permission
    return permission.can_update


def can_manage_gateway_secret(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_secret_permission(gateway_name, user).permission
    return permission.can_manage


def _get_gateway_model_definition_permission_from_regex(regexes: List[GatewayModelDefinitionRegexPermission], gateway_name: str) -> str:
    for regex in regexes:
        if re.match(regex.regex, gateway_name):
            logger.debug(
                f"Regex permission found for gateway model definition {gateway_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}"
            )
            return regex.permission
    raise MlflowException(
        f"gateway name {gateway_name}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def _get_gateway_model_definition_group_permission_from_regex(regexes: List[GatewayModelDefinitionGroupRegexPermission], gateway_name: str) -> str:
    for regex in regexes:
        if re.match(regex.regex, gateway_name):
            logger.debug(
                f"Regex group permission found for gateway model definition {gateway_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}"
            )
            return regex.permission
    raise MlflowException(
        f"gateway name {gateway_name}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def _permission_gateway_model_definition_sources_config(gateway_name: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda gateway_name=gateway_name, user=username: store.get_gateway_model_definition_permission(gateway_name, user).permission,
        "group": lambda gateway_name=gateway_name, user=username: store.get_user_groups_gateway_model_definition_permission(gateway_name, user).permission,
        "regex": lambda gateway_name=gateway_name, user=username: _get_gateway_model_definition_permission_from_regex(
            store.list_gateway_model_definition_regex_permissions(user), gateway_name
        ),
        "group-regex": lambda gateway_name=gateway_name, user=username: _get_gateway_model_definition_group_permission_from_regex(
            store.list_group_gateway_model_definition_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)), gateway_name
        ),
    }


def effective_gateway_model_definition_permission(gateway_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return get_permission_from_store_or_default(_permission_gateway_model_definition_sources_config(gateway_name, user))


def can_read_gateway_model_definition(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_model_definition_permission(gateway_name, user).permission
    return permission.can_read


def can_use_gateway_model_definition(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_model_definition_permission(gateway_name, user).permission
    return permission.can_use


def can_update_gateway_model_definition(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_model_definition_permission(gateway_name, user).permission
    return permission.can_update


def can_manage_gateway_model_definition(gateway_name: str, user: str) -> bool:
    permission = effective_gateway_model_definition_permission(gateway_name, user).permission
    return permission.can_manage


# TODO: check if str can be replaced by Permission in function signature
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
