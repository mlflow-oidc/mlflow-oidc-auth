"""
Permissions router for FastAPI application.

This router handles permission management endpoints for experiments, models, and users.
"""

from typing import List

from fastapi import APIRouter, Body, Depends, Path
from fastapi.exceptions import HTTPException
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from fastapi.responses import JSONResponse
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.dependencies import check_admin_permission, check_experiment_manage_permission, check_registered_model_manage_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import (
    ExperimentPermission,
    ExperimentPermissionSummary,
    ExperimentRegexCreate,
    ExperimentRegexPermission,
    PromptPermission,
    PromptRegexCreate,
    RegisteredModelPermission,
    RegisteredModelRegexCreate,
    ScorerPermission,
    ScorerRegexCreate,
)
from mlflow_oidc_auth.permissions import NO_PERMISSIONS
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import (
    effective_experiment_permission,
    effective_prompt_permission,
    effective_registered_model_permission,
    fetch_all_prompts,
    fetch_all_registered_models,
    get_is_admin,
    get_username,
)

from ._prefix import USER_PERMISSIONS_ROUTER_PREFIX

logger = get_logger()

USER_EXPERIMENT_PERMISSION = "/{username}/experiments"
USER_EXPERIMENT_PERMISSION_DETAIL = "/{username}/experiments/{experiment_id}"
USER_EXPERIMENT_PATTERN_PERMISSIONS = "/{username}/experiment-patterns"
USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL = "/{username}/experiment-patterns/{pattern_id}"
USER_REGISTERED_MODEL_PERMISSIONS = "/{username}/registered-models"
USER_REGISTERED_MODEL_PERMISSION_DETAIL = "/{username}/registered-models/{name}"
USER_REGISTERED_MODEL_PATTERN_PERMISSIONS = "/{username}/registered-models-patterns"
USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL = "/{username}/registered-models-patterns/{pattern_id}"
USER_PROMPT_PERMISSIONS = "/{username}/prompts"
USER_PROMPT_PERMISSION_DETAIL = "/{username}/prompts/{name}"
USER_PROMPT_PATTERN_PERMISSIONS = "/{username}/prompts-patterns"
USER_PROMPT_PATTERN_PERMISSION_DETAIL = "/{username}/prompts-patterns/{pattern_id}"

USER_SCORER_PERMISSIONS = "/{username}/scorers"
USER_SCORER_PERMISSION_DETAIL = "/{username}/scorers/{experiment_id}/{scorer_name}"
USER_SCORER_PATTERN_PERMISSIONS = "/{username}/scorer-patterns"
USER_SCORER_PATTERN_PERMISSION_DETAIL = "/{username}/scorer-patterns/{pattern_id}"

user_permissions_router = APIRouter(
    prefix=USER_PERMISSIONS_ROUTER_PREFIX,
    tags=["user permissions"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)




@user_permissions_router.get(
    USER_EXPERIMENT_PERMISSION,
    response_model=List[ExperimentPermissionSummary],
    summary="Get experiment permissions for a user",
    description="Retrieves a list of experiments with permission information for the specified user.",
)
async def get_user_experiment_permissions(
    username: str = Path(..., description="The username to get permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[ExperimentPermissionSummary]:
    """
    Retrieve a list of experiments with permission information for a user.

    This endpoint returns experiments that are accessible to the specified user,
    filtered based on the requesting user's permissions. If the requesting user
    is an admin, all experiments are returned. If requesting their own permissions,
    users see all experiments they have access to. Otherwise, only experiments the
    current user can manage are shown.

    Parameters:
    -----------
    username : str
        The username to get experiment permissions for.
    request : Request
        The FastAPI request object.

    Returns:
    --------
    List[ExperimentPermissionSummary]
        A list of experiments with permission information.

    Raises:
    -------
    HTTPException
        If the user is not found or the requesting user lacks sufficient permissions.
    """
    tracking_store = _get_tracking_store()
    all_experiments = tracking_store.search_experiments()

    # Determine which experiments to include based on permissions
    if is_admin:
        # Admins can see all experiments
        list_experiments = all_experiments
    elif current_username == username:
        # Users can see their own accessible experiments
        list_experiments = [
            exp for exp in all_experiments if effective_experiment_permission(exp.experiment_id, username).permission.name != NO_PERMISSIONS.name
        ]
    else:
        # For other users, only show experiments the current user can manage
        list_experiments = [exp for exp in all_experiments if effective_experiment_permission(exp.experiment_id, current_username).permission.can_manage]

    # Format experiment information with permissions
    return [
        ExperimentPermissionSummary(
            name=tracking_store.get_experiment(exp.experiment_id).name,
            id=exp.experiment_id,
            permission=(perm := effective_experiment_permission(exp.experiment_id, username)).permission.name,
            type=perm.type,
        )
        for exp in list_experiments
    ]


@user_permissions_router.post(USER_EXPERIMENT_PERMISSION_DETAIL)
async def create_user_experiment_permission(
    username: str = Path(..., description="The username to grant permissions to"),
    experiment_id: str = Path(..., description="The experiment ID to set permissions for"),
    permission_data: ExperimentPermission = Body(..., description="The permission level to grant"),
    _: None = Depends(check_experiment_manage_permission),
) -> JSONResponse:
    store.create_experiment_permission(
        experiment_id,
        username,
        permission_data.permission,
    )
    return JSONResponse(content={"message": "Experiment permission has been created."})


@user_permissions_router.get(USER_EXPERIMENT_PERMISSION_DETAIL)
async def get_user_experiment_permission(
    username: str = Path(..., description="The username to grant permissions to"),
    experiment_id: str = Path(..., description="The experiment ID to set permissions for"),
    _: None = Depends(check_experiment_manage_permission),
):
    ep = store.get_experiment_permission(experiment_id, username)
    return JSONResponse(content={"experiment_permission": ep.to_json()})


@user_permissions_router.patch(USER_EXPERIMENT_PERMISSION_DETAIL)
async def update_user_experiment_permission(
    username: str = Path(..., description="The username to grant permissions to"),
    experiment_id: str = Path(..., description="The experiment ID to set permissions for"),
    permission_data: ExperimentPermission = Body(..., description="The permission level to grant"),
    _: None = Depends(check_experiment_manage_permission),
):
    store.update_experiment_permission(
        experiment_id,
        username,
        permission_data.permission,
    )
    return JSONResponse(content={"message": "Experiment permission has been changed."})


@user_permissions_router.delete(USER_EXPERIMENT_PERMISSION_DETAIL)
async def delete_user_experiment_permission(
    username: str = Path(..., description="The username to revoke permissions from"),
    experiment_id: str = Path(..., description="The experiment ID to revoke permissions for"),
    _: None = Depends(check_experiment_manage_permission),
):
    store.delete_experiment_permission(experiment_id, username)
    return JSONResponse(content={"message": "Experiment permission has been deleted."})


@user_permissions_router.post(
    USER_EXPERIMENT_PATTERN_PERMISSIONS,
    status_code=201,
    summary="Create experiment pattern permission",
    description="Creates a new regex-based permission pattern for experiment access.",
)
async def create_user_experiment_pattern_permission(
    username: str = Path(..., description="The username to create pattern permission for"),
    pattern_data: ExperimentRegexCreate = Body(..., description="The regex pattern permission details"),
    _: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Create a new regex-based permission pattern for experiment access.

    This endpoint allows administrators to define regex patterns that automatically
    grant specific permission levels to a user for experiments matching the pattern.
    Patterns are evaluated based on priority (lower numbers = higher priority).

    Parameters:
    -----------
    username : str
        The username to create the pattern permission for.
    pattern_data : ExperimentRegexCreate
        The regex pattern details including the pattern, priority, and permission level.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        A response indicating success.

    Raises:
    -------
    HTTPException
        If there's an error creating the permission pattern.
    """
    try:
        store.create_experiment_regex_permission(
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
            username=username,
        )
        return JSONResponse(content={"status": "success", "message": f"Experiment pattern permission created for {username}"}, status_code=201)
    except Exception as e:
        logger.error(f"Error creating experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create experiment pattern permission")


@user_permissions_router.get(
    USER_EXPERIMENT_PATTERN_PERMISSIONS,
    response_model=List[ExperimentRegexPermission],
    summary="List experiment pattern permissions for a user",
    description="Retrieves a list of regex-based experiment permission patterns for the specified user.",
)
async def list_user_experiment_pattern_permissions(
    username: str = Path(..., description="The username to list pattern permissions for"), admin_username: str = Depends(check_admin_permission)
) -> List[ExperimentRegexPermission]:
    """
    List all regex-based experiment permission patterns for a user.

    This endpoint returns all regex patterns that define experiment permissions
    for the specified user. Only administrators can access this information.

    Parameters:
    -----------
    username : str
        The username to list regex permissions for.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    List[ExperimentRegexPermission]
        A list of experiment regex permissions for the user.

    Raises:
    -------
    HTTPException
        If there's an error retrieving the permissions.
    """
    try:
        permissions = store.list_experiment_regex_permissions(username=username)
        return [
            ExperimentRegexPermission(pattern_id=str(perm.id), regex=perm.regex, priority=perm.priority, permission=perm.permission) for perm in permissions
        ]
    except Exception as e:
        logger.error(f"Error listing experiment pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve experiment pattern permissions")


@user_permissions_router.get(
    USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    response_model=ExperimentRegexPermission,
    summary="Get experiment pattern permission for a user",
    description="Retrieves a specific regex-based experiment permission pattern for the specified user.",
)
async def get_user_experiment_pattern_permission(
    username: str = Path(..., description="The username to get pattern permission for"),
    pattern_id: str = Path(..., description="The pattern ID to retrieve"),
    admin_username: str = Depends(check_admin_permission),
) -> ExperimentRegexPermission:
    """
    Get a specific regex-based experiment permission pattern for a user.

    Parameters:
    -----------
    username : str
        The username to get the regex permission for.
    pattern_id : str
        The unique identifier of the pattern to retrieve.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    ExperimentRegexPermission
        The experiment regex permission details.

    Raises:
    -------
    HTTPException
        If the pattern is not found or there's an error retrieving it.
    """
    try:
        permission = store.get_experiment_regex_permission(username, int(pattern_id))
        return ExperimentRegexPermission(pattern_id=str(permission.id), regex=permission.regex, priority=permission.priority, permission=permission.permission)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error getting experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Experiment pattern permission not found")


@user_permissions_router.patch(
    USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    summary="Update experiment pattern permission for a user",
    description="Updates a specific regex-based experiment permission pattern for the specified user.",
)
async def update_user_experiment_pattern_permission(
    username: str = Path(..., description="The username to update pattern permission for"),
    pattern_id: str = Path(..., description="The pattern ID to update"),
    pattern_data: ExperimentRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Update a specific regex-based experiment permission pattern for a user.

    Parameters:
    -----------
    username : str
        The username to update the regex permission for.
    pattern_id : str
        The unique identifier of the pattern to update.
    pattern_data : ExperimentRegexCreate
        The updated regex pattern details.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        A response indicating success.

    Raises:
    -------
    HTTPException
        If the pattern is not found or there's an error updating it.
    """
    try:
        store.update_experiment_regex_permission(
            id=int(pattern_id), regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission, username=username
        )
        return JSONResponse(content={"status": "success", "message": f"Experiment pattern permission updated for {username}"})
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error updating experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update experiment pattern permission")


@user_permissions_router.delete(
    USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    summary="Delete experiment pattern permission for a user",
    description="Deletes a specific regex-based experiment permission pattern for the specified user.",
)
async def delete_user_experiment_pattern_permission(
    username: str = Path(..., description="The username to delete pattern permission for"),
    pattern_id: str = Path(..., description="The pattern ID to delete"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Delete a specific regex-based experiment permission pattern for a user.

    Parameters:
    -----------
    username : str
        The username to delete the regex permission for.
    pattern_id : str
        The unique identifier of the pattern to delete.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        A response indicating success.

    Raises:
    -------
    HTTPException
        If the pattern is not found or there's an error deleting it.
    """
    try:
        store.delete_experiment_regex_permission(username, int(pattern_id))
        return JSONResponse(content={"status": "success", "message": f"Experiment pattern permission deleted for {username}"})
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error deleting experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete experiment pattern permission")


@user_permissions_router.get(
    USER_PROMPT_PERMISSIONS,
    summary="List prompt permissions for a user",
    description="Retrieves a list of prompts with permission information for the specified user.",
)
async def get_user_prompts(
    username: str = Path(..., description="The username to get prompt permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
    """
    List prompt permissions for a user.

    This endpoint returns prompts that are accessible to the specified user,
    filtered based on the requesting user's permissions.

    Parameters:
    -----------
    username : str
        The username to get prompt permissions for.
    request : Request
        The FastAPI request object.

    Returns:
    --------
    JSONResponse
        A list of prompts with permission information.

    Raises:
    -------
    HTTPException
        If there's an error retrieving the permissions.
    """
    # Get all prompts and filter based on permissions
    prompts = fetch_all_prompts()

    if is_admin:
        list_prompts = prompts
    elif current_username == username:
        list_prompts = [prompt for prompt in prompts if effective_prompt_permission(prompt.name, username).permission.name != "NO_PERMISSIONS"]
    else:
        list_prompts = [prompt for prompt in prompts if effective_prompt_permission(prompt.name, current_username).permission.can_manage]

    formatted_prompts = [
        {"name": prompt.name, "permission": (perm := effective_prompt_permission(prompt.name, username)).permission.name, "type": perm.type}
        for prompt in list_prompts
    ]

    return JSONResponse(content=formatted_prompts)


@user_permissions_router.post(
    USER_PROMPT_PERMISSION_DETAIL,
    status_code=201,
    summary="Create prompt permission for a user",
    description="Creates a new permission for a user to access a specific prompt.",
)
async def create_user_prompt_permission(
    username: str = Path(..., description="The username to grant prompt permission to"),
    name: str = Path(..., description="The prompt name to set permissions for"),
    permission_data: PromptPermission = Body(..., description="The permission details"),
    _: str = Depends(check_registered_model_manage_permission),
) -> JSONResponse:
    """
    Create a permission for a user to access a prompt.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to grant permissions to.
    name : str
        The name of the prompt to grant permissions for.
    permission_data : PromptPermission
        The permission data containing the permission level.

    Returns:
    --------
    JSONResponse
        A response indicating success.
    """
    try:
        store.create_registered_model_permission(
            name=name,
            username=username,
            permission=permission_data.permission,
        )
        return JSONResponse(content={"status": "success", "message": f"Prompt permission created for {username} on {name}"}, status_code=201)
    except MlflowException as e:
        logger.error(f"Error creating prompt permission: {str(e)}")
        if getattr(e, "error_code", None) == RESOURCE_ALREADY_EXISTS:
            raise HTTPException(status_code=409, detail="Prompt permission already exists")
        if getattr(e, "error_code", None) == INVALID_PARAMETER_VALUE:
            raise HTTPException(status_code=400, detail=str(e))
        raise
    except Exception as e:
        logger.error(f"Error creating prompt permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create prompt permission")


@user_permissions_router.get(
    USER_PROMPT_PERMISSION_DETAIL, summary="Get prompt permission for a user", description="Retrieves the permission for a user on a specific prompt."
)
async def get_user_prompt_permission(
    username: str = Path(..., description="The username to get prompt permission for"),
    name: str = Path(..., description="The prompt name to get permissions for"),
    _: str = Depends(check_registered_model_manage_permission),
) -> JSONResponse:
    """
    Get the permission for a user on a prompt.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to get permissions for.
    name : str
        The name of the prompt to get permissions for.

    Returns:
    --------
    JSONResponse
        A response containing the prompt permission details.
    """
    try:
        rmp = store.get_registered_model_permission(name, username)
        return JSONResponse(content={"prompt_permission": rmp.to_json()})
    except Exception as e:
        logger.error(f"Error getting prompt permission: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Prompt permission not found")


@user_permissions_router.patch(
    USER_PROMPT_PERMISSION_DETAIL, summary="Update prompt permission for a user", description="Updates the permission for a user on a specific prompt."
)
async def update_user_prompt_permission(
    username: str = Path(..., description="The username to update prompt permission for"),
    name: str = Path(..., description="The prompt name to update permissions for"),
    permission_data: PromptPermission = Body(..., description="Updated permission details"),
    _: str = Depends(check_registered_model_manage_permission),
) -> JSONResponse:
    """
    Update the permission for a user on a prompt.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to update permissions for.
    name : str
        The name of the prompt to update permissions for.
    permission_data : PromptPermission
        The updated permission data.
    Returns:
    --------
    JSONResponse
        A response indicating success.
    """
    try:
        store.update_registered_model_permission(
            name=name,
            username=username,
            permission=permission_data.permission,
        )
        return JSONResponse(content={"status": "success", "message": f"Prompt permission updated for {username} on {name}"})
    except MlflowException as e:
        logger.error(f"Error updating prompt permission: {str(e)}")
        if getattr(e, "error_code", None) == RESOURCE_DOES_NOT_EXIST:
            raise HTTPException(status_code=404, detail="Prompt permission does not exist")
        if getattr(e, "error_code", None) == INVALID_PARAMETER_VALUE:
            raise HTTPException(status_code=400, detail=str(e))
        raise
    except Exception as e:
        logger.error(f"Error updating prompt permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update prompt permission")


@user_permissions_router.delete(
    USER_PROMPT_PERMISSION_DETAIL, summary="Delete prompt permission for a user", description="Deletes the permission for a user on a specific prompt."
)
async def delete_user_prompt_permission(
    username: str = Path(..., description="The username to delete prompt permission for"),
    name: str = Path(..., description="The prompt name to delete permissions for"),
    _: str = Depends(check_registered_model_manage_permission),
) -> JSONResponse:
    """
    Delete the permission for a user on a prompt.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to delete permissions for.
    name : str
        The name of the prompt to delete permissions for.

    Returns:
    --------
    JSONResponse
        A response indicating success.
    """
    try:
        store.delete_registered_model_permission(name, username)
        return JSONResponse(content={"status": "success", "message": f"Prompt permission deleted for {username} on {name}"})
    except Exception as e:
        logger.error(f"Error deleting prompt permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete prompt permission")


@user_permissions_router.get(
    USER_PROMPT_PATTERN_PERMISSIONS,
    summary="List prompt pattern permissions for a user",
    description="Retrieves a list of regex-based prompt permission patterns for the specified user.",
)
async def get_user_prompt_pattern_permissions(
    username: str = Path(..., description="The username to list prompt pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    List all regex-based prompt permission patterns for a user.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to list regex permissions for.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        A list of prompt regex permissions for the user.
    """
    try:
        rm = store.list_prompt_regex_permissions(username=username)
        return JSONResponse(content=[r.to_json() for r in rm], status_code=200)
    except Exception as e:
        logger.error(f"Error listing prompt pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve prompt pattern permissions")


@user_permissions_router.post(
    USER_PROMPT_PATTERN_PERMISSIONS,
    status_code=201,
    summary="Create prompt pattern permission for a user",
    description="Creates a new regex-based permission pattern for prompt access.",
)
async def create_user_prompt_regex_permission(
    username: str = Path(..., description="The username to create prompt pattern permission for"),
    pattern_data: PromptRegexCreate = Body(..., description="The regex pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Create a new regex-based permission pattern for prompt access.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to create the pattern permission for.
    pattern_data : PromptRegexCreate
        The regex pattern details including the pattern, priority, and permission level.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        A response indicating success.
    """
    try:
        store.create_prompt_regex_permission(
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
            username=username,
        )
        return JSONResponse(content={"status": "success", "message": f"Prompt pattern permission created for {username}"}, status_code=201)
    except Exception as e:
        logger.error(f"Error creating prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create prompt pattern permission")


@user_permissions_router.get(
    USER_PROMPT_PATTERN_PERMISSION_DETAIL,
    summary="Get prompt pattern permission for a user",
    description="Retrieves a specific regex-based prompt permission pattern for the specified user.",
)
async def get_user_prompt_regex_permission(
    username: str = Path(..., description="The username to get prompt pattern permission for"),
    pattern_id: str = Path(..., description="The pattern ID to retrieve"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Get a specific regex-based prompt permission pattern for a user.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to get the regex permission for.
    pattern_id : str
        The unique identifier of the pattern to retrieve.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        The prompt regex permission details.
    """
    try:
        rm = store.get_prompt_regex_permission(id=int(pattern_id), username=username)
        return JSONResponse(content={"prompt_permission": rm.to_json()}, status_code=200)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error getting prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Prompt pattern permission not found")


@user_permissions_router.patch(
    USER_PROMPT_PATTERN_PERMISSION_DETAIL,
    summary="Update prompt pattern permission for a user",
    description="Updates a specific regex-based prompt permission pattern for the specified user.",
)
async def update_user_prompt_regex_permission(
    username: str = Path(..., description="The username to update prompt pattern permission for"),
    pattern_id: str = Path(..., description="The pattern ID to update"),
    pattern_data: PromptRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Update a specific regex-based prompt permission pattern for a user.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to update the regex permission for.
    pattern_id : str
        The unique identifier of the pattern to update.
    pattern_data : PromptRegexCreate
        The updated regex pattern details.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        The updated prompt regex permission details.
    """
    try:
        rm = store.update_prompt_regex_permission(
            id=int(pattern_id),
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
            username=username,
        )
        return JSONResponse(content={"prompt_permission": rm.to_json()}, status_code=200)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error updating prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update prompt pattern permission")


@user_permissions_router.delete(
    USER_PROMPT_PATTERN_PERMISSION_DETAIL,
    summary="Delete prompt pattern permission for a user",
    description="Deletes a specific regex-based prompt permission pattern for the specified user.",
)
async def delete_user_prompt_regex_permission(
    username: str = Path(..., description="The username to delete prompt pattern permission for"),
    pattern_id: str = Path(..., description="The pattern ID to delete"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Delete a specific regex-based prompt permission pattern for a user.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to delete the regex permission for.
    pattern_id : str
        The unique identifier of the pattern to delete.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        A response indicating success.
    """
    try:
        store.delete_prompt_regex_permission(id=int(pattern_id), username=username)
        return JSONResponse(content={"status": "success"}, status_code=200)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error deleting prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete prompt pattern permission")


@user_permissions_router.get(
    USER_REGISTERED_MODEL_PERMISSIONS,
    summary="List registered model permissions for a user",
    description="Retrieves a list of registered models with permission information for the specified user.",
)
async def get_user_registered_models(
    username: str = Path(..., description="The username to get registered model permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
    """
    List registered model permissions for a user.

    This endpoint returns registered models that are accessible to the specified user,
    filtered based on the requesting user's permissions.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to get registered model permissions for.

    Returns:
    --------
    JSONResponse
        A list of registered models with permission information.
    """

    # Get all registered models and filter based on permissions
    models = fetch_all_registered_models()

    if is_admin:
        list_models = models
    elif current_username == username:
        list_models = [model for model in models if effective_registered_model_permission(model.name, username).permission.name != "NO_PERMISSIONS"]
    else:
        list_models = [model for model in models if effective_registered_model_permission(model.name, current_username).permission.can_manage]

    formatted_models = [
        {"name": model.name, "permission": (perm := effective_registered_model_permission(model.name, username)).permission.name, "type": perm.type}
        for model in list_models
    ]

    return JSONResponse(content=formatted_models)


@user_permissions_router.post(
    USER_REGISTERED_MODEL_PERMISSION_DETAIL,
    status_code=201,
    summary="Create registered model permission for a user",
    description="Creates a new permission for a user to access a specific registered model.",
)
async def create_user_registered_model_permission(
    username: str = Path(..., description="The username to grant registered model permission to"),
    name: str = Path(..., description="The registered model name to set permissions for"),
    permission_data: RegisteredModelPermission = Body(..., description="The permission details"),
    _: str = Depends(check_registered_model_manage_permission),
) -> JSONResponse:
    """
    Create a permission for a user to access a registered model.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to grant permissions to.
    name : str
        The name of the registered model to grant permissions for.
    permission_data : RegisteredModelPermission
        The permission data containing the permission level.
    Returns:
    --------
    JSONResponse
        A response indicating success.
    """
    try:
        store.create_registered_model_permission(
            name=name,
            username=username,
            permission=permission_data.permission,
        )
        return JSONResponse(content={"status": "success", "message": f"Registered model permission created for {username} on {name}"}, status_code=201)
    except MlflowException as e:
        logger.error(f"Error creating registered model permission: {str(e)}")
        if getattr(e, "error_code", None) == RESOURCE_ALREADY_EXISTS:
            raise HTTPException(status_code=409, detail="Registered model permission already exists")
        if getattr(e, "error_code", None) == INVALID_PARAMETER_VALUE:
            raise HTTPException(status_code=400, detail=str(e))
        raise
    except Exception as e:
        logger.error(f"Error creating registered model permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create registered model permission")


@user_permissions_router.get(
    USER_REGISTERED_MODEL_PERMISSION_DETAIL,
    summary="Get registered model permission for a user",
    description="Retrieves the permission for a user on a specific registered model.",
)
async def get_user_registered_model_permission(
    username: str = Path(..., description="The username to get registered model permission for"),
    name: str = Path(..., description="The registered model name to get permissions for"),
    _: str = Depends(check_registered_model_manage_permission),
) -> JSONResponse:
    """
    Get the permission for a user on a registered model.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to get permissions for.
    name : str
        The name of the registered model to get permissions for.

    Returns:
    --------
    JSONResponse
        A response containing the registered model permission details.
    """
    try:
        rmp = store.get_registered_model_permission(name, username)
        return JSONResponse(content={"registered_model_permission": rmp.to_json()})
    except Exception as e:
        logger.error(f"Error getting registered model permission: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Registered model permission not found")


@user_permissions_router.patch(
    USER_REGISTERED_MODEL_PERMISSION_DETAIL,
    summary="Update registered model permission for a user",
    description="Updates the permission for a user on a specific registered model.",
)
async def update_user_registered_model_permission(
    username: str = Path(..., description="The username to update registered model permission for"),
    name: str = Path(..., description="The registered model name to update permissions for"),
    permission_data: RegisteredModelPermission = Body(..., description="Updated permission details"),
    _: str = Depends(check_registered_model_manage_permission),
) -> JSONResponse:
    """
    Update the permission for a user on a registered model.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to update permissions for.
    name : str
        The name of the registered model to update permissions for.
    permission_data : RegisteredModelPermission
        The updated permission data.


    Returns:
    --------
    JSONResponse
        A response indicating success.
    """
    try:
        store.update_registered_model_permission(
            name=name,
            username=username,
            permission=permission_data.permission,
        )
        return JSONResponse(content={"status": "success", "message": f"Registered model permission updated for {username} on {name}"})
    except MlflowException as e:
        logger.error(f"Error updating registered model permission: {str(e)}")
        if getattr(e, "error_code", None) == RESOURCE_DOES_NOT_EXIST:
            raise HTTPException(status_code=404, detail="Registered model permission does not exist")
        if getattr(e, "error_code", None) == INVALID_PARAMETER_VALUE:
            raise HTTPException(status_code=400, detail=str(e))
        raise
    except Exception as e:
        logger.error(f"Error updating registered model permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update registered model permission")


@user_permissions_router.delete(
    USER_REGISTERED_MODEL_PERMISSION_DETAIL,
    summary="Delete registered model permission for a user",
    description="Deletes the permission for a user on a specific registered model.",
)
async def delete_user_registered_model_permission(
    username: str = Path(..., description="The username to delete registered model permission for"),
    name: str = Path(..., description="The registered model name to delete permissions for"),
    _: str = Depends(check_registered_model_manage_permission),
) -> JSONResponse:
    """
    Delete the permission for a user on a registered model.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to delete permissions for.
    name : str
        The name of the registered model to delete permissions for.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        A response indicating success.
    """
    try:
        store.delete_registered_model_permission(name, username)
        return JSONResponse(content={"status": "success", "message": f"Registered model permission deleted for {username} on {name}"})
    except Exception as e:
        logger.error(f"Error deleting registered model permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete registered model permission")


@user_permissions_router.get(
    USER_SCORER_PERMISSIONS,
    summary="List scorer permissions for a user",
    description="Retrieves a list of scorers with permission information for the specified user.",
)
async def get_user_scorer_permissions(
    username: str = Path(..., description="The username to get scorer permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> JSONResponse:
    """List scorer permissions for a user.

    Admins can see all scorer permissions for any user. Users can see their own.
    For other users, only include scorers in experiments the current user can manage.
    """
    try:
        perms = store.list_scorer_permissions(username=username)
        if is_admin or current_username == username:
            filtered = perms
        else:
            filtered = [sp for sp in perms if effective_experiment_permission(sp.experiment_id, current_username).permission.can_manage]
        return JSONResponse(content=[p.to_json() for p in filtered], status_code=200)
    except Exception as e:
        logger.error(f"Error listing scorer permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve scorer permissions")


@user_permissions_router.post(
    USER_SCORER_PERMISSION_DETAIL,
    status_code=201,
    summary="Create scorer permission for a user",
    description="Creates a new permission for a user to access a specific scorer.",
)
async def create_user_scorer_permission(
    username: str = Path(..., description="The username to grant scorer permission to"),
    experiment_id: str = Path(..., description="The experiment ID owning the scorer"),
    scorer_name: str = Path(..., description="The scorer name"),
    permission_data: ScorerPermission = Body(..., description="The permission details"),
    _: None = Depends(check_experiment_manage_permission),
) -> JSONResponse:
    """Create a scorer permission for a user.

    We require MANAGE on the owning experiment to grant/revoke scorer permissions.
    """
    try:
        sp = store.create_scorer_permission(
            experiment_id=str(experiment_id),
            scorer_name=str(scorer_name),
            username=str(username),
            permission=str(permission_data.permission),
        )
        return JSONResponse(content={"scorer_permission": sp.to_json()}, status_code=201)
    except MlflowException as e:
        logger.error(f"Error creating scorer permission: {str(e)}")
        if getattr(e, "error_code", None) == RESOURCE_ALREADY_EXISTS:
            raise HTTPException(status_code=409, detail="Scorer permission already exists")
        if getattr(e, "error_code", None) == INVALID_PARAMETER_VALUE:
            raise HTTPException(status_code=400, detail=str(e))
        raise
    except Exception as e:
        logger.error(f"Error creating scorer permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create scorer permission")


@user_permissions_router.get(
    USER_SCORER_PERMISSION_DETAIL,
    summary="Get scorer permission for a user",
    description="Retrieves the permission for a user on a specific scorer.",
)
async def get_user_scorer_permission(
    username: str = Path(..., description="The username to get scorer permission for"),
    experiment_id: str = Path(..., description="The experiment ID owning the scorer"),
    scorer_name: str = Path(..., description="The scorer name"),
    _: None = Depends(check_experiment_manage_permission),
) -> JSONResponse:
    try:
        sp = store.get_scorer_permission(str(experiment_id), str(scorer_name), str(username))
        return JSONResponse(content={"scorer_permission": sp.to_json()})
    except Exception as e:
        logger.error(f"Error getting scorer permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Scorer permission not found")


@user_permissions_router.patch(
    USER_SCORER_PERMISSION_DETAIL,
    summary="Update scorer permission for a user",
    description="Updates the permission for a user on a specific scorer.",
)
async def update_user_scorer_permission(
    username: str = Path(..., description="The username to update scorer permission for"),
    experiment_id: str = Path(..., description="The experiment ID owning the scorer"),
    scorer_name: str = Path(..., description="The scorer name"),
    permission_data: ScorerPermission = Body(..., description="Updated permission details"),
    _: None = Depends(check_experiment_manage_permission),
) -> JSONResponse:
    try:
        store.update_scorer_permission(
            experiment_id=str(experiment_id),
            scorer_name=str(scorer_name),
            username=str(username),
            permission=str(permission_data.permission),
        )
        return JSONResponse(content={"status": "success", "message": f"Scorer permission updated for {username} on {scorer_name}"})
    except MlflowException as e:
        logger.error(f"Error updating scorer permission: {str(e)}")
        if getattr(e, "error_code", None) == RESOURCE_DOES_NOT_EXIST:
            raise HTTPException(status_code=404, detail="Scorer permission does not exist")
        if getattr(e, "error_code", None) == INVALID_PARAMETER_VALUE:
            raise HTTPException(status_code=400, detail=str(e))
        raise
    except Exception as e:
        logger.error(f"Error updating scorer permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update scorer permission")


@user_permissions_router.delete(
    USER_SCORER_PERMISSION_DETAIL,
    summary="Delete scorer permission for a user",
    description="Deletes the permission for a user on a specific scorer.",
)
async def delete_user_scorer_permission(
    username: str = Path(..., description="The username to delete scorer permission for"),
    experiment_id: str = Path(..., description="The experiment ID owning the scorer"),
    scorer_name: str = Path(..., description="The scorer name"),
    _: None = Depends(check_experiment_manage_permission),
) -> JSONResponse:
    try:
        store.delete_scorer_permission(str(experiment_id), str(scorer_name), str(username))
        return JSONResponse(content={"status": "success", "message": f"Scorer permission deleted for {username} on {scorer_name}"})
    except Exception as e:
        logger.error(f"Error deleting scorer permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete scorer permission")


@user_permissions_router.get(
    USER_SCORER_PATTERN_PERMISSIONS,
    summary="List scorer pattern permissions for a user",
    description="Retrieves a list of regex-based scorer permission patterns for the specified user.",
)
async def get_user_scorer_regex_permissions(
    username: str = Path(..., description="The username to list scorer pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    try:
        perms = store.list_scorer_regex_permissions(username=username)
        return JSONResponse(content=[p.to_json() for p in perms], status_code=200)
    except Exception as e:
        logger.error(f"Error listing scorer pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve scorer pattern permissions")


@user_permissions_router.post(
    USER_SCORER_PATTERN_PERMISSIONS,
    status_code=201,
    summary="Create scorer pattern permission for a user",
    description="Creates a new regex-based permission pattern for scorer access.",
)
async def create_user_scorer_regex_permission(
    username: str = Path(..., description="The username to create scorer pattern permission for"),
    pattern_data: ScorerRegexCreate = Body(..., description="The regex pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    try:
        perm = store.create_scorer_regex_permission(
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
            username=username,
        )
        return JSONResponse(content={"pattern": perm.to_json()}, status_code=201)
    except MlflowException as e:
        logger.error(f"Error creating scorer pattern permission: {str(e)}")
        if getattr(e, "error_code", None) == RESOURCE_ALREADY_EXISTS:
            raise HTTPException(status_code=409, detail="Scorer pattern permission already exists")
        if getattr(e, "error_code", None) == INVALID_PARAMETER_VALUE:
            raise HTTPException(status_code=400, detail=str(e))
        raise
    except Exception as e:
        logger.error(f"Error creating scorer pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create scorer pattern permission")


@user_permissions_router.get(
    USER_SCORER_PATTERN_PERMISSION_DETAIL,
    summary="Get specific scorer pattern permission for a user",
    description="Retrieves a specific scorer regex pattern permission for a user.",
)
async def get_user_scorer_pattern_permission(
    username: str = Path(..., description="The username"),
    pattern_id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    try:
        perm = store.get_scorer_regex_permission(username=username, id=pattern_id)
        return JSONResponse(content={"pattern": perm.to_json()})
    except Exception as e:
        logger.error(f"Error getting scorer pattern permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Scorer pattern permission not found")


@user_permissions_router.patch(
    USER_SCORER_PATTERN_PERMISSION_DETAIL,
    summary="Update scorer pattern permission for a user",
    description="Updates a specific scorer regex pattern permission for a user.",
)
async def update_user_scorer_pattern_permission(
    username: str = Path(..., description="The username"),
    pattern_id: int = Path(..., description="The pattern ID"),
    pattern_data: ScorerRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    try:
        perm = store.update_scorer_regex_permission(
            id=pattern_id,
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
            username=username,
        )
        return JSONResponse(content={"pattern": perm.to_json()})
    except Exception as e:
        logger.error(f"Error updating scorer pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update scorer pattern permission")


@user_permissions_router.delete(
    USER_SCORER_PATTERN_PERMISSION_DETAIL,
    summary="Delete scorer pattern permission for a user",
    description="Deletes a specific scorer regex pattern permission for a user.",
)
async def delete_user_scorer_pattern_permission(
    username: str = Path(..., description="The username"),
    pattern_id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    try:
        store.delete_scorer_regex_permission(id=pattern_id, username=username)
        return JSONResponse(content={"status": "success", "message": f"Scorer pattern permission deleted for {username}"})
    except Exception as e:
        logger.error(f"Error deleting scorer pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete scorer pattern permission")


@user_permissions_router.get(
    USER_REGISTERED_MODEL_PATTERN_PERMISSIONS,
    summary="List registered model pattern permissions for a user",
    description="Retrieves a list of regex-based registered model permission patterns for the specified user.",
)
async def get_user_registered_model_regex_permissions(
    username: str = Path(..., description="The username to list registered model pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    List all regex-based registered model permission patterns for a user.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to list regex permissions for.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        A list of registered model regex permissions for the user.
    """
    try:
        rm = store.list_registered_model_regex_permissions(username=username)
        return JSONResponse(content=[r.to_json() for r in rm], status_code=200)
    except Exception as e:
        logger.error(f"Error listing registered model pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve registered model pattern permissions")


@user_permissions_router.post(
    USER_REGISTERED_MODEL_PATTERN_PERMISSIONS,
    status_code=201,
    summary="Create registered model pattern permission for a user",
    description="Creates a new regex-based permission pattern for registered model access.",
)
async def create_user_registered_model_regex_permission(
    username: str = Path(..., description="The username to create registered model pattern permission for"),
    pattern_data: RegisteredModelRegexCreate = Body(..., description="The regex pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Create a new regex-based permission pattern for registered model access.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to create the pattern permission for.
    pattern_data : RegisteredModelRegexCreate
        The regex pattern details including the pattern, priority, and permission level.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        A response indicating success.
    """
    try:
        store.create_registered_model_regex_permission(
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
            username=username,
        )
        return JSONResponse(content={"status": "success", "message": f"Registered model pattern permission created for {username}"}, status_code=201)
    except Exception as e:
        logger.error(f"Error creating registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create registered model pattern permission")


@user_permissions_router.get(
    USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    summary="Get registered model pattern permission for a user",
    description="Retrieves a specific regex-based registered model permission pattern for the specified user.",
)
async def get_user_registered_model_regex_permission(
    username: str = Path(..., description="The username to get registered model pattern permission for"),
    pattern_id: str = Path(..., description="The pattern ID to retrieve"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Get a specific regex-based registered model permission pattern for a user.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to get the regex permission for.
    pattern_id : str
        The unique identifier of the pattern to retrieve.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        The registered model regex permission details.
    """
    try:
        rm = store.get_registered_model_regex_permission(id=int(pattern_id), username=username)
        return JSONResponse(content={"registered_model_permission": rm.to_json()}, status_code=200)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error getting registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Registered model pattern permission not found")


@user_permissions_router.patch(
    USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    summary="Update registered model pattern permission for a user",
    description="Updates a specific regex-based registered model permission pattern for the specified user.",
)
async def update_user_registered_model_regex_permission(
    username: str = Path(..., description="The username to update registered model pattern permission for"),
    pattern_id: str = Path(..., description="The pattern ID to update"),
    pattern_data: RegisteredModelRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Update a specific regex-based registered model permission pattern for a user.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to update the regex permission for.
    pattern_id : str
        The unique identifier of the pattern to update.
    pattern_data : RegisteredModelRegexCreate
        The updated regex pattern details.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        The updated registered model regex permission details.
    """
    try:
        rm = store.update_registered_model_regex_permission(
            id=int(pattern_id),
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
            username=username,
        )
        return JSONResponse(content={"registered_model_permission": rm.to_json()}, status_code=200)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error updating registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update registered model pattern permission")


@user_permissions_router.delete(
    USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    summary="Delete registered model pattern permission for a user",
    description="Deletes a specific regex-based registered model permission pattern for the specified user.",
)
async def delete_user_registered_model_regex_permission(
    username: str = Path(..., description="The username to delete registered model pattern permission for"),
    pattern_id: str = Path(..., description="The pattern ID to delete"),
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Delete a specific regex-based registered model permission pattern for a user.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to delete the regex permission for.
    pattern_id : str
        The unique identifier of the pattern to delete.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        A response indicating success.
    """
    try:
        store.delete_registered_model_regex_permission(id=int(pattern_id), username=username)
        return JSONResponse(content={"status": "success"}, status_code=200)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error deleting registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete registered model pattern permission")
