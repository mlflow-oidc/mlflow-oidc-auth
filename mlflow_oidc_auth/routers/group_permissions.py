"""
Group permissions router for FastAPI application.

This router handles permission management endpoints for groups, including
experiment, model, and prompt permissions at the group level.
"""

from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.dependencies import check_admin_permission, check_experiment_manage_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import (
    ExperimentPermission,
    ExperimentRegexCreate,
    GatewayPermission,
    GatewayPermissionRecord,
    GatewayPermissionResponse,
    GatewayRegexCreate,
    GatewayRegexPermissionRecord,
    GatewayRegexPermissionResponse,
    GroupExperimentPermissionItem,
    GroupListResponse,
    GroupUser,
    GroupNamedPermissionItem,
    GroupPromptRegexPermissionItem,
    PromptPermission,
    PromptRegexCreate,
    RegisteredModelPermission,
    RegisteredModelRegexCreate,
    GroupRegisteredModelRegexPermissionItem,
    ScorerPermission,
    ScorerRegexCreate,
    GroupScorerPermissionItem,
    GroupScorerRegexPermissionItem,
    GroupExperimentRegexPermissionItem,
    StatusMessageResponse,
)
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import (
    effective_experiment_permission,
    effective_prompt_permission,
    effective_registered_model_permission,
    get_is_admin,
    get_username,
)

from ._prefix import GROUP_PERMISSIONS_ROUTER_PREFIX

logger = get_logger()

group_permissions_router = APIRouter(
    prefix=GROUP_PERMISSIONS_ROUTER_PREFIX,
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)

LIST_GROUPS = ""

GROUP_EXPERIMENT_PERMISSIONS = "/{group_name}/experiments"
GROUP_EXPERIMENT_PERMISSION_DETAIL = "/{group_name}/experiments/{experiment_id}"
GROUP_EXPERIMENT_PATTERN_PERMISSIONS = "/{group_name}/experiment-patterns"
GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL = "/{group_name}/experiment-patterns/{id}"

# GROUP, REGISTERED_MODEL, PATTERN
GROUP_REGISTERED_MODEL_PERMISSIONS = "/{group_name}/registered-models"
GROUP_REGISTERED_MODEL_PERMISSION_DETAIL = "/{group_name}/registered-models/{name}"
GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS = "/{group_name}/registered-models-patterns"
GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL = "/{group_name}/registered-models-patterns/{id}"

# GROUP, PROMPT, PATTERN
GROUP_PROMPT_PERMISSIONS = "/{group_name}/prompts"
GROUP_PROMPT_PERMISSION_DETAIL = "/{group_name}/prompts/{prompt_name}"
GROUP_PROMPT_PATTERN_PERMISSIONS = "/{group_name}/prompts-patterns"
GROUP_PROMPT_PATTERN_PERMISSION_DETAIL = "/{group_name}/prompts-patterns/{id}"

# GROUP, SCORER, PATTERN
GROUP_SCORER_PERMISSIONS = "/{group_name}/scorers"
GROUP_SCORER_PERMISSION_DETAIL = "/{group_name}/scorers/{experiment_id}/{scorer_name}"
GROUP_SCORER_PATTERN_PERMISSIONS = "/{group_name}/scorer-patterns"
GROUP_SCORER_PATTERN_PERMISSION_DETAIL = "/{group_name}/scorer-patterns/{id}"
GROUP_USER_PERMISSIONS = "/{group_name}/users"

# GROUP, GATEWAY ENDPOINT, PATTERN
GROUP_GATEWAY_ENDPOINT_PERMISSIONS = "/{group_name}/gateways/endpoints"
GROUP_GATEWAY_ENDPOINT_PERMISSION_DETAIL = "/{group_name}/gateways/endpoints/{name}"
GROUP_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS = "/{group_name}/gateways/endpoints-patterns"
GROUP_GATEWAY_ENDPOINT_PATTERN_PERMISSION_DETAIL = "/{group_name}/gateways/endpoints-patterns/{id}"

# GROUP, GATEWAY MODEL DEFINITION, PATTERN
GROUP_GATEWAY_MODEL_DEFINITION_PERMISSIONS = "/{group_name}/gateways/model-definitions"
GROUP_GATEWAY_MODEL_DEFINITION_PERMISSION_DETAIL = "/{group_name}/gateways/model-definitions/{name}"
GROUP_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSIONS = "/{group_name}/gateways/model-definitions-patterns"
GROUP_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSION_DETAIL = "/{group_name}/gateways/model-definitions-patterns/{id}"

# GROUP, GATEWAY SECRET, PATTERN
GROUP_GATEWAY_SECRET_PERMISSIONS = "/{group_name}/gateways/secrets"
GROUP_GATEWAY_SECRET_PERMISSION_DETAIL = "/{group_name}/gateways/secrets/{name}"
GROUP_GATEWAY_SECRET_PATTERN_PERMISSIONS = "/{group_name}/gateways/secrets-patterns"
GROUP_GATEWAY_SECRET_PATTERN_PERMISSION_DETAIL = "/{group_name}/gateways/secrets-patterns/{id}"


@group_permissions_router.get(
    LIST_GROUPS,
    summary="List groups",
    description="Retrieves a list of all groups in the system.",
    response_model=GroupListResponse,
    tags=["groups"],
)
async def list_groups(username: str = Depends(get_username)) -> GroupListResponse:
    """
    List all groups in the system.

    This endpoint returns all groups in the system. Any authenticated user can access this endpoint.

    Parameters:
    -----------
    username : str
        The authenticated username (injected by dependency).

    Returns:
    --------
    GroupListResponse
        The list of groups available in the system.

    Raises:
    -------
    HTTPException
        If there is an error retrieving the groups.
    """
    try:
        from mlflow_oidc_auth.store import store

        groups = store.get_groups()
        return GroupListResponse(root=groups)

    except Exception as e:
        logger.error(f"Error listing groups: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve groups")


@group_permissions_router.get(
    GROUP_USER_PERMISSIONS,
    response_model=List[GroupUser],
    summary="List users in a group",
    description="Retrieves a list of users who are members of the specified group.",
    tags=["group users"],
)
async def get_group_users(
    group_name: str = Path(..., description="The group name to get users for"), admin_username: str = Depends(check_admin_permission)
) -> List[GroupUser]:
    """
    List all users who are members of a specific group.

    This endpoint returns all users who belong to the specified group,
    including their admin status within the group.

    Parameters:
    -----------
    group_name : str
        The name of the group to get users for.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    List[GroupUser]
        A list of users in the group with their details.

    Raises:
    -------
    HTTPException
        If there's an error retrieving the group users.
    """
    try:
        users = store.get_group_users(group_name)
        return [GroupUser(username=user.username, is_admin=user.is_admin) for user in users]
    except Exception as e:
        logger.error(f"Error getting group users: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Group not found or error retrieving users")


@group_permissions_router.get(
    GROUP_EXPERIMENT_PERMISSIONS,
    summary="List experiment permissions for a group",
    description="Retrieves a list of experiments with permission information for the specified group.",
    response_model=List[GroupExperimentPermissionItem],
    tags=["group experiment permissions"],
)
async def get_group_experiments(
    group_name: str = Path(..., description="The group name to get experiment permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[GroupExperimentPermissionItem]:
    """
    List experiment permissions for a group.

    This endpoint returns experiments that have permissions assigned to the specified group.
    Admins can see all group experiments, regular users can only see group experiments
    for experiments they can manage.

    Parameters:
    -----------
    group_name : str
        The group name to get experiment permissions for.
    current_username : str
        The username of the currently authenticated user (from dependency).
    is_admin : bool
        Whether the current user is an admin (from dependency).

    Returns:
    --------
    List[GroupExperimentPermissionItem]
        The experiments that grant permissions to the group.
    """
    try:
        # Get experiments that have permissions assigned to this group
        group_experiments = store.get_group_experiments(group_name)
        tracking_store = _get_tracking_store()

        items: List[GroupExperimentPermissionItem] = []
        for experiment in group_experiments:
            can_manage = is_admin or effective_experiment_permission(experiment.experiment_id, current_username).permission.can_manage
            if not can_manage:
                continue

            mlflow_experiment = tracking_store.get_experiment(experiment.experiment_id)
            items.append(
                GroupExperimentPermissionItem(
                    id=str(experiment.experiment_id),
                    name=mlflow_experiment.name,
                    permission=experiment.permission,
                )
            )

        return items

    except Exception as e:
        logger.error(f"Error retrieving group experiment permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve group experiment permissions")


@group_permissions_router.post(
    GROUP_EXPERIMENT_PERMISSION_DETAIL,
    status_code=201,
    summary="Create experiment permission for a group",
    description="Creates a new permission for a group to access a specific experiment.",
    response_model=StatusMessageResponse,
    tags=["group experiment permissions"],
)
async def create_group_experiment_permission(
    group_name: str = Path(..., description="The group name to grant experiment permission to"),
    experiment_id: str = Path(..., description="The experiment ID to set permissions for"),
    permission_data: ExperimentPermission = Body(..., description="The permission details"),
    current_username: str = Depends(check_experiment_manage_permission),
) -> StatusMessageResponse:
    """
    Create a permission for a group to access an experiment.

    Parameters:
    -----------
    group_name : str
        The group name to grant permissions to.
    experiment_id : str
        The ID of the experiment to grant permissions for.
    permission_data : ExperimentPermission
        The permission data containing the permission level.
    current_username : str
        The username of the authenticated user who can manage this experiment (from dependency).

    Returns:
    --------
    StatusMessageResponse
        Confirmation of the created permission.
    """
    try:
        store.create_group_experiment_permission(
            group_name,
            experiment_id,
            permission_data.permission,
        )
        return StatusMessageResponse(message=f"Experiment permission created for group {group_name} on experiment {experiment_id}")
    except Exception as e:
        logger.error(f"Error creating group experiment permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create group experiment permission")


@group_permissions_router.patch(
    GROUP_EXPERIMENT_PERMISSION_DETAIL,
    summary="Update experiment permission for a group",
    description="Updates the permission for a group on a specific experiment.",
    response_model=StatusMessageResponse,
    tags=["group experiment permissions"],
)
async def update_group_experiment_permission(
    group_name: str = Path(..., description="The group name to update experiment permission for"),
    experiment_id: str = Path(..., description="The experiment ID to update permissions for"),
    permission_data: ExperimentPermission = Body(..., description="Updated permission details"),
    current_username: str = Depends(check_experiment_manage_permission),
) -> StatusMessageResponse:
    """
    Update the permission for a group on an experiment.

    Parameters:
    -----------
    group_name : str
        The group name to update permissions for.
    experiment_id : str
        The ID of the experiment to update permissions for.
    permission_data : ExperimentPermission
        The updated permission data.
    current_username : str
        The username of the authenticated user who can manage this experiment (from dependency).

    Returns:
    --------
    StatusMessageResponse
        Confirmation of the updated permission.
    """
    try:
        store.update_group_experiment_permission(
            group_name,
            experiment_id,
            permission_data.permission,
        )
        return StatusMessageResponse(message=f"Experiment permission updated for group {group_name} on experiment {experiment_id}")
    except Exception as e:
        logger.error(f"Error updating group experiment permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update group experiment permission")


@group_permissions_router.delete(
    GROUP_EXPERIMENT_PERMISSION_DETAIL,
    summary="Delete experiment permission for a group",
    description="Deletes the permission for a group on a specific experiment.",
    response_model=StatusMessageResponse,
    tags=["group experiment permissions"],
)
async def delete_group_experiment_permission(
    group_name: str = Path(..., description="The group name to delete experiment permission for"),
    experiment_id: str = Path(..., description="The experiment ID to delete permissions for"),
    current_username: str = Depends(check_experiment_manage_permission),
) -> StatusMessageResponse:
    """
    Delete the permission for a group on an experiment.

    Parameters:
    -----------
    group_name : str
        The group name to delete permissions for.
    experiment_id : str
        The ID of the experiment to delete permissions for.
    current_username : str
        The username of the authenticated user who can manage this experiment (from dependency).

    Returns:
    --------
    StatusMessageResponse
        Confirmation of the deleted permission.
    """
    try:
        store.delete_group_experiment_permission(group_name, experiment_id)
        return StatusMessageResponse(message=f"Experiment permission deleted for group {group_name} on experiment {experiment_id}")
    except Exception as e:
        logger.error(f"Error deleting group experiment permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete group experiment permission")


@group_permissions_router.get(
    GROUP_REGISTERED_MODEL_PERMISSIONS,
    summary="List registered model permissions for a group",
    description="Retrieves a list of registered models with permission information for the specified group.",
    response_model=List[GroupNamedPermissionItem],
    tags=["group registered model permissions"],
)
async def get_group_registered_models(
    group_name: str = Path(..., description="The group name to get registered model permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[GroupNamedPermissionItem]:
    """
    List registered model permissions for a group.

    This endpoint returns registered models that have permissions assigned to the specified group.
    Admins can see all group models, regular users can only see group models
    for models they can manage.

    Parameters:
    -----------
    group_name : str
        The group name to get registered model permissions for.
    current_username : str
        The username of the currently authenticated user (from dependency).
    is_admin : bool
        Whether the current user is an admin (from dependency).

    Returns:
    --------
    List[GroupNamedPermissionItem]
        The registered models that expose permissions to the group.
    """
    try:
        # Get registered models that have permissions assigned to this group
        group_models = store.get_group_models(group_name)

        items: List[GroupNamedPermissionItem] = []
        for model in group_models:
            can_manage = is_admin or effective_registered_model_permission(model.name, current_username).permission.can_manage
            if not can_manage:
                continue

            items.append(GroupNamedPermissionItem(name=model.name, permission=model.permission))

        return items

    except Exception as e:
        logger.error(f"Error retrieving group registered model permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve group registered model permissions")


@group_permissions_router.post(
    GROUP_REGISTERED_MODEL_PERMISSION_DETAIL,
    status_code=201,
    summary="Create registered model permission for a group",
    description="Creates a new permission for a group to access a specific registered model.",
    response_model=StatusMessageResponse,
    tags=["group registered model permissions"],
)
async def create_group_registered_model_permission(
    group_name: str = Path(..., description="The group name to grant registered model permission to"),
    name: str = Path(..., description="The registered model name to set permissions for"),
    permission_data: RegisteredModelPermission = Body(..., description="The permission details"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> StatusMessageResponse:
    """
    Create a permission for a group to access a registered model.

    Parameters:
    -----------
    group_name : str
        The group name to grant permissions to.
    name : str
        The name of the registered model to grant permissions for.
    permission_data : RegisteredModelPermission
        The permission data containing the permission level.
    current_username : str
        The username of the authenticated user (from dependency).
    is_admin : bool
        Whether the current user is an admin (from dependency).

    Returns:
    --------
    StatusMessageResponse
        Confirmation of the created permission.
    """
    # Check if user can manage this registered model
    if not is_admin and not effective_registered_model_permission(name, current_username).permission.can_manage:
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage registered model {name}")
    try:
        store.create_group_model_permission(
            group_name=group_name,
            name=name,
            permission=permission_data.permission,
        )
        return StatusMessageResponse(message=f"Registered model permission created for group {group_name} on model {name}")
    except Exception as e:
        logger.error(f"Error creating group registered model permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create group registered model permission")


@group_permissions_router.patch(
    GROUP_REGISTERED_MODEL_PERMISSION_DETAIL,
    summary="Update registered model permission for a group",
    description="Updates the permission for a group on a specific registered model.",
    response_model=StatusMessageResponse,
    tags=["group registered model permissions"],
)
async def update_group_registered_model_permission(
    group_name: str = Path(..., description="The group name to update registered model permission for"),
    name: str = Path(..., description="The registered model name to update permissions for"),
    permission_data: RegisteredModelPermission = Body(..., description="Updated permission details"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> StatusMessageResponse:
    """
    Update the permission for a group on a registered model.

    Parameters:
    -----------
    group_name : str
        The group name to update permissions for.
    name : str
        The name of the registered model to update permissions for.
    permission_data : RegisteredModelPermission
        The updated permission data.
    current_username : str
        The username of the authenticated user (from dependency).
    is_admin : bool
        Whether the current user is an admin (from dependency).

    Returns:
    --------
    StatusMessageResponse
        Confirmation of the updated permission.
    """
    # Check if user can manage this registered model
    if not is_admin and not effective_registered_model_permission(name, current_username).permission.can_manage:
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage registered model {name}")
    try:
        store.update_group_model_permission(
            group_name=group_name,
            name=name,
            permission=permission_data.permission,
        )
        return StatusMessageResponse(message=f"Registered model permission updated for group {group_name} on model {name}")
    except Exception as e:
        logger.error(f"Error updating group registered model permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update group registered model permission")


@group_permissions_router.delete(
    GROUP_REGISTERED_MODEL_PERMISSION_DETAIL,
    summary="Delete registered model permission for a group",
    description="Deletes the permission for a group on a specific registered model.",
    response_model=StatusMessageResponse,
    tags=["group registered model permissions"],
)
async def delete_group_registered_model_permission(
    group_name: str = Path(..., description="The group name to delete registered model permission for"),
    name: str = Path(..., description="The registered model name to delete permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> StatusMessageResponse:
    """
    Delete the permission for a group on a registered model.

    Parameters:
    -----------
    group_name : str
        The group name to delete permissions for.
    name : str
        The name of the registered model to delete permissions for.
    current_username : str
        The username of the authenticated user (from dependency).
    is_admin : bool
        Whether the current user is an admin (from dependency).

    Returns:
    --------
    StatusMessageResponse
        Confirmation of the deleted permission.
    """
    # Check if user can manage this registered model
    if not is_admin and not effective_registered_model_permission(name, current_username).permission.can_manage:
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage registered model {name}")
    try:
        store.delete_group_model_permission(group_name, name)
        return StatusMessageResponse(message=f"Registered model permission deleted for group {group_name} on model {name}")
    except Exception as e:
        logger.error(f"Error deleting group registered model permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete group registered model permission")


@group_permissions_router.get(
    GROUP_PROMPT_PERMISSIONS,
    summary="Get group prompt permissions",
    description="Retrieves all prompt permissions for a specific group.",
    response_model=List[GroupNamedPermissionItem],
    tags=["group prompt permissions"],
)
async def get_group_prompts(
    group_name: str = Path(..., description="The group name to get prompt permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[GroupNamedPermissionItem]:
    """
    Get all prompt permissions for a group.

    This endpoint returns prompts that have permissions assigned to the specified group.
    Admins can see all group prompts, regular users can only see group prompts
    for prompts they can manage.

    Parameters:
    -----------
    group_name : str
        The group name to get prompt permissions for.
    current_username : str
        The username of the currently authenticated user (from dependency).
    is_admin : bool
        Whether the current user is an admin (from dependency).

    Returns:
    --------
    List[GroupNamedPermissionItem]
        The prompts that grant permissions to the group.
    """
    try:
        # Get prompts that have permissions assigned to this group
        group_prompts = store.get_group_prompts(group_name)

        # For admins: show all group prompts
        items: List[GroupNamedPermissionItem] = []
        for prompt in group_prompts:
            can_manage = is_admin or effective_prompt_permission(prompt.name, current_username).permission.can_manage
            if not can_manage:
                continue

            items.append(GroupNamedPermissionItem(name=prompt.name, permission=prompt.permission))

        return items
    except Exception as e:
        logger.error(f"Error getting group prompt permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get group prompt permissions")


@group_permissions_router.post(
    GROUP_PROMPT_PERMISSION_DETAIL,
    status_code=201,
    summary="Create prompt permission for a group",
    description="Creates a new permission for a group to access a specific prompt.",
    response_model=StatusMessageResponse,
    tags=["group prompt permissions"],
)
async def create_group_prompt_permission(
    group_name: str = Path(..., description="The group name to grant prompt permission to"),
    prompt_name: str = Path(..., description="The prompt name to set permissions for"),
    permission_data: PromptPermission = Body(..., description="The permission details"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> StatusMessageResponse:
    """
    Create a permission for a group to access a prompt.

    Parameters:
    -----------
    group_name : str
        The group name to grant permissions to.
    prompt_name : str
        The name of the prompt to grant permissions for.
    permission_data : PromptPermission
        The permission data containing the permission level.
    current_username : str
        The username of the authenticated user (from dependency).
    is_admin : bool
        Whether the current user is an admin (from dependency).

    Returns:
    --------
    StatusMessageResponse
        Confirmation of the created permission.
    """
    # Check if user can manage this prompt
    if not is_admin and not effective_prompt_permission(prompt_name, current_username).permission.can_manage:
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage prompt {prompt_name}")

    try:
        store.create_group_prompt_permission(
            group_name=group_name,
            name=prompt_name,
            permission=permission_data.permission,
        )
        return StatusMessageResponse(message=f"Prompt permission created for group {group_name} on prompt {prompt_name}")
    except Exception as e:
        logger.error(f"Error creating group prompt permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create group prompt permission")


@group_permissions_router.patch(
    GROUP_PROMPT_PERMISSION_DETAIL,
    summary="Update prompt permission for a group",
    description="Updates the permission for a group on a specific prompt.",
    response_model=StatusMessageResponse,
    tags=["group prompt permissions"],
)
async def update_group_prompt_permission(
    group_name: str = Path(..., description="The group name to update prompt permission for"),
    prompt_name: str = Path(..., description="The prompt name to update permissions for"),
    permission_data: PromptPermission = Body(..., description="Updated permission details"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> StatusMessageResponse:
    """
    Update the permission for a group on a prompt.

    Parameters:
    -----------
    group_name : str
        The group name to update permissions for.
    prompt_name : str
        The name of the prompt to update permissions for.
    permission_data : PromptPermission
        The updated permission data.
    current_username : str
        The username of the authenticated user (from dependency).
    is_admin : bool
        Whether the current user is an admin (from dependency).

    Returns:
    --------
    StatusMessageResponse
        Confirmation of the updated permission.
    """
    # Check if user can manage this prompt
    if not is_admin and not effective_prompt_permission(prompt_name, current_username).permission.can_manage:
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage prompt {prompt_name}")

    try:
        store.update_group_prompt_permission(
            group_name=group_name,
            name=prompt_name,
            permission=permission_data.permission,
        )
        return StatusMessageResponse(message=f"Prompt permission updated for group {group_name} on prompt {prompt_name}")
    except Exception as e:
        logger.error(f"Error updating group prompt permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update group prompt permission")


@group_permissions_router.delete(
    GROUP_PROMPT_PERMISSION_DETAIL,
    summary="Delete prompt permission for a group",
    description="Deletes the permission for a group on a specific prompt.",
    response_model=StatusMessageResponse,
    tags=["group prompt permissions"],
)
async def delete_group_prompt_permission(
    group_name: str = Path(..., description="The group name to delete prompt permission for"),
    prompt_name: str = Path(..., description="The prompt name to delete permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> StatusMessageResponse:
    """
    Delete the permission for a group on a prompt.

    Parameters:
    -----------
    group_name : str
        The group name to delete permissions for.
    prompt_name : str
        The name of the prompt to delete permissions for.
    current_username : str
        The username of the authenticated user (from dependency).
    is_admin : bool
        Whether the current user is an admin (from dependency).

    Returns:
    --------
    StatusMessageResponse
        Confirmation of the deleted permission.
    """
    # Check if user can manage this prompt
    if not is_admin and not effective_prompt_permission(prompt_name, current_username).permission.can_manage:
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage prompt {prompt_name}")

    try:
        store.delete_group_prompt_permission(group_name, prompt_name)
        return StatusMessageResponse(message=f"Prompt permission deleted for group {group_name} on prompt {prompt_name}")
    except Exception as e:
        logger.error(f"Error deleting group prompt permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete group prompt permission")


@group_permissions_router.get(
    GROUP_EXPERIMENT_PATTERN_PERMISSIONS,
    summary="Get group experiment pattern permissions",
    description="Retrieves all experiment regex pattern permissions for a specific group.",
    response_model=List[GroupExperimentRegexPermissionItem],
    tags=["group experiment pattern permissions"],
)
async def get_group_experiment_pattern_permissions(
    group_name: str = Path(..., description="The group name to get experiment pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[GroupExperimentRegexPermissionItem]:
    """
    Get all experiment regex pattern permissions for a group.
    """
    try:
        patterns = store.list_group_experiment_regex_permissions(group_name)
        items: List[GroupExperimentRegexPermissionItem] = []
        for pattern in patterns:
            payload = pattern.to_json() if hasattr(pattern, "to_json") else None
            if isinstance(payload, dict):
                items.append(
                    GroupExperimentRegexPermissionItem(
                        id=payload["id"],
                        regex=payload["regex"],
                        priority=payload["priority"],
                        group_id=payload.get("group_id"),
                        permission=payload["permission"],
                    )
                )
            else:
                items.append(
                    GroupExperimentRegexPermissionItem(
                        id=pattern.id,
                        regex=pattern.regex,
                        priority=pattern.priority,
                        group_id=getattr(pattern, "group_id", None),
                        permission=pattern.permission,
                    )
                )

        return items
    except Exception as e:
        logger.error(f"Error getting group experiment pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get group experiment pattern permissions")


@group_permissions_router.post(
    GROUP_EXPERIMENT_PATTERN_PERMISSIONS,
    status_code=201,
    summary="Create experiment pattern permission for a group",
    description="Creates a new regex pattern permission for a group to access experiments.",
    response_model=StatusMessageResponse,
    tags=["group experiment pattern permissions"],
)
async def create_group_experiment_pattern_permission(
    group_name: str = Path(..., description="The group name to create experiment pattern permission for"),
    pattern_data: ExperimentRegexCreate = Body(..., description="The pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """
    Create a regex pattern permission for a group to access experiments.
    """
    try:
        store.create_group_experiment_regex_permission(
            regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission, group_name=group_name
        )
        return StatusMessageResponse(message=f"Experiment pattern permission created for group {group_name}")
    except Exception as e:
        logger.error(f"Error creating group experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create group experiment pattern permission")


@group_permissions_router.get(
    GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    summary="Get specific experiment pattern permission for a group",
    description="Retrieves a specific experiment regex pattern permission for a group.",
    response_model=GroupExperimentRegexPermissionItem,
    tags=["group experiment pattern permissions"],
)
async def get_group_experiment_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> GroupExperimentRegexPermissionItem:
    """
    Get a specific experiment regex pattern permission for a group.
    """
    try:
        pattern = store.get_group_experiment_regex_permission(group_name, id)
        payload = pattern.to_json() if hasattr(pattern, "to_json") else None
        if isinstance(payload, dict):
            item = GroupExperimentRegexPermissionItem(
                id=payload["id"],
                regex=payload["regex"],
                priority=payload["priority"],
                group_id=payload.get("group_id"),
                permission=payload["permission"],
            )
        else:
            item = GroupExperimentRegexPermissionItem(
                id=pattern.id,
                regex=pattern.regex,
                priority=pattern.priority,
                group_id=getattr(pattern, "group_id", None),
                permission=pattern.permission,
            )

        return item
    except Exception as e:
        logger.error(f"Error getting group experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get group experiment pattern permission")


@group_permissions_router.patch(
    GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    summary="Update experiment pattern permission for a group",
    description="Updates a specific experiment regex pattern permission for a group.",
    response_model=StatusMessageResponse,
    tags=["group experiment pattern permissions"],
)
async def update_group_experiment_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    id: int = Path(..., description="The pattern ID"),
    pattern_data: ExperimentRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """
    Update a specific experiment regex pattern permission for a group.
    """
    try:
        store.update_group_experiment_regex_permission(
            id=id, group_name=group_name, regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission
        )
        return StatusMessageResponse(message=f"Experiment pattern permission updated for group {group_name}")
    except Exception as e:
        logger.error(f"Error updating group experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update group experiment pattern permission")


@group_permissions_router.delete(
    GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    summary="Delete experiment pattern permission for a group",
    description="Deletes a specific experiment regex pattern permission for a group.",
    response_model=StatusMessageResponse,
    tags=["group experiment pattern permissions"],
)
async def delete_group_experiment_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """
    Delete a specific experiment regex pattern permission for a group.
    """
    try:
        store.delete_group_experiment_regex_permission(group_name, id)
        return StatusMessageResponse(message=f"Experiment pattern permission deleted for group {group_name}")
    except Exception as e:
        logger.error(f"Error deleting group experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete group experiment pattern permission")


@group_permissions_router.get(
    GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS,
    summary="Get group registered model pattern permissions",
    description="Retrieves all registered model regex pattern permissions for a specific group.",
    response_model=List[GroupRegisteredModelRegexPermissionItem],
    tags=["group registered model pattern permissions"],
)
async def get_group_registered_model_pattern_permissions(
    group_name: str = Path(..., description="The group name to get registered model pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[GroupRegisteredModelRegexPermissionItem]:
    """
    Get all registered model regex pattern permissions for a group.
    """
    try:
        patterns = store.list_group_registered_model_regex_permissions(group_name)
        items: List[GroupRegisteredModelRegexPermissionItem] = []
        for pattern in patterns:
            payload = pattern.to_json() if hasattr(pattern, "to_json") else None
            if isinstance(payload, dict):
                items.append(
                    GroupRegisteredModelRegexPermissionItem(
                        id=payload["id"],
                        regex=payload["regex"],
                        priority=payload["priority"],
                        group_id=payload.get("group_id"),
                        permission=payload["permission"],
                        prompt=bool(payload.get("prompt", False)),
                    )
                )
            else:
                items.append(
                    GroupRegisteredModelRegexPermissionItem(
                        id=pattern.id,
                        regex=pattern.regex,
                        priority=pattern.priority,
                        group_id=getattr(pattern, "group_id", None),
                        permission=pattern.permission,
                        prompt=bool(getattr(pattern, "prompt", False)),
                    )
                )

        return items
    except Exception as e:
        logger.error(f"Error getting group registered model pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get group registered model pattern permissions")


@group_permissions_router.post(
    GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS,
    status_code=201,
    summary="Create registered model pattern permission for a group",
    description="Creates a new regex pattern permission for a group to access registered models.",
    response_model=StatusMessageResponse,
    tags=["group registered model pattern permissions"],
)
async def create_group_registered_model_pattern_permission(
    group_name: str = Path(..., description="The group name to create registered model pattern permission for"),
    pattern_data: RegisteredModelRegexCreate = Body(..., description="The pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """
    Create a regex pattern permission for a group to access registered models.
    """
    try:
        store.create_group_registered_model_regex_permission(
            regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission, group_name=group_name
        )
        return StatusMessageResponse(message=f"Registered model pattern permission created for group {group_name}")
    except Exception as e:
        logger.error(f"Error creating group registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create group registered model pattern permission")


@group_permissions_router.get(
    GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    summary="Get specific registered model pattern permission for a group",
    description="Retrieves a specific registered model regex pattern permission for a group.",
    response_model=GroupRegisteredModelRegexPermissionItem,
    tags=["group registered model pattern permissions"],
)
async def get_group_registered_model_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> GroupRegisteredModelRegexPermissionItem:
    """
    Get a specific registered model regex pattern permission for a group.
    """
    try:
        pattern = store.get_group_registered_model_regex_permission(group_name, id)
        payload = pattern.to_json() if hasattr(pattern, "to_json") else None
        if isinstance(payload, dict):
            item = GroupRegisteredModelRegexPermissionItem(
                id=payload["id"],
                regex=payload["regex"],
                priority=payload["priority"],
                group_id=payload.get("group_id"),
                permission=payload["permission"],
                prompt=bool(payload.get("prompt", False)),
            )
        else:
            item = GroupRegisteredModelRegexPermissionItem(
                id=pattern.id,
                regex=pattern.regex,
                priority=pattern.priority,
                group_id=getattr(pattern, "group_id", None),
                permission=pattern.permission,
                prompt=bool(getattr(pattern, "prompt", False)),
            )

        return item
    except Exception as e:
        logger.error(f"Error getting group registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get group registered model pattern permission")


@group_permissions_router.patch(
    GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    summary="Update registered model pattern permission for a group",
    description="Updates a specific registered model regex pattern permission for a group.",
    response_model=StatusMessageResponse,
    tags=["group registered model pattern permissions"],
)
async def update_group_registered_model_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    id: int = Path(..., description="The pattern ID"),
    pattern_data: RegisteredModelRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """
    Update a specific registered model regex pattern permission for a group.
    """
    try:
        store.update_group_registered_model_regex_permission(
            id=id, group_name=group_name, regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission
        )
        return StatusMessageResponse(message=f"Registered model pattern permission updated for group {group_name}")
    except Exception as e:
        logger.error(f"Error updating group registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update group registered model pattern permission")


@group_permissions_router.delete(
    GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    summary="Delete registered model pattern permission for a group",
    description="Deletes a specific registered model regex pattern permission for a group.",
    response_model=StatusMessageResponse,
    tags=["group registered model pattern permissions"],
)
async def delete_group_registered_model_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """
    Delete a specific registered model regex pattern permission for a group.
    """
    try:
        store.delete_group_registered_model_regex_permission(group_name, id)
        return StatusMessageResponse(message=f"Registered model pattern permission deleted for group {group_name}")
    except Exception as e:
        logger.error(f"Error deleting group registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete group registered model pattern permission")


@group_permissions_router.get(
    GROUP_PROMPT_PATTERN_PERMISSIONS,
    summary="Get group prompt pattern permissions",
    description="Retrieves all prompt regex pattern permissions for a specific group.",
    response_model=List[GroupPromptRegexPermissionItem],
    tags=["group prompt pattern permissions"],
)
async def get_group_prompt_pattern_permissions(
    group_name: str = Path(..., description="The group name to get prompt pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[GroupPromptRegexPermissionItem]:
    """
    Get all prompt regex pattern permissions for a group.
    """
    try:
        patterns = store.list_group_prompt_regex_permissions(group_name)
        items: List[GroupPromptRegexPermissionItem] = []
        for pattern in patterns:
            payload = pattern.to_json() if hasattr(pattern, "to_json") else None
            if isinstance(payload, dict):
                items.append(
                    GroupPromptRegexPermissionItem(
                        id=payload["id"],
                        regex=payload["regex"],
                        priority=payload["priority"],
                        group_id=payload.get("group_id"),
                        permission=payload["permission"],
                        prompt=bool(payload.get("prompt", False)),
                    )
                )
            else:
                items.append(
                    GroupPromptRegexPermissionItem(
                        id=pattern.id,
                        regex=pattern.regex,
                        priority=pattern.priority,
                        group_id=getattr(pattern, "group_id", None),
                        permission=pattern.permission,
                        prompt=bool(getattr(pattern, "prompt", False)),
                    )
                )

        return items
    except Exception as e:
        logger.error(f"Error getting group prompt pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get group prompt pattern permissions")


@group_permissions_router.post(
    GROUP_PROMPT_PATTERN_PERMISSIONS,
    status_code=201,
    summary="Create prompt pattern permission for a group",
    description="Creates a new regex pattern permission for a group to access prompts.",
    response_model=StatusMessageResponse,
    tags=["group prompt pattern permissions"],
)
async def create_group_prompt_pattern_permission(
    group_name: str = Path(..., description="The group name to create prompt pattern permission for"),
    pattern_data: PromptRegexCreate = Body(..., description="The pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """
    Create a regex pattern permission for a group to access prompts.
    """
    try:
        store.create_group_prompt_regex_permission(
            regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission, group_name=group_name
        )
        return StatusMessageResponse(message=f"Prompt pattern permission created for group {group_name}")
    except Exception as e:
        logger.error(f"Error creating group prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create group prompt pattern permission")


@group_permissions_router.get(
    GROUP_PROMPT_PATTERN_PERMISSION_DETAIL,
    summary="Get specific prompt pattern permission for a group",
    description="Retrieves a specific prompt regex pattern permission for a group.",
    response_model=GroupPromptRegexPermissionItem,
    tags=["group prompt pattern permissions"],
)
async def get_group_prompt_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> GroupPromptRegexPermissionItem:
    """
    Get a specific prompt regex pattern permission for a group.
    """
    try:
        pattern = store.get_group_prompt_regex_permission(id, group_name)
        payload = pattern.to_json() if hasattr(pattern, "to_json") else None
        if isinstance(payload, dict):
            item = GroupPromptRegexPermissionItem(
                id=payload["id"],
                regex=payload["regex"],
                priority=payload["priority"],
                group_id=payload.get("group_id"),
                permission=payload["permission"],
                prompt=bool(payload.get("prompt", False)),
            )
        else:
            item = GroupPromptRegexPermissionItem(
                id=pattern.id,
                regex=pattern.regex,
                priority=pattern.priority,
                group_id=getattr(pattern, "group_id", None),
                permission=pattern.permission,
                prompt=bool(getattr(pattern, "prompt", False)),
            )

        return item
    except Exception as e:
        logger.error(f"Error getting group prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get group prompt pattern permission")


@group_permissions_router.patch(
    GROUP_PROMPT_PATTERN_PERMISSION_DETAIL,
    summary="Update prompt pattern permission for a group",
    description="Updates a specific prompt regex pattern permission for a group.",
    response_model=StatusMessageResponse,
    tags=["group prompt pattern permissions"],
)
async def update_group_prompt_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    id: int = Path(..., description="The pattern ID"),
    pattern_data: PromptRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """
    Update a specific prompt regex pattern permission for a group.
    """
    try:
        store.update_group_prompt_regex_permission(
            id=id, group_name=group_name, regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission
        )
        return StatusMessageResponse(message=f"Prompt pattern permission updated for group {group_name}")
    except Exception as e:
        logger.error(f"Error updating group prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update group prompt pattern permission")


@group_permissions_router.delete(
    GROUP_PROMPT_PATTERN_PERMISSION_DETAIL,
    summary="Delete prompt pattern permission for a group",
    description="Deletes a specific prompt regex pattern permission for a group.",
    response_model=StatusMessageResponse,
    tags=["group prompt pattern permissions"],
)
async def delete_group_prompt_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """
    Delete a specific prompt regex pattern permission for a group.
    """
    try:
        store.delete_group_prompt_regex_permission(id, group_name)
        return StatusMessageResponse(message=f"Prompt pattern permission deleted for group {group_name}")
    except Exception as e:
        logger.error(f"Error deleting group prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete group prompt pattern permission")


@group_permissions_router.get(
    GROUP_SCORER_PERMISSIONS,
    summary="List scorer permissions for a group",
    description="Retrieves a list of scorers with permission information for the specified group.",
    response_model=List[GroupScorerPermissionItem],
    tags=["group scorer permissions"],
)
async def get_group_scorers(
    group_name: str = Path(..., description="The group name to get scorer permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[GroupScorerPermissionItem]:
    """List scorer permissions for a group.

    Admins can see all group scorer permissions. Regular users only see entries
    for scorers belonging to experiments they can manage.
    """
    try:
        group_scorers = store.list_group_scorer_permissions(group_name)
        filtered = (
            group_scorers
            if is_admin
            else [sp for sp in group_scorers if effective_experiment_permission(sp.experiment_id, current_username).permission.can_manage]
        )
        return [
            GroupScorerPermissionItem(
                experiment_id=str(scorer.experiment_id),
                scorer_name=scorer.scorer_name,
                group_id=scorer.group_id,
                permission=scorer.permission,
            )
            for scorer in filtered
        ]
    except Exception as e:
        logger.error(f"Error retrieving group scorer permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve group scorer permissions")


@group_permissions_router.post(
    GROUP_SCORER_PERMISSION_DETAIL,
    status_code=201,
    summary="Create scorer permission for a group",
    description="Creates a new permission for a group to access a specific scorer.",
    response_model=StatusMessageResponse,
    tags=["group scorer permissions"],
)
async def create_group_scorer_permission(
    group_name: str = Path(..., description="The group name to grant scorer permission to"),
    experiment_id: str = Path(..., description="The experiment ID owning the scorer"),
    scorer_name: str = Path(..., description="The scorer name"),
    permission_data: ScorerPermission = Body(..., description="The permission details"),
    _: None = Depends(check_experiment_manage_permission),
) -> StatusMessageResponse:
    try:
        store.create_group_scorer_permission(
            group_name=group_name,
            experiment_id=str(experiment_id),
            scorer_name=str(scorer_name),
            permission=str(permission_data.permission),
        )
        return StatusMessageResponse(message=f"Scorer permission created for group {group_name} on scorer {scorer_name}")
    except Exception as e:
        logger.error(f"Error creating group scorer permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create group scorer permission")


@group_permissions_router.patch(
    GROUP_SCORER_PERMISSION_DETAIL,
    summary="Update scorer permission for a group",
    description="Updates the permission for a group on a specific scorer.",
    response_model=StatusMessageResponse,
    tags=["group scorer permissions"],
)
async def update_group_scorer_permission(
    group_name: str = Path(..., description="The group name to update scorer permission for"),
    experiment_id: str = Path(..., description="The experiment ID owning the scorer"),
    scorer_name: str = Path(..., description="The scorer name"),
    permission_data: ScorerPermission = Body(..., description="Updated permission details"),
    _: None = Depends(check_experiment_manage_permission),
) -> StatusMessageResponse:
    try:
        store.update_group_scorer_permission(
            group_name=group_name,
            experiment_id=str(experiment_id),
            scorer_name=str(scorer_name),
            permission=str(permission_data.permission),
        )
        return StatusMessageResponse(message=f"Scorer permission updated for group {group_name} on scorer {scorer_name}")
    except Exception as e:
        logger.error(f"Error updating group scorer permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update group scorer permission")


@group_permissions_router.delete(
    GROUP_SCORER_PERMISSION_DETAIL,
    summary="Delete scorer permission for a group",
    description="Deletes the permission for a group on a specific scorer.",
    response_model=StatusMessageResponse,
    tags=["group scorer permissions"],
)
async def delete_group_scorer_permission(
    group_name: str = Path(..., description="The group name to delete scorer permission for"),
    experiment_id: str = Path(..., description="The experiment ID owning the scorer"),
    scorer_name: str = Path(..., description="The scorer name"),
    _: None = Depends(check_experiment_manage_permission),
) -> StatusMessageResponse:
    try:
        store.delete_group_scorer_permission(group_name, str(experiment_id), str(scorer_name))
        return StatusMessageResponse(message=f"Scorer permission deleted for group {group_name} on scorer {scorer_name}")
    except Exception as e:
        logger.error(f"Error deleting group scorer permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete group scorer permission")


@group_permissions_router.get(
    GROUP_SCORER_PATTERN_PERMISSIONS,
    summary="Get group scorer pattern permissions",
    description="Retrieves all scorer regex pattern permissions for a specific group.",
    response_model=List[GroupScorerRegexPermissionItem],
    tags=["group scorer pattern permissions"],
)
async def get_group_scorer_pattern_permissions(
    group_name: str = Path(..., description="The group name to get scorer pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[GroupScorerRegexPermissionItem]:
    try:
        patterns = store.list_group_scorer_regex_permissions(group_name)
        items: List[GroupScorerRegexPermissionItem] = []
        for pattern in patterns:
            payload = pattern.to_json() if hasattr(pattern, "to_json") else None
            if isinstance(payload, dict):
                items.append(
                    GroupScorerRegexPermissionItem(
                        id=payload["id"],
                        regex=payload["regex"],
                        priority=payload["priority"],
                        group_id=payload.get("group_id"),
                        permission=payload["permission"],
                    )
                )
            else:
                items.append(
                    GroupScorerRegexPermissionItem(
                        id=pattern.id,
                        regex=pattern.regex,
                        priority=pattern.priority,
                        group_id=getattr(pattern, "group_id", None),
                        permission=pattern.permission,
                    )
                )

        return items
    except Exception as e:
        logger.error(f"Error getting group scorer pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get group scorer pattern permissions")


@group_permissions_router.post(
    GROUP_SCORER_PATTERN_PERMISSIONS,
    status_code=201,
    summary="Create scorer pattern permission for a group",
    description="Creates a new regex pattern permission for a group to access scorers.",
    response_model=StatusMessageResponse,
    tags=["group scorer pattern permissions"],
)
async def create_group_scorer_pattern_permission(
    group_name: str = Path(..., description="The group name to create scorer pattern permission for"),
    pattern_data: ScorerRegexCreate = Body(..., description="The pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    try:
        store.create_group_scorer_regex_permission(
            group_name=group_name,
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
        )
        return StatusMessageResponse(message=f"Scorer pattern permission created for group {group_name}")
    except Exception as e:
        logger.error(f"Error creating group scorer pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create group scorer pattern permission")


@group_permissions_router.get(
    GROUP_SCORER_PATTERN_PERMISSION_DETAIL,
    summary="Get specific scorer pattern permission for a group",
    description="Retrieves a specific scorer regex pattern permission for a group.",
    response_model=GroupScorerRegexPermissionItem,
    tags=["group scorer pattern permissions"],
)
async def get_group_scorer_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> GroupScorerRegexPermissionItem:
    try:
        pattern = store.get_group_scorer_regex_permission(group_name, id)
        payload = pattern.to_json() if hasattr(pattern, "to_json") else None
        if isinstance(payload, dict):
            item = GroupScorerRegexPermissionItem(
                id=payload["id"],
                regex=payload["regex"],
                priority=payload["priority"],
                group_id=payload.get("group_id"),
                permission=payload["permission"],
            )
        else:
            item = GroupScorerRegexPermissionItem(
                id=pattern.id,
                regex=pattern.regex,
                priority=pattern.priority,
                group_id=getattr(pattern, "group_id", None),
                permission=pattern.permission,
            )

        return item
    except Exception as e:
        logger.error(f"Error getting group scorer pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get group scorer pattern permission")


@group_permissions_router.patch(
    GROUP_SCORER_PATTERN_PERMISSION_DETAIL,
    summary="Update scorer pattern permission for a group",
    description="Updates a specific scorer regex pattern permission for a group.",
    response_model=StatusMessageResponse,
    tags=["group scorer pattern permissions"],
)
async def update_group_scorer_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    id: int = Path(..., description="The pattern ID"),
    pattern_data: ScorerRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    try:
        store.update_group_scorer_regex_permission(
            id=id,
            group_name=group_name,
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
        )
        return StatusMessageResponse(message=f"Scorer pattern permission updated for group {group_name}")
    except Exception as e:
        logger.error(f"Error updating group scorer pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update group scorer pattern permission")


@group_permissions_router.delete(
    GROUP_SCORER_PATTERN_PERMISSION_DETAIL,
    summary="Delete scorer pattern permission for a group",
    description="Deletes a specific scorer regex pattern permission for a group.",
    response_model=StatusMessageResponse,
    tags=["group scorer pattern permissions"],
)
async def delete_group_scorer_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    try:
        store.delete_group_scorer_regex_permission(id, group_name)
        return StatusMessageResponse(message=f"Scorer pattern permission deleted for group {group_name}")
    except Exception as e:
        logger.error(f"Error deleting group scorer pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete group scorer pattern permission")


# ========================================================================================
# GATEWAY ENDPOINT PERMISSIONS
# ========================================================================================


@group_permissions_router.get(
    GROUP_GATEWAY_ENDPOINT_PERMISSIONS,
    response_model=List[GatewayPermissionRecord],
    summary="List gateway endpoint permissions for a group",
    description="Retrieves a list of gateway endpoint permissions for the specified group.",
    tags=["group gateway endpoint permissions"],
)
async def get_group_gateway_endpoint_permissions(
    group_name: str = Path(..., description="The group name to get gateway endpoint permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[GatewayPermissionRecord]:
    """List gateway endpoint permissions for a group."""
    try:
        perms = store.list_group_gateway_endpoint_permissions(group_name=group_name)
        return [GatewayPermissionRecord(gateway_name=p.gateway_name, user_id=None, permission=p.permission, group_id=p.group_id) for p in perms]
    except Exception as e:
        logger.error(f"Error listing group gateway endpoint permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve group gateway endpoint permissions")


@group_permissions_router.post(
    GROUP_GATEWAY_ENDPOINT_PERMISSION_DETAIL,
    status_code=201,
    response_model=GatewayPermissionResponse,
    summary="Create gateway endpoint permission for a group",
    description="Creates a new permission for a group to access a specific gateway endpoint.",
    tags=["group gateway endpoint permissions"],
)
async def create_group_gateway_endpoint_permission(
    group_name: str = Path(..., description="The group name to grant gateway endpoint permission to"),
    name: str = Path(..., description="The gateway endpoint name to set permissions for"),
    permission_data: GatewayPermission = Body(..., description="The permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> GatewayPermissionResponse:
    """Create a gateway endpoint permission for a group."""
    try:
        perm = store.create_group_gateway_endpoint_permission(group_name=group_name, gateway_name=name, permission=permission_data.permission)
        return GatewayPermissionResponse(
            gateway_permission=GatewayPermissionRecord(gateway_name=perm.gateway_name, user_id=None, permission=perm.permission, group_id=perm.group_id)
        )
    except Exception as e:
        logger.error(f"Error creating group gateway endpoint permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create group gateway endpoint permission")


@group_permissions_router.get(
    GROUP_GATEWAY_ENDPOINT_PERMISSION_DETAIL,
    response_model=GatewayPermissionResponse,
    summary="Get gateway endpoint permission for a group",
    description="Retrieves the permission for a group on a specific gateway endpoint.",
    tags=["group gateway endpoint permissions"],
)
async def get_group_gateway_endpoint_permission(
    group_name: str = Path(..., description="The group name to get gateway endpoint permission for"),
    name: str = Path(..., description="The gateway endpoint name to get permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> GatewayPermissionResponse:
    """Get a gateway endpoint permission for a group."""
    try:
        perm = store.get_user_groups_gateway_endpoint_permission(gateway_name=name, group_name=group_name)
        return GatewayPermissionResponse(
            gateway_permission=GatewayPermissionRecord(gateway_name=perm.gateway_name, user_id=None, permission=perm.permission, group_id=perm.group_id)
        )
    except Exception as e:
        logger.error(f"Error getting group gateway endpoint permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Group gateway endpoint permission not found")


@group_permissions_router.patch(
    GROUP_GATEWAY_ENDPOINT_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Update gateway endpoint permission for a group",
    description="Updates the permission for a group on a specific gateway endpoint.",
    tags=["group gateway endpoint permissions"],
)
async def update_group_gateway_endpoint_permission(
    group_name: str = Path(..., description="The group name to update gateway endpoint permission for"),
    name: str = Path(..., description="The gateway endpoint name to update permissions for"),
    permission_data: GatewayPermission = Body(..., description="Updated permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Update a gateway endpoint permission for a group."""
    try:
        store.update_group_gateway_endpoint_permission(group_name=group_name, gateway_name=name, permission=permission_data.permission)
        return StatusMessageResponse(message=f"Gateway endpoint permission updated for group {group_name} on {name}")
    except Exception as e:
        logger.error(f"Error updating group gateway endpoint permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update group gateway endpoint permission")


@group_permissions_router.delete(
    GROUP_GATEWAY_ENDPOINT_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway endpoint permission for a group",
    description="Deletes the permission for a group on a specific gateway endpoint.",
    tags=["group gateway endpoint permissions"],
)
async def delete_group_gateway_endpoint_permission(
    group_name: str = Path(..., description="The group name to delete gateway endpoint permission for"),
    name: str = Path(..., description="The gateway endpoint name to delete permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway endpoint permission for a group."""
    try:
        store.delete_group_gateway_endpoint_permission(group_name=group_name, gateway_name=name)
        return StatusMessageResponse(message=f"Gateway endpoint permission deleted for group {group_name} on {name}")
    except Exception as e:
        logger.error(f"Error deleting group gateway endpoint permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete group gateway endpoint permission")


# ========================================================================================
# GATEWAY ENDPOINT PATTERN PERMISSIONS
# ========================================================================================


@group_permissions_router.get(
    GROUP_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS,
    response_model=List[GatewayRegexPermissionRecord],
    summary="List gateway endpoint pattern permissions for a group",
    description="Retrieves a list of regex-based gateway endpoint permission patterns for the specified group.",
    tags=["group gateway endpoint pattern permissions"],
)
async def get_group_gateway_endpoint_pattern_permissions(
    group_name: str = Path(..., description="The group name to list gateway endpoint pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[GatewayRegexPermissionRecord]:
    """List gateway endpoint pattern permissions for a group."""
    try:
        perms = store.list_group_gateway_endpoint_regex_permissions(group_name=group_name)
        return [GatewayRegexPermissionRecord(id=p.id, regex=p.regex, priority=p.priority, user_id=p.group_id, permission=p.permission) for p in perms]
    except Exception as e:
        logger.error(f"Error listing group gateway endpoint pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve group gateway endpoint pattern permissions")


@group_permissions_router.post(
    GROUP_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS,
    status_code=201,
    response_model=GatewayRegexPermissionResponse,
    summary="Create gateway endpoint pattern permission for a group",
    description="Creates a new regex-based permission pattern for gateway endpoint access.",
    tags=["group gateway endpoint pattern permissions"],
)
async def create_group_gateway_endpoint_pattern_permission(
    group_name: str = Path(..., description="The group name to create gateway endpoint pattern permission for"),
    pattern_data: GatewayRegexCreate = Body(..., description="The regex pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> GatewayRegexPermissionResponse:
    """Create a gateway endpoint pattern permission for a group."""
    try:
        perm = store.create_group_gateway_endpoint_regex_permission(
            group_name=group_name, regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission
        )
        return GatewayRegexPermissionResponse(
            gateway_permission=GatewayRegexPermissionRecord(
                id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.group_id, permission=perm.permission
            )
        )
    except Exception as e:
        logger.error(f"Error creating group gateway endpoint pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create group gateway endpoint pattern permission")


@group_permissions_router.get(
    GROUP_GATEWAY_ENDPOINT_PATTERN_PERMISSION_DETAIL,
    response_model=GatewayRegexPermissionResponse,
    summary="Get gateway endpoint pattern permission for a group",
    description="Retrieves a specific regex-based gateway endpoint permission pattern for the specified group.",
    tags=["group gateway endpoint pattern permissions"],
)
async def get_group_gateway_endpoint_pattern_permission(
    group_name: str = Path(..., description="The group name to get gateway endpoint pattern permission for"),
    id: int = Path(..., description="The pattern ID to retrieve"),
    admin_username: str = Depends(check_admin_permission),
) -> GatewayRegexPermissionResponse:
    """Get a gateway endpoint pattern permission for a group."""
    try:
        perm = store.get_group_gateway_endpoint_regex_permission(id=id, group_name=group_name)
        return GatewayRegexPermissionResponse(
            gateway_permission=GatewayRegexPermissionRecord(
                id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.group_id, permission=perm.permission
            )
        )
    except Exception as e:
        logger.error(f"Error getting group gateway endpoint pattern permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Group gateway endpoint pattern permission not found")


@group_permissions_router.patch(
    GROUP_GATEWAY_ENDPOINT_PATTERN_PERMISSION_DETAIL,
    response_model=GatewayRegexPermissionResponse,
    summary="Update gateway endpoint pattern permission for a group",
    description="Updates a specific regex-based gateway endpoint permission pattern for the specified group.",
    tags=["group gateway endpoint pattern permissions"],
)
async def update_group_gateway_endpoint_pattern_permission(
    group_name: str = Path(..., description="The group name to update gateway endpoint pattern permission for"),
    id: int = Path(..., description="The pattern ID to update"),
    pattern_data: GatewayRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> GatewayRegexPermissionResponse:
    """Update a gateway endpoint pattern permission for a group."""
    try:
        perm = store.update_group_gateway_endpoint_regex_permission(
            id=id, group_name=group_name, regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission
        )
        return GatewayRegexPermissionResponse(
            gateway_permission=GatewayRegexPermissionRecord(
                id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.group_id, permission=perm.permission
            )
        )
    except Exception as e:
        logger.error(f"Error updating group gateway endpoint pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update group gateway endpoint pattern permission")


@group_permissions_router.delete(
    GROUP_GATEWAY_ENDPOINT_PATTERN_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway endpoint pattern permission for a group",
    description="Deletes a specific regex-based gateway endpoint permission pattern for the specified group.",
    tags=["group gateway endpoint pattern permissions"],
)
async def delete_group_gateway_endpoint_pattern_permission(
    group_name: str = Path(..., description="The group name to delete gateway endpoint pattern permission for"),
    id: int = Path(..., description="The pattern ID to delete"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway endpoint pattern permission for a group."""
    try:
        store.delete_group_gateway_endpoint_regex_permission(id=id, group_name=group_name)
        return StatusMessageResponse(message=f"Gateway endpoint pattern permission deleted for group {group_name}")
    except Exception as e:
        logger.error(f"Error deleting group gateway endpoint pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete group gateway endpoint pattern permission")


# ========================================================================================
# GATEWAY MODEL DEFINITION PERMISSIONS
# ========================================================================================


@group_permissions_router.get(
    GROUP_GATEWAY_MODEL_DEFINITION_PERMISSIONS,
    response_model=List[GatewayPermissionRecord],
    summary="List gateway model definition permissions for a group",
    description="Retrieves a list of gateway model definition permissions for the specified group.",
    tags=["group gateway model definition permissions"],
)
async def get_group_gateway_model_definition_permissions(
    group_name: str = Path(..., description="The group name to get gateway model definition permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[GatewayPermissionRecord]:
    """List gateway model definition permissions for a group."""
    try:
        perms = store.list_group_gateway_model_definition_permissions(group_name=group_name)
        return [GatewayPermissionRecord(gateway_name=p.gateway_name, user_id=None, permission=p.permission, group_id=p.group_id) for p in perms]
    except Exception as e:
        logger.error(f"Error listing group gateway model definition permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve group gateway model definition permissions")


@group_permissions_router.post(
    GROUP_GATEWAY_MODEL_DEFINITION_PERMISSION_DETAIL,
    status_code=201,
    response_model=GatewayPermissionResponse,
    summary="Create gateway model definition permission for a group",
    description="Creates a new permission for a group to access a specific gateway model definition.",
    tags=["group gateway model definition permissions"],
)
async def create_group_gateway_model_definition_permission(
    group_name: str = Path(..., description="The group name to grant gateway model definition permission to"),
    name: str = Path(..., description="The gateway model definition name to set permissions for"),
    permission_data: GatewayPermission = Body(..., description="The permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> GatewayPermissionResponse:
    """Create a gateway model definition permission for a group."""
    try:
        perm = store.create_group_gateway_model_definition_permission(group_name=group_name, gateway_name=name, permission=permission_data.permission)
        return GatewayPermissionResponse(
            gateway_permission=GatewayPermissionRecord(gateway_name=perm.gateway_name, user_id=None, permission=perm.permission, group_id=perm.group_id)
        )
    except Exception as e:
        logger.error(f"Error creating group gateway model definition permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create group gateway model definition permission")


@group_permissions_router.get(
    GROUP_GATEWAY_MODEL_DEFINITION_PERMISSION_DETAIL,
    response_model=GatewayPermissionResponse,
    summary="Get gateway model definition permission for a group",
    description="Retrieves the permission for a group on a specific gateway model definition.",
    tags=["group gateway model definition permissions"],
)
async def get_group_gateway_model_definition_permission(
    group_name: str = Path(..., description="The group name to get gateway model definition permission for"),
    name: str = Path(..., description="The gateway model definition name to get permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> GatewayPermissionResponse:
    """Get a gateway model definition permission for a group."""
    try:
        perm = store.get_user_groups_gateway_model_definition_permission(gateway_name=name, group_name=group_name)
        return GatewayPermissionResponse(
            gateway_permission=GatewayPermissionRecord(gateway_name=perm.gateway_name, user_id=None, permission=perm.permission, group_id=perm.group_id)
        )
    except Exception as e:
        logger.error(f"Error getting group gateway model definition permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Group gateway model definition permission not found")


@group_permissions_router.patch(
    GROUP_GATEWAY_MODEL_DEFINITION_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Update gateway model definition permission for a group",
    description="Updates the permission for a group on a specific gateway model definition.",
    tags=["group gateway model definition permissions"],
)
async def update_group_gateway_model_definition_permission(
    group_name: str = Path(..., description="The group name to update gateway model definition permission for"),
    name: str = Path(..., description="The gateway model definition name to update permissions for"),
    permission_data: GatewayPermission = Body(..., description="Updated permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Update a gateway model definition permission for a group."""
    try:
        store.update_group_gateway_model_definition_permission(group_name=group_name, gateway_name=name, permission=permission_data.permission)
        return StatusMessageResponse(message=f"Gateway model definition permission updated for group {group_name} on {name}")
    except Exception as e:
        logger.error(f"Error updating group gateway model definition permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update group gateway model definition permission")


@group_permissions_router.delete(
    GROUP_GATEWAY_MODEL_DEFINITION_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway model definition permission for a group",
    description="Deletes the permission for a group on a specific gateway model definition.",
    tags=["group gateway model definition permissions"],
)
async def delete_group_gateway_model_definition_permission(
    group_name: str = Path(..., description="The group name to delete gateway model definition permission for"),
    name: str = Path(..., description="The gateway model definition name to delete permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway model definition permission for a group."""
    try:
        store.delete_group_gateway_model_definition_permission(group_name=group_name, gateway_name=name)
        return StatusMessageResponse(message=f"Gateway model definition permission deleted for group {group_name} on {name}")
    except Exception as e:
        logger.error(f"Error deleting group gateway model definition permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete group gateway model definition permission")


# ========================================================================================
# GATEWAY MODEL DEFINITION PATTERN PERMISSIONS
# ========================================================================================


@group_permissions_router.get(
    GROUP_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSIONS,
    response_model=List[GatewayRegexPermissionRecord],
    summary="List gateway model definition pattern permissions for a group",
    description="Retrieves a list of regex-based gateway model definition permission patterns for the specified group.",
    tags=["group gateway model definition pattern permissions"],
)
async def get_group_gateway_model_definition_pattern_permissions(
    group_name: str = Path(..., description="The group name to list gateway model definition pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[GatewayRegexPermissionRecord]:
    """List gateway model definition pattern permissions for a group."""
    try:
        perms = store.list_group_gateway_model_definition_regex_permissions(group_name=group_name)
        return [GatewayRegexPermissionRecord(id=p.id, regex=p.regex, priority=p.priority, user_id=p.group_id, permission=p.permission) for p in perms]
    except Exception as e:
        logger.error(f"Error listing group gateway model definition pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve group gateway model definition pattern permissions")


@group_permissions_router.post(
    GROUP_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSIONS,
    status_code=201,
    response_model=GatewayRegexPermissionResponse,
    summary="Create gateway model definition pattern permission for a group",
    description="Creates a new regex-based permission pattern for gateway model definition access.",
    tags=["group gateway model definition pattern permissions"],
)
async def create_group_gateway_model_definition_pattern_permission(
    group_name: str = Path(..., description="The group name to create gateway model definition pattern permission for"),
    pattern_data: GatewayRegexCreate = Body(..., description="The regex pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> GatewayRegexPermissionResponse:
    """Create a gateway model definition pattern permission for a group."""
    try:
        perm = store.create_group_gateway_model_definition_regex_permission(
            group_name=group_name, regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission
        )
        return GatewayRegexPermissionResponse(
            gateway_permission=GatewayRegexPermissionRecord(
                id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.group_id, permission=perm.permission
            )
        )
    except Exception as e:
        logger.error(f"Error creating group gateway model definition pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create group gateway model definition pattern permission")


@group_permissions_router.get(
    GROUP_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSION_DETAIL,
    response_model=GatewayRegexPermissionResponse,
    summary="Get gateway model definition pattern permission for a group",
    description="Retrieves a specific regex-based gateway model definition permission pattern for the specified group.",
    tags=["group gateway model definition pattern permissions"],
)
async def get_group_gateway_model_definition_pattern_permission(
    group_name: str = Path(..., description="The group name to get gateway model definition pattern permission for"),
    id: int = Path(..., description="The pattern ID to retrieve"),
    admin_username: str = Depends(check_admin_permission),
) -> GatewayRegexPermissionResponse:
    """Get a gateway model definition pattern permission for a group."""
    try:
        perm = store.get_group_gateway_model_definition_regex_permission(id=id, group_name=group_name)
        return GatewayRegexPermissionResponse(
            gateway_permission=GatewayRegexPermissionRecord(
                id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.group_id, permission=perm.permission
            )
        )
    except Exception as e:
        logger.error(f"Error getting group gateway model definition pattern permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Group gateway model definition pattern permission not found")


@group_permissions_router.patch(
    GROUP_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSION_DETAIL,
    response_model=GatewayRegexPermissionResponse,
    summary="Update gateway model definition pattern permission for a group",
    description="Updates a specific regex-based gateway model definition permission pattern for the specified group.",
    tags=["group gateway model definition pattern permissions"],
)
async def update_group_gateway_model_definition_pattern_permission(
    group_name: str = Path(..., description="The group name to update gateway model definition pattern permission for"),
    id: int = Path(..., description="The pattern ID to update"),
    pattern_data: GatewayRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> GatewayRegexPermissionResponse:
    """Update a gateway model definition pattern permission for a group."""
    try:
        perm = store.update_group_gateway_model_definition_regex_permission(
            id=id, group_name=group_name, regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission
        )
        return GatewayRegexPermissionResponse(
            gateway_permission=GatewayRegexPermissionRecord(
                id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.group_id, permission=perm.permission
            )
        )
    except Exception as e:
        logger.error(f"Error updating group gateway model definition pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update group gateway model definition pattern permission")


@group_permissions_router.delete(
    GROUP_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway model definition pattern permission for a group",
    description="Deletes a specific regex-based gateway model definition permission pattern for the specified group.",
    tags=["group gateway model definition pattern permissions"],
)
async def delete_group_gateway_model_definition_pattern_permission(
    group_name: str = Path(..., description="The group name to delete gateway model definition pattern permission for"),
    id: int = Path(..., description="The pattern ID to delete"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway model definition pattern permission for a group."""
    try:
        store.delete_group_gateway_model_definition_regex_permission(id=id, group_name=group_name)
        return StatusMessageResponse(message=f"Gateway model definition pattern permission deleted for group {group_name}")
    except Exception as e:
        logger.error(f"Error deleting group gateway model definition pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete group gateway model definition pattern permission")


# ========================================================================================
# GATEWAY SECRET PERMISSIONS
# ========================================================================================


@group_permissions_router.get(
    GROUP_GATEWAY_SECRET_PERMISSIONS,
    response_model=List[GatewayPermissionRecord],
    summary="List gateway secret permissions for a group",
    description="Retrieves a list of gateway secret permissions for the specified group.",
    tags=["group gateway secret permissions"],
)
async def get_group_gateway_secret_permissions(
    group_name: str = Path(..., description="The group name to get gateway secret permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[GatewayPermissionRecord]:
    """List gateway secret permissions for a group."""
    try:
        perms = store.list_group_gateway_secret_permissions(group_name=group_name)
        return [GatewayPermissionRecord(gateway_name=p.gateway_name, user_id=None, permission=p.permission, group_id=p.group_id) for p in perms]
    except Exception as e:
        logger.error(f"Error listing group gateway secret permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve group gateway secret permissions")


@group_permissions_router.post(
    GROUP_GATEWAY_SECRET_PERMISSION_DETAIL,
    status_code=201,
    response_model=GatewayPermissionResponse,
    summary="Create gateway secret permission for a group",
    description="Creates a new permission for a group to access a specific gateway secret.",
    tags=["group gateway secret permissions"],
)
async def create_group_gateway_secret_permission(
    group_name: str = Path(..., description="The group name to grant gateway secret permission to"),
    name: str = Path(..., description="The gateway secret name to set permissions for"),
    permission_data: GatewayPermission = Body(..., description="The permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> GatewayPermissionResponse:
    """Create a gateway secret permission for a group."""
    try:
        perm = store.create_group_gateway_secret_permission(group_name=group_name, gateway_name=name, permission=permission_data.permission)
        return GatewayPermissionResponse(
            gateway_permission=GatewayPermissionRecord(gateway_name=perm.gateway_name, user_id=None, permission=perm.permission, group_id=perm.group_id)
        )
    except Exception as e:
        logger.error(f"Error creating group gateway secret permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create group gateway secret permission")


@group_permissions_router.get(
    GROUP_GATEWAY_SECRET_PERMISSION_DETAIL,
    response_model=GatewayPermissionResponse,
    summary="Get gateway secret permission for a group",
    description="Retrieves the permission for a group on a specific gateway secret.",
    tags=["group gateway secret permissions"],
)
async def get_group_gateway_secret_permission(
    group_name: str = Path(..., description="The group name to get gateway secret permission for"),
    name: str = Path(..., description="The gateway secret name to get permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> GatewayPermissionResponse:
    """Get a gateway secret permission for a group."""
    try:
        perm = store.get_user_groups_gateway_secret_permission(gateway_name=name, group_name=group_name)
        return GatewayPermissionResponse(
            gateway_permission=GatewayPermissionRecord(gateway_name=perm.gateway_name, user_id=None, permission=perm.permission, group_id=perm.group_id)
        )
    except Exception as e:
        logger.error(f"Error getting group gateway secret permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Group gateway secret permission not found")


@group_permissions_router.patch(
    GROUP_GATEWAY_SECRET_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Update gateway secret permission for a group",
    description="Updates the permission for a group on a specific gateway secret.",
    tags=["group gateway secret permissions"],
)
async def update_group_gateway_secret_permission(
    group_name: str = Path(..., description="The group name to update gateway secret permission for"),
    name: str = Path(..., description="The gateway secret name to update permissions for"),
    permission_data: GatewayPermission = Body(..., description="Updated permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Update a gateway secret permission for a group."""
    try:
        store.update_group_gateway_secret_permission(group_name=group_name, gateway_name=name, permission=permission_data.permission)
        return StatusMessageResponse(message=f"Gateway secret permission updated for group {group_name} on {name}")
    except Exception as e:
        logger.error(f"Error updating group gateway secret permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update group gateway secret permission")


@group_permissions_router.delete(
    GROUP_GATEWAY_SECRET_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway secret permission for a group",
    description="Deletes the permission for a group on a specific gateway secret.",
    tags=["group gateway secret permissions"],
)
async def delete_group_gateway_secret_permission(
    group_name: str = Path(..., description="The group name to delete gateway secret permission for"),
    name: str = Path(..., description="The gateway secret name to delete permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway secret permission for a group."""
    try:
        store.delete_group_gateway_secret_permission(group_name=group_name, gateway_name=name)
        return StatusMessageResponse(message=f"Gateway secret permission deleted for group {group_name} on {name}")
    except Exception as e:
        logger.error(f"Error deleting group gateway secret permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete group gateway secret permission")


# ========================================================================================
# GATEWAY SECRET PATTERN PERMISSIONS
# ========================================================================================


@group_permissions_router.get(
    GROUP_GATEWAY_SECRET_PATTERN_PERMISSIONS,
    response_model=List[GatewayRegexPermissionRecord],
    summary="List gateway secret pattern permissions for a group",
    description="Retrieves a list of regex-based gateway secret permission patterns for the specified group.",
    tags=["group gateway secret pattern permissions"],
)
async def get_group_gateway_secret_pattern_permissions(
    group_name: str = Path(..., description="The group name to list gateway secret pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[GatewayRegexPermissionRecord]:
    """List gateway secret pattern permissions for a group."""
    try:
        perms = store.list_group_gateway_secret_regex_permissions(group_name=group_name)
        return [GatewayRegexPermissionRecord(id=p.id, regex=p.regex, priority=p.priority, user_id=p.group_id, permission=p.permission) for p in perms]
    except Exception as e:
        logger.error(f"Error listing group gateway secret pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve group gateway secret pattern permissions")


@group_permissions_router.post(
    GROUP_GATEWAY_SECRET_PATTERN_PERMISSIONS,
    status_code=201,
    response_model=GatewayRegexPermissionResponse,
    summary="Create gateway secret pattern permission for a group",
    description="Creates a new regex-based permission pattern for gateway secret access.",
    tags=["group gateway secret pattern permissions"],
)
async def create_group_gateway_secret_pattern_permission(
    group_name: str = Path(..., description="The group name to create gateway secret pattern permission for"),
    pattern_data: GatewayRegexCreate = Body(..., description="The regex pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> GatewayRegexPermissionResponse:
    """Create a gateway secret pattern permission for a group."""
    try:
        perm = store.create_group_gateway_secret_regex_permission(
            group_name=group_name, regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission
        )
        return GatewayRegexPermissionResponse(
            gateway_permission=GatewayRegexPermissionRecord(
                id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.group_id, permission=perm.permission
            )
        )
    except Exception as e:
        logger.error(f"Error creating group gateway secret pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create group gateway secret pattern permission")


@group_permissions_router.get(
    GROUP_GATEWAY_SECRET_PATTERN_PERMISSION_DETAIL,
    response_model=GatewayRegexPermissionResponse,
    summary="Get gateway secret pattern permission for a group",
    description="Retrieves a specific regex-based gateway secret permission pattern for the specified group.",
    tags=["group gateway secret pattern permissions"],
)
async def get_group_gateway_secret_pattern_permission(
    group_name: str = Path(..., description="The group name to get gateway secret pattern permission for"),
    id: int = Path(..., description="The pattern ID to retrieve"),
    admin_username: str = Depends(check_admin_permission),
) -> GatewayRegexPermissionResponse:
    """Get a gateway secret pattern permission for a group."""
    try:
        perm = store.get_group_gateway_secret_regex_permission(id=id, group_name=group_name)
        return GatewayRegexPermissionResponse(
            gateway_permission=GatewayRegexPermissionRecord(
                id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.group_id, permission=perm.permission
            )
        )
    except Exception as e:
        logger.error(f"Error getting group gateway secret pattern permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Group gateway secret pattern permission not found")


@group_permissions_router.patch(
    GROUP_GATEWAY_SECRET_PATTERN_PERMISSION_DETAIL,
    response_model=GatewayRegexPermissionResponse,
    summary="Update gateway secret pattern permission for a group",
    description="Updates a specific regex-based gateway secret permission pattern for the specified group.",
    tags=["group gateway secret pattern permissions"],
)
async def update_group_gateway_secret_pattern_permission(
    group_name: str = Path(..., description="The group name to update gateway secret pattern permission for"),
    id: int = Path(..., description="The pattern ID to update"),
    pattern_data: GatewayRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> GatewayRegexPermissionResponse:
    """Update a gateway secret pattern permission for a group."""
    try:
        perm = store.update_group_gateway_secret_regex_permission(
            id=id, group_name=group_name, regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission
        )
        return GatewayRegexPermissionResponse(
            gateway_permission=GatewayRegexPermissionRecord(
                id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.group_id, permission=perm.permission
            )
        )
    except Exception as e:
        logger.error(f"Error updating group gateway secret pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update group gateway secret pattern permission")


@group_permissions_router.delete(
    GROUP_GATEWAY_SECRET_PATTERN_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway secret pattern permission for a group",
    description="Deletes a specific regex-based gateway secret permission pattern for the specified group.",
    tags=["group gateway secret pattern permissions"],
)
async def delete_group_gateway_secret_pattern_permission(
    group_name: str = Path(..., description="The group name to delete gateway secret pattern permission for"),
    id: int = Path(..., description="The pattern ID to delete"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway secret pattern permission for a group."""
    try:
        store.delete_group_gateway_secret_regex_permission(id=id, group_name=group_name)
        return StatusMessageResponse(message=f"Gateway secret pattern permission deleted for group {group_name}")
    except Exception as e:
        logger.error(f"Error deleting group gateway secret pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete group gateway secret pattern permission")
