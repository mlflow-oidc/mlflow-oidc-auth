"""
Group permissions router for FastAPI application.

This router handles permission management endpoints for groups, including
experiment, model, and prompt permissions at the group level.
"""

from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from fastapi.responses import JSONResponse
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.dependencies import check_admin_permission, check_experiment_manage_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import (
    ExperimentPermission,
    ExperimentRegexCreate,
    GroupUser,
    PromptPermission,
    PromptRegexCreate,
    RegisteredModelPermission,
    RegisteredModelRegexCreate,
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
    tags=["permissions", "groups"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)

LIST_GROUPS = ""

GROUP_EXPERIMENT_PERMISSIONS = "/{group_name}/experiments"
GROUP_EXPERIMENT_PERMISSION_DETAIL = "/{group_name}/experiments/{experiment_id}"
GROUP_EXPERIMENT_PATTERN_PERMISSIONS = "/{group_name}/experiment-patterns"
GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL = "/{group_name}/experiment-patterns/{pattern_id}"

# GROUP, REGISTERED_MODEL, PATTERN
GROUP_REGISTERED_MODEL_PERMISSIONS = "/{group_name}/registered-models"
GROUP_REGISTERED_MODEL_PERMISSION_DETAIL = "/{group_name}/registered-models/{name}"
GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS = "/{group_name}/registered-models-patterns"
GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL = "/{group_name}/registered-models-patterns/{pattern_id}"

# GROUP, PROMPT, PATTERN
GROUP_PROMPT_PERMISSIONS = "/{group_name}/prompts"
GROUP_PROMPT_PERMISSION_DETAIL = "/{group_name}/prompts/{prompt_name}"
GROUP_PROMPT_PATTERN_PERMISSIONS = "/{group_name}/prompts-patterns"
GROUP_PROMPT_PATTERN_PERMISSION_DETAIL = "/{group_name}/prompts-patterns/{pattern_id}"
GROUP_USER_PERMISSIONS = "/{group_name}/users"


@group_permissions_router.get(LIST_GROUPS, summary="List groups", description="Retrieves a list of all groups in the system.")
async def list_groups(username: str = Depends(get_username)) -> JSONResponse:
    """
    List all groups in the system.

    This endpoint returns all groups in the system. Any authenticated user can access this endpoint.

    Parameters:
    -----------
    username : str
        The authenticated username (injected by dependency).

    Returns:
    --------
    JSONResponse
        A JSON response containing the list of groups.

    Raises:
    -------
    HTTPException
        If there is an error retrieving the groups.
    """
    try:
        from mlflow_oidc_auth.store import store

        groups = store.get_groups()
        return JSONResponse(content=groups)

    except Exception as e:
        logger.error(f"Error listing groups: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve groups: {str(e)}")


@group_permissions_router.get(
    GROUP_USER_PERMISSIONS,
    response_model=List[GroupUser],
    summary="List users in a group",
    description="Retrieves a list of users who are members of the specified group.",
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
        raise HTTPException(status_code=404, detail=f"Group not found or error retrieving users: {str(e)}")


@group_permissions_router.get(
    GROUP_EXPERIMENT_PERMISSIONS,
    summary="List experiment permissions for a group",
    description="Retrieves a list of experiments with permission information for the specified group.",
)
async def get_group_experiments(
    group_name: str = Path(..., description="The group name to get experiment permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
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
    JSONResponse
        A list of experiments with permission information for the group.
    """
    try:
        # Get experiments that have permissions assigned to this group
        group_experiments = store.get_group_experiments(group_name)
        tracking_store = _get_tracking_store()

        # For admins: show all group experiments
        if is_admin:
            formatted_experiments = [
                {
                    "id": experiment.experiment_id,
                    "name": tracking_store.get_experiment(experiment.experiment_id).name,
                    "permission": experiment.permission,
                }
                for experiment in group_experiments
            ]
        else:
            # For regular users: only show group experiments where the user can manage that experiment
            formatted_experiments = [
                {
                    "id": experiment.experiment_id,
                    "name": tracking_store.get_experiment(experiment.experiment_id).name,
                    "permission": experiment.permission,
                }
                for experiment in group_experiments
                if effective_experiment_permission(experiment.experiment_id, current_username).permission.can_manage
            ]

        return JSONResponse(content=formatted_experiments)

    except Exception as e:
        logger.error(f"Error retrieving group experiment permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve group experiment permissions: {str(e)}")


@group_permissions_router.post(
    GROUP_EXPERIMENT_PERMISSION_DETAIL,
    status_code=201,
    summary="Create experiment permission for a group",
    description="Creates a new permission for a group to access a specific experiment.",
)
async def create_group_experiment_permission(
    group_name: str = Path(..., description="The group name to grant experiment permission to"),
    experiment_id: str = Path(..., description="The experiment ID to set permissions for"),
    permission_data: ExperimentPermission = Body(..., description="The permission details"),
    current_username: str = Depends(check_experiment_manage_permission),
) -> JSONResponse:
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
    JSONResponse
        A response indicating success.
    """
    try:
        store.create_group_experiment_permission(
            group_name,
            experiment_id,
            permission_data.permission,
        )
        return JSONResponse(
            content={"status": "success", "message": f"Experiment permission created for group {group_name} on experiment {experiment_id}"}, status_code=201
        )
    except Exception as e:
        logger.error(f"Error creating group experiment permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create group experiment permission: {str(e)}")


@group_permissions_router.patch(
    GROUP_EXPERIMENT_PERMISSION_DETAIL,
    summary="Update experiment permission for a group",
    description="Updates the permission for a group on a specific experiment.",
)
async def update_group_experiment_permission(
    group_name: str = Path(..., description="The group name to update experiment permission for"),
    experiment_id: str = Path(..., description="The experiment ID to update permissions for"),
    permission_data: ExperimentPermission = Body(..., description="Updated permission details"),
    current_username: str = Depends(check_experiment_manage_permission),
) -> JSONResponse:
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
    JSONResponse
        A response indicating success.
    """
    try:
        store.update_group_experiment_permission(
            group_name,
            experiment_id,
            permission_data.permission,
        )
        return JSONResponse(content={"status": "success", "message": f"Experiment permission updated for group {group_name} on experiment {experiment_id}"})
    except Exception as e:
        logger.error(f"Error updating group experiment permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update group experiment permission: {str(e)}")


@group_permissions_router.delete(
    GROUP_EXPERIMENT_PERMISSION_DETAIL,
    summary="Delete experiment permission for a group",
    description="Deletes the permission for a group on a specific experiment.",
)
async def delete_group_experiment_permission(
    group_name: str = Path(..., description="The group name to delete experiment permission for"),
    experiment_id: str = Path(..., description="The experiment ID to delete permissions for"),
    current_username: str = Depends(check_experiment_manage_permission),
) -> JSONResponse:
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
    JSONResponse
        A response indicating success.
    """
    try:
        store.delete_group_experiment_permission(group_name, experiment_id)
        return JSONResponse(content={"status": "success", "message": f"Experiment permission deleted for group {group_name} on experiment {experiment_id}"})
    except Exception as e:
        logger.error(f"Error deleting group experiment permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete group experiment permission: {str(e)}")


@group_permissions_router.get(
    GROUP_REGISTERED_MODEL_PERMISSIONS,
    summary="List registered model permissions for a group",
    description="Retrieves a list of registered models with permission information for the specified group.",
)
async def get_group_registered_models(
    group_name: str = Path(..., description="The group name to get registered model permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
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
    JSONResponse
        A list of registered models with permission information for the group.
    """
    try:
        # Get registered models that have permissions assigned to this group
        group_models = store.get_group_models(group_name)

        # For admins: show all group models
        if is_admin:
            formatted_models = [
                {
                    "name": model.name,
                    "permission": model.permission,
                }
                for model in group_models
            ]
        else:
            # For regular users: only show group models where the user can manage that model
            formatted_models = [
                {
                    "name": model.name,
                    "permission": model.permission,
                }
                for model in group_models
                if effective_registered_model_permission(model.name, current_username).permission.can_manage
            ]

        return JSONResponse(content=formatted_models)

    except Exception as e:
        logger.error(f"Error retrieving group registered model permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve group registered model permissions: {str(e)}")


@group_permissions_router.post(
    GROUP_REGISTERED_MODEL_PERMISSION_DETAIL,
    status_code=201,
    summary="Create registered model permission for a group",
    description="Creates a new permission for a group to access a specific registered model.",
)
async def create_group_registered_model_permission(
    group_name: str = Path(..., description="The group name to grant registered model permission to"),
    name: str = Path(..., description="The registered model name to set permissions for"),
    permission_data: RegisteredModelPermission = Body(..., description="The permission details"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
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
    JSONResponse
        A response indicating success.
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
        return JSONResponse(
            content={"status": "success", "message": f"Registered model permission created for group {group_name} on model {name}"}, status_code=201
        )
    except Exception as e:
        logger.error(f"Error creating group registered model permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create group registered model permission: {str(e)}")


@group_permissions_router.patch(
    GROUP_REGISTERED_MODEL_PERMISSION_DETAIL,
    summary="Update registered model permission for a group",
    description="Updates the permission for a group on a specific registered model.",
)
async def update_group_registered_model_permission(
    group_name: str = Path(..., description="The group name to update registered model permission for"),
    name: str = Path(..., description="The registered model name to update permissions for"),
    permission_data: RegisteredModelPermission = Body(..., description="Updated permission details"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
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
    JSONResponse
        A response indicating success.
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
        return JSONResponse(content={"status": "success", "message": f"Registered model permission updated for group {group_name} on model {name}"})
    except Exception as e:
        logger.error(f"Error updating group registered model permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update group registered model permission: {str(e)}")


@group_permissions_router.delete(
    GROUP_REGISTERED_MODEL_PERMISSION_DETAIL,
    summary="Delete registered model permission for a group",
    description="Deletes the permission for a group on a specific registered model.",
)
async def delete_group_registered_model_permission(
    group_name: str = Path(..., description="The group name to delete registered model permission for"),
    name: str = Path(..., description="The registered model name to delete permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
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
    JSONResponse
        A response indicating success.
    """
    # Check if user can manage this registered model
    if not is_admin and not effective_registered_model_permission(name, current_username).permission.can_manage:
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage registered model {name}")
    try:
        store.delete_group_model_permission(group_name, name)
        return JSONResponse(content={"status": "success", "message": f"Registered model permission deleted for group {group_name} on model {name}"})
    except Exception as e:
        logger.error(f"Error deleting group registered model permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete group registered model permission: {str(e)}")


@group_permissions_router.get(
    GROUP_PROMPT_PERMISSIONS, summary="Get group prompt permissions", description="Retrieves all prompt permissions for a specific group."
)
async def get_group_prompts(
    group_name: str = Path(..., description="The group name to get prompt permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
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
    JSONResponse
        A JSON response containing the list of prompt permissions for the group.
    """
    try:
        # Get prompts that have permissions assigned to this group
        group_prompts = store.get_group_prompts(group_name)

        # For admins: show all group prompts
        if is_admin:
            formatted_prompts = [
                {
                    "name": prompt.name,
                    "permission": prompt.permission,
                }
                for prompt in group_prompts
            ]
        else:
            # For regular users: only show group prompts where the user can manage that prompt
            formatted_prompts = [
                {
                    "name": prompt.name,
                    "permission": prompt.permission,
                }
                for prompt in group_prompts
                if effective_prompt_permission(prompt.name, current_username).permission.can_manage
            ]

        return JSONResponse(content=formatted_prompts)
    except Exception as e:
        logger.error(f"Error getting group prompt permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get group prompt permissions: {str(e)}")


@group_permissions_router.post(
    GROUP_PROMPT_PERMISSION_DETAIL,
    status_code=201,
    summary="Create prompt permission for a group",
    description="Creates a new permission for a group to access a specific prompt.",
)
async def create_group_prompt_permission(
    group_name: str = Path(..., description="The group name to grant prompt permission to"),
    prompt_name: str = Path(..., description="The prompt name to set permissions for"),
    permission_data: PromptPermission = Body(..., description="The permission details"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
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
    JSONResponse
        A response indicating success.
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
        return JSONResponse(
            content={"status": "success", "message": f"Prompt permission created for group {group_name} on prompt {prompt_name}"}, status_code=201
        )
    except Exception as e:
        logger.error(f"Error creating group prompt permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create group prompt permission: {str(e)}")


@group_permissions_router.patch(
    GROUP_PROMPT_PERMISSION_DETAIL, summary="Update prompt permission for a group", description="Updates the permission for a group on a specific prompt."
)
async def update_group_prompt_permission(
    group_name: str = Path(..., description="The group name to update prompt permission for"),
    prompt_name: str = Path(..., description="The prompt name to update permissions for"),
    permission_data: PromptPermission = Body(..., description="Updated permission details"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
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
    JSONResponse
        A response indicating success.
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
        return JSONResponse(content={"status": "success", "message": f"Prompt permission updated for group {group_name} on prompt {prompt_name}"})
    except Exception as e:
        logger.error(f"Error updating group prompt permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update group prompt permission: {str(e)}")


@group_permissions_router.delete(
    GROUP_PROMPT_PERMISSION_DETAIL, summary="Delete prompt permission for a group", description="Deletes the permission for a group on a specific prompt."
)
async def delete_group_prompt_permission(
    group_name: str = Path(..., description="The group name to delete prompt permission for"),
    prompt_name: str = Path(..., description="The prompt name to delete permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
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
    JSONResponse
        A response indicating success.
    """
    # Check if user can manage this prompt
    if not is_admin and not effective_prompt_permission(prompt_name, current_username).permission.can_manage:
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage prompt {prompt_name}")

    try:
        store.delete_group_prompt_permission(group_name, prompt_name)
        return JSONResponse(content={"status": "success", "message": f"Prompt permission deleted for group {group_name} on prompt {prompt_name}"})
    except Exception as e:
        logger.error(f"Error deleting group prompt permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete group prompt permission: {str(e)}")


@group_permissions_router.get(
    GROUP_EXPERIMENT_PATTERN_PERMISSIONS,
    summary="Get group experiment pattern permissions",
    description="Retrieves all experiment regex pattern permissions for a specific group.",
)
async def get_group_experiment_pattern_permissions(
    group_name: str = Path(..., description="The group name to get experiment pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Get all experiment regex pattern permissions for a group.
    """
    try:
        patterns = store.list_group_experiment_regex_permissions(group_name)
        return JSONResponse(content=[pattern.to_json() for pattern in patterns])
    except Exception as e:
        logger.error(f"Error getting group experiment pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get group experiment pattern permissions: {str(e)}")


@group_permissions_router.post(
    GROUP_EXPERIMENT_PATTERN_PERMISSIONS,
    status_code=201,
    summary="Create experiment pattern permission for a group",
    description="Creates a new regex pattern permission for a group to access experiments.",
)
async def create_group_experiment_pattern_permission(
    group_name: str = Path(..., description="The group name to create experiment pattern permission for"),
    pattern_data: ExperimentRegexCreate = Body(..., description="The pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Create a regex pattern permission for a group to access experiments.
    """
    try:
        store.create_group_experiment_regex_permission(
            regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission, group_name=group_name
        )
        return JSONResponse(content={"status": "success", "message": f"Experiment pattern permission created for group {group_name}"}, status_code=201)
    except Exception as e:
        logger.error(f"Error creating group experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create group experiment pattern permission: {str(e)}")


@group_permissions_router.get(
    GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    summary="Get specific experiment pattern permission for a group",
    description="Retrieves a specific experiment regex pattern permission for a group.",
)
async def get_group_experiment_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    pattern_id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Get a specific experiment regex pattern permission for a group.
    """
    try:
        pattern = store.get_group_experiment_regex_permission(group_name, pattern_id)
        return JSONResponse(content={"pattern": pattern.to_json()})
    except Exception as e:
        logger.error(f"Error getting group experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get group experiment pattern permission: {str(e)}")


@group_permissions_router.patch(
    GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    summary="Update experiment pattern permission for a group",
    description="Updates a specific experiment regex pattern permission for a group.",
)
async def update_group_experiment_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    pattern_id: int = Path(..., description="The pattern ID"),
    pattern_data: ExperimentRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Update a specific experiment regex pattern permission for a group.
    """
    try:
        store.update_group_experiment_regex_permission(
            id=pattern_id, group_name=group_name, regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission
        )
        return JSONResponse(content={"status": "success", "message": f"Experiment pattern permission updated for group {group_name}"})
    except Exception as e:
        logger.error(f"Error updating group experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update group experiment pattern permission: {str(e)}")


@group_permissions_router.delete(
    GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    summary="Delete experiment pattern permission for a group",
    description="Deletes a specific experiment regex pattern permission for a group.",
)
async def delete_group_experiment_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    pattern_id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Delete a specific experiment regex pattern permission for a group.
    """
    try:
        store.delete_group_experiment_regex_permission(group_name, pattern_id)
        return JSONResponse(content={"status": "success", "message": f"Experiment pattern permission deleted for group {group_name}"})
    except Exception as e:
        logger.error(f"Error deleting group experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete group experiment pattern permission: {str(e)}")


@group_permissions_router.get(
    GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS,
    summary="Get group registered model pattern permissions",
    description="Retrieves all registered model regex pattern permissions for a specific group.",
)
async def get_group_registered_model_pattern_permissions(
    group_name: str = Path(..., description="The group name to get registered model pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Get all registered model regex pattern permissions for a group.
    """
    try:
        patterns = store.list_group_registered_model_regex_permissions(group_name)
        return JSONResponse(content=[pattern.to_json() for pattern in patterns])
    except Exception as e:
        logger.error(f"Error getting group registered model pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get group registered model pattern permissions: {str(e)}")


@group_permissions_router.post(
    GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS,
    status_code=201,
    summary="Create registered model pattern permission for a group",
    description="Creates a new regex pattern permission for a group to access registered models.",
)
async def create_group_registered_model_pattern_permission(
    group_name: str = Path(..., description="The group name to create registered model pattern permission for"),
    pattern_data: RegisteredModelRegexCreate = Body(..., description="The pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Create a regex pattern permission for a group to access registered models.
    """
    try:
        store.create_group_registered_model_regex_permission(
            regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission, group_name=group_name
        )
        return JSONResponse(content={"status": "success", "message": f"Registered model pattern permission created for group {group_name}"}, status_code=201)
    except Exception as e:
        logger.error(f"Error creating group registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create group registered model pattern permission: {str(e)}")


@group_permissions_router.get(
    GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    summary="Get specific registered model pattern permission for a group",
    description="Retrieves a specific registered model regex pattern permission for a group.",
)
async def get_group_registered_model_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    pattern_id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Get a specific registered model regex pattern permission for a group.
    """
    try:
        pattern = store.get_group_registered_model_regex_permission(group_name, pattern_id)
        return JSONResponse(content={"pattern": pattern.to_json()})
    except Exception as e:
        logger.error(f"Error getting group registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get group registered model pattern permission: {str(e)}")


@group_permissions_router.patch(
    GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    summary="Update registered model pattern permission for a group",
    description="Updates a specific registered model regex pattern permission for a group.",
)
async def update_group_registered_model_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    pattern_id: int = Path(..., description="The pattern ID"),
    pattern_data: RegisteredModelRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Update a specific registered model regex pattern permission for a group.
    """
    try:
        store.update_group_registered_model_regex_permission(
            id=pattern_id, group_name=group_name, regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission
        )
        return JSONResponse(content={"status": "success", "message": f"Registered model pattern permission updated for group {group_name}"})
    except Exception as e:
        logger.error(f"Error updating group registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update group registered model pattern permission: {str(e)}")


@group_permissions_router.delete(
    GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    summary="Delete registered model pattern permission for a group",
    description="Deletes a specific registered model regex pattern permission for a group.",
)
async def delete_group_registered_model_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    pattern_id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Delete a specific registered model regex pattern permission for a group.
    """
    try:
        store.delete_group_registered_model_regex_permission(group_name, pattern_id)
        return JSONResponse(content={"status": "success", "message": f"Registered model pattern permission deleted for group {group_name}"})
    except Exception as e:
        logger.error(f"Error deleting group registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete group registered model pattern permission: {str(e)}")


@group_permissions_router.get(
    GROUP_PROMPT_PATTERN_PERMISSIONS,
    summary="Get group prompt pattern permissions",
    description="Retrieves all prompt regex pattern permissions for a specific group.",
)
async def get_group_prompt_pattern_permissions(
    group_name: str = Path(..., description="The group name to get prompt pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Get all prompt regex pattern permissions for a group.
    """
    try:
        patterns = store.list_group_prompt_regex_permissions(group_name)
        return JSONResponse(content=[pattern.to_json() for pattern in patterns])
    except Exception as e:
        logger.error(f"Error getting group prompt pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get group prompt pattern permissions: {str(e)}")


@group_permissions_router.post(
    GROUP_PROMPT_PATTERN_PERMISSIONS,
    status_code=201,
    summary="Create prompt pattern permission for a group",
    description="Creates a new regex pattern permission for a group to access prompts.",
)
async def create_group_prompt_pattern_permission(
    group_name: str = Path(..., description="The group name to create prompt pattern permission for"),
    pattern_data: PromptRegexCreate = Body(..., description="The pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Create a regex pattern permission for a group to access prompts.
    """
    try:
        store.create_group_prompt_regex_permission(
            regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission, group_name=group_name
        )
        return JSONResponse(content={"status": "success", "message": f"Prompt pattern permission created for group {group_name}"}, status_code=201)
    except Exception as e:
        logger.error(f"Error creating group prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create group prompt pattern permission: {str(e)}")


@group_permissions_router.get(
    GROUP_PROMPT_PATTERN_PERMISSION_DETAIL,
    summary="Get specific prompt pattern permission for a group",
    description="Retrieves a specific prompt regex pattern permission for a group.",
)
async def get_group_prompt_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    pattern_id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Get a specific prompt regex pattern permission for a group.
    """
    try:
        pattern = store.get_group_prompt_regex_permission(pattern_id, group_name)
        return JSONResponse(content={"pattern": pattern.to_json()})
    except Exception as e:
        logger.error(f"Error getting group prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get group prompt pattern permission: {str(e)}")


@group_permissions_router.patch(
    GROUP_PROMPT_PATTERN_PERMISSION_DETAIL,
    summary="Update prompt pattern permission for a group",
    description="Updates a specific prompt regex pattern permission for a group.",
)
async def update_group_prompt_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    pattern_id: int = Path(..., description="The pattern ID"),
    pattern_data: PromptRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Update a specific prompt regex pattern permission for a group.
    """
    try:
        store.update_group_prompt_regex_permission(
            id=pattern_id, group_name=group_name, regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission
        )
        return JSONResponse(content={"status": "success", "message": f"Prompt pattern permission updated for group {group_name}"})
    except Exception as e:
        logger.error(f"Error updating group prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update group prompt pattern permission: {str(e)}")


@group_permissions_router.delete(
    GROUP_PROMPT_PATTERN_PERMISSION_DETAIL,
    summary="Delete prompt pattern permission for a group",
    description="Deletes a specific prompt regex pattern permission for a group.",
)
async def delete_group_prompt_pattern_permission(
    group_name: str = Path(..., description="The group name"),
    pattern_id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Delete a specific prompt regex pattern permission for a group.
    """
    try:
        store.delete_group_prompt_regex_permission(pattern_id, group_name)
        return JSONResponse(content={"status": "success", "message": f"Prompt pattern permission deleted for group {group_name}"})
    except Exception as e:
        logger.error(f"Error deleting group prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete group prompt pattern permission: {str(e)}")
