"""Batch permission resolution utilities for efficient bulk permission lookups.

This module provides optimized functions for resolving permissions across multiple
resources (experiments, models, prompts) in a single operation, minimizing database
queries compared to per-item permission lookups.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities import (
    ExperimentGroupRegexPermission,
    ExperimentPermission,
    ExperimentRegexPermission,
    RegisteredModelGroupRegexPermission,
    RegisteredModelPermission,
    RegisteredModelRegexPermission,
)
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import PermissionResult
from mlflow_oidc_auth.permissions import get_permission
from mlflow_oidc_auth.store import store

logger = get_logger()


@dataclass
class UserPermissionContext:
    """Pre-fetched permission data for a user to enable batch permission resolution.

    Attributes:
        username: The username for which permissions were fetched.
        group_ids: List of group IDs the user belongs to.
        user_experiment_permissions: Dict mapping experiment_id to permission string.
        group_experiment_permissions: Dict mapping experiment_id to permission string.
        experiment_regex_permissions: Ordered list of user's experiment regex permissions.
        group_experiment_regex_permissions: Ordered list of group experiment regex permissions.
        user_model_permissions: Dict mapping model_name to permission string.
        group_model_permissions: Dict mapping model_name to permission string.
        model_regex_permissions: Ordered list of user's model regex permissions.
        group_model_regex_permissions: Ordered list of group model regex permissions.
        prompt_regex_permissions: Ordered list of user's prompt regex permissions.
        group_prompt_regex_permissions: Ordered list of group prompt regex permissions.
    """

    username: str
    group_ids: List[int]
    # Experiment permissions
    user_experiment_permissions: Dict[str, str]
    group_experiment_permissions: Dict[str, str]
    experiment_regex_permissions: List[ExperimentRegexPermission]
    group_experiment_regex_permissions: List[ExperimentGroupRegexPermission]
    # Model permissions (also used for prompts)
    user_model_permissions: Dict[str, str]
    group_model_permissions: Dict[str, str]
    model_regex_permissions: List[RegisteredModelRegexPermission]
    group_model_regex_permissions: List[RegisteredModelGroupRegexPermission]
    # Prompt-specific regex permissions
    prompt_regex_permissions: List[RegisteredModelRegexPermission]
    group_prompt_regex_permissions: List[RegisteredModelGroupRegexPermission]


def build_user_permission_context(username: str) -> UserPermissionContext:
    """Build a permission context for a user by fetching all permissions in batch.

    This function makes a fixed number of database queries regardless of the number
    of resources being checked, enabling efficient batch permission resolution.

    Parameters:
        username: The username to build context for.

    Returns:
        UserPermissionContext with all permission data pre-fetched.
    """
    # Get user's group IDs (single query)
    group_ids = store.get_groups_ids_for_user(username)

    # Fetch all experiment permissions for user (single query)
    user_exp_perms = store.list_experiment_permissions(username)
    user_experiment_permissions = {p.experiment_id: p.permission for p in user_exp_perms}

    # Fetch all experiment permissions from user's groups (single query)
    group_exp_perms = store.list_user_groups_experiment_permissions(username)
    group_experiment_permissions = {p.experiment_id: p.permission for p in group_exp_perms}

    # Fetch experiment regex permissions (single query each)
    experiment_regex_permissions = store.list_experiment_regex_permissions(username)
    group_experiment_regex_permissions = store.list_group_experiment_regex_permissions_for_groups_ids(group_ids) if group_ids else []

    # Fetch all registered model permissions for user (single query)
    user_model_perms = store.list_registered_model_permissions(username)
    user_model_permissions = {p.name: p.permission for p in user_model_perms}

    # Fetch all model permissions from user's groups (single query)
    group_model_perms = store.list_user_groups_registered_model_permissions(username)
    group_model_permissions = {p.name: p.permission for p in group_model_perms}

    # Fetch model regex permissions (single query each)
    model_regex_permissions = store.list_registered_model_regex_permissions(username)
    group_model_regex_permissions = store.list_group_registered_model_regex_permissions_for_groups_ids(group_ids) if group_ids else []

    # Fetch prompt regex permissions (prompts use model permissions but have separate regex)
    prompt_regex_permissions = store.list_prompt_regex_permissions(username)
    group_prompt_regex_permissions = store.list_group_prompt_regex_permissions_for_groups_ids(group_ids) if group_ids else []

    return UserPermissionContext(
        username=username,
        group_ids=group_ids,
        user_experiment_permissions=user_experiment_permissions,
        group_experiment_permissions=group_experiment_permissions,
        experiment_regex_permissions=experiment_regex_permissions,
        group_experiment_regex_permissions=group_experiment_regex_permissions,
        user_model_permissions=user_model_permissions,
        group_model_permissions=group_model_permissions,
        model_regex_permissions=model_regex_permissions,
        group_model_regex_permissions=group_model_regex_permissions,
        prompt_regex_permissions=prompt_regex_permissions,
        group_prompt_regex_permissions=group_prompt_regex_permissions,
    )


def _resolve_permission_from_context(
    source_order: List[str],
    user_direct: Optional[str],
    group_direct: Optional[str],
    user_regex_match: Optional[str],
    group_regex_match: Optional[str],
) -> PermissionResult:
    """Resolve effective permission from pre-fetched data following source priority.

    Parameters:
        source_order: Ordered list of permission sources to check.
        user_direct: Direct user permission (or None if not found).
        group_direct: Direct group permission (or None if not found).
        user_regex_match: User regex-matched permission (or None if not found).
        group_regex_match: Group regex-matched permission (or None if not found).

    Returns:
        PermissionResult with the resolved permission and its source.
    """
    source_map = {
        "user": user_direct,
        "group": group_direct,
        "regex": user_regex_match,
        "group-regex": group_regex_match,
    }

    for source in source_order:
        perm = source_map.get(source)
        if perm is not None:
            logger.debug(f"Batch permission found using source: {source}")
            return PermissionResult(get_permission(perm), source)

    # Fallback to default
    logger.debug("Batch permission using default")
    return PermissionResult(get_permission(config.DEFAULT_MLFLOW_PERMISSION), "fallback")


def _find_regex_permission(regexes: List, name: str) -> Optional[str]:
    """Find the first matching regex permission for a given name.

    Parameters:
        regexes: List of regex permission objects with .regex and .permission attributes.
        name: The name to match against regexes.

    Returns:
        The permission string if a match is found, None otherwise.
    """
    for regex_perm in regexes:
        if re.match(regex_perm.regex, name):
            return regex_perm.permission
    return None


def resolve_experiment_permission_from_context(
    ctx: UserPermissionContext,
    experiment_id: str,
    experiment_name: Optional[str] = None,
) -> PermissionResult:
    """Resolve experiment permission using pre-fetched context (no DB queries).

    Parameters:
        ctx: Pre-built user permission context.
        experiment_id: The experiment ID to resolve permission for.
        experiment_name: Optional experiment name for regex matching. If not provided,
            it will be fetched from the tracking store (single query).

    Returns:
        PermissionResult with the resolved permission.
    """
    # Get experiment name for regex matching (may require a query if not provided)
    if experiment_name is None:
        experiment_name = _get_tracking_store().get_experiment(experiment_id).name

    # Look up permissions from context (no DB queries)
    user_direct = ctx.user_experiment_permissions.get(experiment_id)
    group_direct = ctx.group_experiment_permissions.get(experiment_id)
    user_regex = _find_regex_permission(ctx.experiment_regex_permissions, experiment_name)
    group_regex = _find_regex_permission(ctx.group_experiment_regex_permissions, experiment_name)

    return _resolve_permission_from_context(
        config.PERMISSION_SOURCE_ORDER,
        user_direct,
        group_direct,
        user_regex,
        group_regex,
    )


def resolve_model_permission_from_context(ctx: UserPermissionContext, model_name: str) -> PermissionResult:
    """Resolve registered model permission using pre-fetched context (no DB queries).

    Parameters:
        ctx: Pre-built user permission context.
        model_name: The model name to resolve permission for.

    Returns:
        PermissionResult with the resolved permission.
    """
    user_direct = ctx.user_model_permissions.get(model_name)
    group_direct = ctx.group_model_permissions.get(model_name)
    user_regex = _find_regex_permission(ctx.model_regex_permissions, model_name)
    group_regex = _find_regex_permission(ctx.group_model_regex_permissions, model_name)

    return _resolve_permission_from_context(
        config.PERMISSION_SOURCE_ORDER,
        user_direct,
        group_direct,
        user_regex,
        group_regex,
    )


def resolve_prompt_permission_from_context(ctx: UserPermissionContext, prompt_name: str) -> PermissionResult:
    """Resolve prompt permission using pre-fetched context (no DB queries).

    Prompts use the same direct permissions as models but have separate regex patterns.

    Parameters:
        ctx: Pre-built user permission context.
        prompt_name: The prompt name to resolve permission for.

    Returns:
        PermissionResult with the resolved permission.
    """
    # Prompts share direct permissions with models
    user_direct = ctx.user_model_permissions.get(prompt_name)
    group_direct = ctx.group_model_permissions.get(prompt_name)
    # But use prompt-specific regex patterns
    user_regex = _find_regex_permission(ctx.prompt_regex_permissions, prompt_name)
    group_regex = _find_regex_permission(ctx.group_prompt_regex_permissions, prompt_name)

    return _resolve_permission_from_context(
        config.PERMISSION_SOURCE_ORDER,
        user_direct,
        group_direct,
        user_regex,
        group_regex,
    )


def batch_resolve_experiment_permissions(
    username: str,
    experiments: List,
) -> Dict[str, PermissionResult]:
    """Resolve permissions for multiple experiments in batch.

    This function makes a fixed number of DB queries (~10) regardless of the number
    of experiments, compared to N*4 queries for N experiments with per-item lookups.

    Parameters:
        username: The user to resolve permissions for.
        experiments: List of experiment objects with .experiment_id and .name attributes.

    Returns:
        Dict mapping experiment_id to PermissionResult.
    """
    ctx = build_user_permission_context(username)
    return {exp.experiment_id: resolve_experiment_permission_from_context(ctx, exp.experiment_id, exp.name) for exp in experiments}


def batch_resolve_model_permissions(
    username: str,
    models: List,
) -> Dict[str, PermissionResult]:
    """Resolve permissions for multiple registered models in batch.

    This function makes a fixed number of DB queries (~10) regardless of the number
    of models, compared to N*4 queries for N models with per-item lookups.

    Parameters:
        username: The user to resolve permissions for.
        models: List of model objects with .name attribute.

    Returns:
        Dict mapping model_name to PermissionResult.
    """
    ctx = build_user_permission_context(username)
    return {model.name: resolve_model_permission_from_context(ctx, model.name) for model in models}


def batch_resolve_prompt_permissions(
    username: str,
    prompts: List,
) -> Dict[str, PermissionResult]:
    """Resolve permissions for multiple prompts in batch.

    This function makes a fixed number of DB queries (~10) regardless of the number
    of prompts, compared to N*4 queries for N prompts with per-item lookups.

    Parameters:
        username: The user to resolve permissions for.
        prompts: List of prompt objects with .name attribute.

    Returns:
        Dict mapping prompt_name to PermissionResult.
    """
    ctx = build_user_permission_context(username)
    return {prompt.name: resolve_prompt_permission_from_context(ctx, prompt.name) for prompt in prompts}


def filter_manageable_experiments(username: str, experiments: List) -> List:
    """Filter experiments to only those the user can manage.

    This function uses batch permission resolution for efficiency.

    Parameters:
        username: The user to check permissions for.
        experiments: List of experiment objects with .experiment_id and .name attributes.

    Returns:
        List of experiments the user can manage.
    """
    permissions = batch_resolve_experiment_permissions(username, experiments)
    return [exp for exp in experiments if permissions[exp.experiment_id].permission.can_manage]


def filter_manageable_models(username: str, models: List) -> List:
    """Filter models to only those the user can manage.

    This function uses batch permission resolution for efficiency.

    Parameters:
        username: The user to check permissions for.
        models: List of model objects with .name attribute.

    Returns:
        List of models the user can manage.
    """
    permissions = batch_resolve_model_permissions(username, models)
    return [model for model in models if permissions[model.name].permission.can_manage]


def filter_manageable_prompts(username: str, prompts: List) -> List:
    """Filter prompts to only those the user can manage.

    This function uses batch permission resolution for efficiency.

    Parameters:
        username: The user to check permissions for.
        prompts: List of prompt objects with .name attribute.

    Returns:
        List of prompts the user can manage.
    """
    permissions = batch_resolve_prompt_permissions(username, prompts)
    return [prompt for prompt in prompts if permissions[prompt.name].permission.can_manage]


def filter_manageable_gateway_endpoints(username: str, endpoints: List) -> List:
    """Filter gateway endpoints to only those the user can manage.

    This function checks permissions for each endpoint using the existing
    gateway permission resolution logic.

    Parameters:
        username: The user to check permissions for.
        endpoints: List of gateway endpoint dictionaries with 'name' key.

    Returns:
        List of endpoint dictionaries the user can manage.
    """
    from mlflow_oidc_auth.utils.permissions import can_manage_gateway_endpoint

    manageable = []
    for endpoint in endpoints:
        endpoint_name = endpoint.get("name", "")
        if not endpoint_name:
            continue
        try:
            if can_manage_gateway_endpoint(endpoint_name, username):
                manageable.append(endpoint)
        except Exception as e:
            # Treat errors (missing resource etc.) as not manageable
            logger.debug(f"Error checking gateway endpoint permission for {endpoint_name}: {e}")
            continue

    return manageable


def filter_manageable_gateway_secrets(username: str, secrets: List) -> List:
    """Filter gateway secrets to only those the user can manage.

    Parameters:
        username: The user to check permissions for.
        secrets: List of gateway secret dictionaries with 'name' or 'key' key.

    Returns:
        List of secret dictionaries the user can manage.
    """
    from mlflow_oidc_auth.utils.permissions import can_manage_gateway_secret

    manageable = []
    for secret in secrets:
        # Secrets might use 'key' or 'name' depending on the MLflow version
        secret_name = secret.get("name") or secret.get("key", "")
        if not secret_name:
            continue
        try:
            if can_manage_gateway_secret(secret_name, username):
                manageable.append(secret)
        except Exception as e:
            logger.debug(f"Error checking gateway secret permission for {secret_name}: {e}")
            continue

    return manageable


def filter_manageable_gateway_model_definitions(username: str, models: List) -> List:
    """Filter gateway model definitions to only those the user can manage.

    Parameters:
        username: The user to check permissions for.
        models: List of gateway model definition dictionaries with 'name' key.

    Returns:
        List of model definition dictionaries the user can manage.
    """
    from mlflow_oidc_auth.utils.permissions import can_manage_gateway_model_definition

    manageable = []
    for model in models:
        model_name = model.get("name", "")
        if not model_name:
            continue
        try:
            if can_manage_gateway_model_definition(model_name, username):
                manageable.append(model)
        except Exception as e:
            logger.debug(f"Error checking gateway model definition permission for {model_name}: {e}")
            continue

    return manageable
