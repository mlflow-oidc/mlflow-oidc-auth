"""
Permission resolution utilities for MLflow OIDC Auth.

This module provides registry-driven permission resolution for all 7 resource types.
The PERMISSION_REGISTRY maps resource types to builder functions that create
source configurations, and resolve_permission() is the single entry point.

Existing public functions (effective_*, can_*) are thin wrappers around
resolve_permission() and remain backward-compatible.
"""

import re
from typing import Callable, Dict

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import PermissionResult
from mlflow_oidc_auth.permissions import NO_PERMISSIONS, get_permission
from mlflow_oidc_auth.store import store

logger = get_logger()

# Resource type constants
EXPERIMENT = "experiment"
REGISTERED_MODEL = "registered_model"
PROMPT = "prompt"
SCORER = "scorer"
GATEWAY_ENDPOINT = "gateway_endpoint"
GATEWAY_SECRET = "gateway_secret"
GATEWAY_MODEL_DEFINITION = "gateway_model_definition"


# ---------------------------------------------------------------------------
# Generic regex matcher (replaces 10+ near-identical functions)
# ---------------------------------------------------------------------------


def _match_regex_permission(regexes, name: str, label: str) -> str:
    """Generic regex matcher for any resource type. Replaces 8 near-identical functions."""
    for regex in regexes:
        if re.match(regex.regex, name):
            logger.debug(f"Regex permission found for {label} {name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}")
            return regex.permission
    raise MlflowException(f"{label} {name}", error_code=RESOURCE_DOES_NOT_EXIST)


# ---------------------------------------------------------------------------
# Experiment-specific regex wrappers (experiment_id → experiment_name lookup)
# ---------------------------------------------------------------------------


def _get_experiment_permission_from_regex(regexes, experiment_id: str) -> str:
    experiment_name = _get_tracking_store().get_experiment(experiment_id).name
    return _match_regex_permission(regexes, experiment_name, "experiment")


def _get_experiment_group_permission_from_regex(regexes, experiment_id: str) -> str:
    experiment_name = _get_tracking_store().get_experiment(experiment_id).name
    return _match_regex_permission(regexes, experiment_name, "experiment")


# ---------------------------------------------------------------------------
# Builder functions — one per resource type
# ---------------------------------------------------------------------------


def _build_experiment_sources(experiment_id: str, username: str, **kwargs) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda experiment_id=experiment_id, user=username: store.get_experiment_permission(experiment_id, user).permission,
        "group": lambda experiment_id=experiment_id, user=username: store.get_user_groups_experiment_permission(experiment_id, user).permission,
        "regex": lambda experiment_id=experiment_id, user=username: _get_experiment_permission_from_regex(
            store.list_experiment_regex_permissions(user), experiment_id
        ),
        "group-regex": lambda experiment_id=experiment_id, user=username: _get_experiment_group_permission_from_regex(
            store.list_group_experiment_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            experiment_id,
        ),
    }


def _build_registered_model_sources(model_name: str, username: str, **kwargs) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda model_name=model_name, user=username: store.get_registered_model_permission(model_name, user).permission,
        "group": lambda model_name=model_name, user=username: store.get_user_groups_registered_model_permission(model_name, user).permission,
        "regex": lambda model_name=model_name, user=username: _match_regex_permission(
            store.list_registered_model_regex_permissions(user),
            model_name,
            "model name",
        ),
        "group-regex": lambda model_name=model_name, user=username: _match_regex_permission(
            store.list_group_registered_model_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            model_name,
            "model name",
        ),
    }


def _build_prompt_sources(model_name: str, username: str, **kwargs) -> Dict[str, Callable[[], str]]:
    """Build prompt permission sources.

    CRITICAL: user/group sources map to store.get_registered_model_permission and
    store.get_user_groups_registered_model_permission (NOT prompt-specific methods).
    Regex sources use prompt-specific store methods. This is intentional — preserved
    from the original implementation.
    """
    return {
        "user": lambda model_name=model_name, user=username: store.get_registered_model_permission(model_name, user).permission,
        "group": lambda model_name=model_name, user=username: store.get_user_groups_registered_model_permission(model_name, user).permission,
        "regex": lambda model_name=model_name, user=username: _match_regex_permission(store.list_prompt_regex_permissions(user), model_name, "model name"),
        "group-regex": lambda model_name=model_name, user=username: _match_regex_permission(
            store.list_group_prompt_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            model_name,
            "model name",
        ),
    }


def _build_scorer_sources(experiment_id: str, username: str, **kwargs) -> Dict[str, Callable[[], str]]:
    scorer_name = kwargs["scorer_name"]
    return {
        "user": lambda experiment_id=experiment_id, scorer_name=scorer_name, user=username: store.get_scorer_permission(
            experiment_id, scorer_name, user
        ).permission,
        "group": lambda experiment_id=experiment_id, scorer_name=scorer_name, user=username: store.get_user_groups_scorer_permission(
            experiment_id, scorer_name, user
        ).permission,
        "regex": lambda scorer_name=scorer_name, user=username: _match_regex_permission(store.list_scorer_regex_permissions(user), scorer_name, "scorer name"),
        "group-regex": lambda scorer_name=scorer_name, user=username: _match_regex_permission(
            store.list_group_scorer_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            scorer_name,
            "scorer name",
        ),
    }


def _build_gateway_endpoint_sources(gateway_name: str, username: str, **kwargs) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda gateway_name=gateway_name, user=username: store.get_gateway_endpoint_permission(gateway_name, user).permission,
        "group": lambda gateway_name=gateway_name, user=username: store.get_user_groups_gateway_endpoint_permission(gateway_name, user).permission,
        "regex": lambda gateway_name=gateway_name, user=username: _match_regex_permission(
            store.list_gateway_endpoint_regex_permissions(user),
            gateway_name,
            "gateway name",
        ),
        "group-regex": lambda gateway_name=gateway_name, user=username: _match_regex_permission(
            store.list_group_gateway_endpoint_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            gateway_name,
            "gateway name",
        ),
    }


def _build_gateway_secret_sources(gateway_name: str, username: str, **kwargs) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda gateway_name=gateway_name, user=username: store.get_gateway_secret_permission(gateway_name, user).permission,
        "group": lambda gateway_name=gateway_name, user=username: store.get_user_groups_gateway_secret_permission(gateway_name, user).permission,
        "regex": lambda gateway_name=gateway_name, user=username: _match_regex_permission(
            store.list_gateway_secret_regex_permissions(user),
            gateway_name,
            "gateway name",
        ),
        "group-regex": lambda gateway_name=gateway_name, user=username: _match_regex_permission(
            store.list_group_gateway_secret_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            gateway_name,
            "gateway name",
        ),
    }


def _build_gateway_model_definition_sources(gateway_name: str, username: str, **kwargs) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda gateway_name=gateway_name, user=username: store.get_gateway_model_definition_permission(gateway_name, user).permission,
        "group": lambda gateway_name=gateway_name, user=username: store.get_user_groups_gateway_model_definition_permission(gateway_name, user).permission,
        "regex": lambda gateway_name=gateway_name, user=username: _match_regex_permission(
            store.list_gateway_model_definition_regex_permissions(user),
            gateway_name,
            "gateway name",
        ),
        "group-regex": lambda gateway_name=gateway_name, user=username: _match_regex_permission(
            store.list_group_gateway_model_definition_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)),
            gateway_name,
            "gateway name",
        ),
    }


# ---------------------------------------------------------------------------
# Permission Registry and resolve_permission()
# ---------------------------------------------------------------------------


PERMISSION_REGISTRY: Dict[str, Callable[..., Dict[str, Callable[[], str]]]] = {
    EXPERIMENT: _build_experiment_sources,
    REGISTERED_MODEL: _build_registered_model_sources,
    PROMPT: _build_prompt_sources,
    SCORER: _build_scorer_sources,
    GATEWAY_ENDPOINT: _build_gateway_endpoint_sources,
    GATEWAY_SECRET: _build_gateway_secret_sources,
    GATEWAY_MODEL_DEFINITION: _build_gateway_model_definition_sources,
}


def resolve_permission(resource_type: str, resource_id: str, username: str, **kwargs) -> PermissionResult:
    """Single entry point for all permission resolution. Per D-01 (REFAC-01)."""
    builder = PERMISSION_REGISTRY[resource_type]
    sources_config = builder(resource_id, username, **kwargs)
    result = get_permission_from_store_or_default(sources_config)

    # Workspace fallback: when no resource-level permission found (per WSAUTH-C/WSAUTH-04)
    if result.kind == "fallback" and config.MLFLOW_ENABLE_WORKSPACES:
        from mlflow_oidc_auth.bridge.user import get_request_workspace
        from mlflow_oidc_auth.utils.workspace_cache import (
            get_workspace_permission_cached,
        )

        workspace = get_request_workspace()
        if workspace:
            ws_perm = get_workspace_permission_cached(username, workspace)
            if ws_perm is not None:
                return PermissionResult(ws_perm, "workspace")
            return PermissionResult(NO_PERMISSIONS, "workspace-deny")

    return result


# ---------------------------------------------------------------------------
# Public API — thin wrappers (unchanged signatures)
# ---------------------------------------------------------------------------


def effective_experiment_permission(experiment_id: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return resolve_permission(EXPERIMENT, experiment_id, user)


def effective_registered_model_permission(model_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return resolve_permission(REGISTERED_MODEL, model_name, user)


def effective_prompt_permission(prompt_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return resolve_permission(PROMPT, prompt_name, user)


def effective_scorer_permission(experiment_id: str, scorer_name: str, user: str) -> PermissionResult:
    """Resolve effective permission for a scorer.

    This mirrors the behavior of `effective_experiment_permission` / `effective_registered_model_permission`
    but uses scorer-specific permission sources.
    """
    return resolve_permission(SCORER, experiment_id, user, scorer_name=scorer_name)


def effective_gateway_endpoint_permission(gateway_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return resolve_permission(GATEWAY_ENDPOINT, gateway_name, user)


def effective_gateway_secret_permission(gateway_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return resolve_permission(GATEWAY_SECRET, gateway_name, user)


def effective_gateway_model_definition_permission(gateway_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return resolve_permission(GATEWAY_MODEL_DEFINITION, gateway_name, user)


# ---------------------------------------------------------------------------
# can_* helpers (unchanged signatures)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Core resolution loop (UNCHANGED)
# ---------------------------------------------------------------------------


# TODO: check if str can be replaced by Permission in function signature
def get_permission_from_store_or_default(
    PERMISSION_SOURCES_CONFIG: Dict[str, Callable[[], str]],
) -> PermissionResult:
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
