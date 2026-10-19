"""Batch permission resolution for the FastAPI routers.

Thin wrappers over :mod:`mlflow_oidc_auth.utils.grant_context` (issue #460), the one resolver the
single-resource checks and the MLflow list filters use too. A batch loads the user's grants once
per resource type — a fixed number of statements however many resources it resolves — and decides
each resource in memory, with the same source order, ``NO_PERMISSIONS`` handling and workspace
fallback as every other path. That includes the experiment-in-request-workspace check, from the
experiment entity's own ``workspace`` where the caller passes entities.
"""

from typing import Any, Callable, Dict, List, Optional

from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import PermissionResult
from mlflow_oidc_auth.utils.grant_context import (
    EXPERIMENT,
    GATEWAY_ENDPOINT,
    GATEWAY_MODEL_DEFINITION,
    GATEWAY_SECRET,
    PROMPT,
    REGISTERED_MODEL,
    GrantContext,
    load_grant_context,
    resolve,
)

logger = get_logger()


def _batch_workspace() -> Optional[str]:
    """The workspace the batch's workspace fallback applies in.

    MLflow's request workspace (the ContextVar ``WorkspaceContextMiddleware`` sets), as the batch
    path has always used in FastAPI route context; None with workspaces disabled.
    """
    from mlflow_oidc_auth.config import config

    if not config.MLFLOW_ENABLE_WORKSPACES:
        return None
    from mlflow.utils.workspace_context import get_request_workspace as mlflow_get_request_workspace

    return mlflow_get_request_workspace()


def build_user_permission_context(username: str) -> GrantContext:
    """A bulk grant context for ``username`` for one batch.

    Grants are read lazily, once per resource type, so on databases whose ``=`` compares names
    exactly a batch costs a fixed number of statements regardless of the number of resources.
    Elsewhere direct grants are looked up per resource in SQL (see ``grant_context``).

    Parameters:
        username: The username to build context for.

    Returns:
        The grant context.
    """
    return load_grant_context(username, _batch_workspace(), bulk=True)


def resolve_experiment_permission_from_context(
    ctx: GrantContext,
    experiment_id: str,
    experiment_name: Optional[str] = None,
    experiment_workspace: Optional[str] = None,
) -> PermissionResult:
    """Resolve experiment permission against a grant context.

    Parameters:
        ctx: The user's grant context.
        experiment_id: The experiment ID to resolve permission for.
        experiment_name: The experiment name for pattern matching; looked up when omitted.
        experiment_workspace: The experiment's workspace, from its entity. Omitted, the workspace
            fallback asks MLflow whether the experiment is in the request's workspace.

    Returns:
        PermissionResult with the resolved permission.
    """
    return resolve(ctx, EXPERIMENT, experiment_id, name=experiment_name, resource_workspace=experiment_workspace)


def resolve_model_permission_from_context(ctx: GrantContext, model_name: str) -> PermissionResult:
    """Resolve registered model permission against a grant context.

    Parameters:
        ctx: The user's grant context.
        model_name: The model name to resolve permission for.

    Returns:
        PermissionResult with the resolved permission.
    """
    return resolve(ctx, REGISTERED_MODEL, model_name)


def resolve_prompt_permission_from_context(ctx: GrantContext, prompt_name: str) -> PermissionResult:
    """Resolve prompt permission against a grant context.

    Prompts use the registered-model direct grants but their own patterns.

    Parameters:
        ctx: The user's grant context.
        prompt_name: The prompt name to resolve permission for.

    Returns:
        PermissionResult with the resolved permission.
    """
    return resolve(ctx, PROMPT, prompt_name)


def batch_resolve_experiment_permissions(username: str, experiments: List) -> Dict[str, PermissionResult]:
    """Resolve permissions for multiple experiments in batch.

    Each experiment's own ``name`` and ``workspace`` are used, so no experiment is looked up
    again and none outside the request's workspace can inherit the workspace permission.

    Parameters:
        username: The user to resolve permissions for.
        experiments: Experiment objects with ``.experiment_id``, ``.name`` and, from MLflow,
            ``.workspace``.

    Returns:
        Dict mapping experiment_id to PermissionResult.
    """
    ctx = build_user_permission_context(username)
    return {
        exp.experiment_id: resolve_experiment_permission_from_context(ctx, exp.experiment_id, exp.name, getattr(exp, "workspace", None) or None)
        for exp in experiments
    }


def batch_resolve_model_permissions(username: str, models: List) -> Dict[str, PermissionResult]:
    """Resolve permissions for multiple registered models in batch.

    A registry listing returns prompts too (they are registered models). Each row is judged by its
    own kind, read from its tags, so a prompt is never resolved with model patterns (#479).

    Parameters:
        username: The user to resolve permissions for.
        models: List of model objects with .name (and, from the registry, .tags) attributes.

    Returns:
        Dict mapping model_name to PermissionResult.
    """
    from mlflow_oidc_auth.utils.prompt_kind import is_prompt_row

    ctx = build_user_permission_context(username)
    return {
        model.name: (resolve_prompt_permission_from_context if is_prompt_row(model) else resolve_model_permission_from_context)(ctx, model.name)
        for model in models
    }


def batch_resolve_prompt_permissions(username: str, prompts: List) -> Dict[str, PermissionResult]:
    """Resolve permissions for multiple prompts in batch.

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

    Parameters:
        username: The user to check permissions for.
        prompts: List of prompt objects with .name attribute.

    Returns:
        List of prompts the user can manage.
    """
    permissions = batch_resolve_prompt_permissions(username, prompts)
    return [prompt for prompt in prompts if permissions[prompt.name].permission.can_manage]


def _filter_manageable_by_name(username: str, resource_type: str, items: List, name_of: Callable[[Any], str]) -> List:
    """The items of a gateway listing ``username`` can manage, resolved against one bulk context.

    The workspace fallback applies in the workspace the request names, as the single-resource
    gateway checks (``can_manage_gateway_*``) decide it: a header-less request gets the global
    default. The experiment, model and prompt filters use MLflow's request workspace instead
    (:func:`_batch_workspace`); aligning the two is #480. An item without a name, or one whose
    resolution fails, is not manageable.
    """
    ctx = load_grant_context(username, bulk=True)
    manageable = []
    for item in items:
        name = name_of(item)
        if not name:
            continue
        try:
            if resolve(ctx, resource_type, name).permission.can_manage:
                manageable.append(item)
        except Exception:
            # Treat errors (missing resource etc.) as not manageable. The name is not logged: for
            # a gateway secret it is the secret's name.
            logger.debug("Error checking a gateway permission; treating the resource as not manageable")
    return manageable


def filter_manageable_gateway_endpoints(username: str, endpoints: List) -> List:
    """Filter gateway endpoints to only those the user can manage.

    Parameters:
        username: The user to check permissions for.
        endpoints: List of gateway endpoint dictionaries with 'name' key.

    Returns:
        List of endpoint dictionaries the user can manage.
    """
    return _filter_manageable_by_name(username, GATEWAY_ENDPOINT, endpoints, lambda endpoint: endpoint.get("name", ""))


def filter_manageable_gateway_secrets(username: str, secrets: List) -> List:
    """Filter gateway secrets to only those the user can manage.

    Parameters:
        username: The user to check permissions for.
        secrets: List of gateway secret dictionaries with 'secret_name', 'name', or 'key' key.

    Returns:
        List of secret dictionaries the user can manage.
    """
    # MLflow GatewaySecretInfo uses 'secret_name'; fall back to 'name'/'key' for compatibility
    return _filter_manageable_by_name(
        username, GATEWAY_SECRET, secrets, lambda secret: secret.get("secret_name") or secret.get("name") or secret.get("key", "")
    )


def filter_manageable_gateway_model_definitions(username: str, models: List) -> List:
    """Filter gateway model definitions to only those the user can manage.

    Parameters:
        username: The user to check permissions for.
        models: List of gateway model definition dictionaries with 'name' key.

    Returns:
        List of model definition dictionaries the user can manage.
    """
    return _filter_manageable_by_name(username, GATEWAY_MODEL_DEFINITION, models, lambda model: model.get("name", ""))
