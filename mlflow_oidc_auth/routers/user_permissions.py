"""
Permissions router for FastAPI application.

This router handles permission management endpoints for experiments, models, and users.
"""

from typing import List

from fastapi import APIRouter, Body, Depends, Path
from fastapi.exceptions import HTTPException
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.dependencies import check_admin_permission, check_experiment_manage_permission, check_registered_model_manage_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import (
    ExperimentPermission,
    ExperimentPermissionRecord,
    ExperimentPermissionResponse,
    ExperimentPermissionSummary,
    ExperimentRegexCreate,
    ExperimentRegexPermission,
    GatewayPermission,
    GatewayRegexCreate,
    MessageResponse,
    NamedPermissionSummary,
    PromptPermission,
    PromptPermissionResponse,
    PromptRegexCreate,
    PromptRegexPermissionResponse,
    RegisteredModelPermission,
    RegisteredModelPermissionRecord,
    RegisteredModelPermissionResponse,
    RegisteredModelRegexCreate,
    RegisteredModelRegexPermissionRecord,
    RegisteredModelRegexPermissionResponse,
    ScorerPermission,
    ScorerPermissionRecord,
    ScorerPermissionResponse,
    ScorerRegexCreate,
    ScorerRegexPermissionRecord,
    ScorerRegexPermissionResponse,
    StatusMessageResponse,
    StatusOnlyResponse,
    UserGatewayRegexPermissionItem,
)
from mlflow_oidc_auth.permissions import NO_PERMISSIONS
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import effective_experiment_permission, fetch_all_prompts, fetch_all_registered_models, get_is_admin, get_username
from mlflow_oidc_auth.utils.batch_permissions import batch_resolve_experiment_permissions, batch_resolve_model_permissions, batch_resolve_prompt_permissions

from ._prefix import USER_PERMISSIONS_ROUTER_PREFIX

logger = get_logger()

USER_EXPERIMENT_PERMISSION = "/{username}/experiments"
USER_EXPERIMENT_PERMISSION_DETAIL = "/{username}/experiments/{experiment_id}"
USER_EXPERIMENT_PATTERN_PERMISSIONS = "/{username}/experiment-patterns"
USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL = "/{username}/experiment-patterns/{id}"

USER_REGISTERED_MODEL_PERMISSIONS = "/{username}/registered-models"
USER_REGISTERED_MODEL_PERMISSION_DETAIL = "/{username}/registered-models/{name:path}"
USER_REGISTERED_MODEL_PATTERN_PERMISSIONS = "/{username}/registered-models-patterns"
USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL = "/{username}/registered-models-patterns/{id}"

USER_PROMPT_PERMISSIONS = "/{username}/prompts"
USER_PROMPT_PERMISSION_DETAIL = "/{username}/prompts/{name:path}"
USER_PROMPT_PATTERN_PERMISSIONS = "/{username}/prompts-patterns"
USER_PROMPT_PATTERN_PERMISSION_DETAIL = "/{username}/prompts-patterns/{id}"

USER_SCORER_PERMISSIONS = "/{username}/scorers"
USER_SCORER_PERMISSION_DETAIL = "/{username}/scorers/{experiment_id}/{scorer_name:path}"
USER_SCORER_PATTERN_PERMISSIONS = "/{username}/scorer-patterns"
USER_SCORER_PATTERN_PERMISSION_DETAIL = "/{username}/scorer-patterns/{id}"

USER_GATEWAY_ENDPOINT_PERMISSIONS = "/{username}/gateways/endpoints"
USER_GATEWAY_ENDPOINT_PERMISSION_DETAIL = "/{username}/gateways/endpoints/{name:path}"
USER_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS = "/{username}/gateways/endpoints-patterns"
USER_GATEWAY_ENDPOINT_PATTERN_PERMISSION_DETAIL = "/{username}/gateways/endpoints-patterns/{id}"

USER_GATEWAY_MODEL_DEFINITION_PERMISSIONS = "/{username}/gateways/model-definitions"
USER_GATEWAY_MODEL_DEFINITION_PERMISSION_DETAIL = "/{username}/gateways/model-definitions/{name:path}"
USER_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSIONS = "/{username}/gateways/model-definitions-patterns"
USER_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSION_DETAIL = "/{username}/gateways/model-definitions-patterns/{id}"

USER_GATEWAY_SECRET_PERMISSIONS = "/{username}/gateways/secrets"
USER_GATEWAY_SECRET_PERMISSION_DETAIL = "/{username}/gateways/secrets/{name:path}"
USER_GATEWAY_SECRET_PATTERN_PERMISSIONS = "/{username}/gateways/secrets-patterns"
USER_GATEWAY_SECRET_PATTERN_PERMISSION_DETAIL = "/{username}/gateways/secrets-patterns/{id}"

user_permissions_router = APIRouter(
    prefix=USER_PERMISSIONS_ROUTER_PREFIX,
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
    tags=["user experiment permissions"],
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

    # Batch resolve permissions for all experiments (fixed number of DB queries)
    experiment_permissions = batch_resolve_experiment_permissions(username, all_experiments)

    # Determine which experiments to include based on permissions
    if is_admin:
        # Admins can see all experiments
        list_experiments = all_experiments
    elif current_username == username:
        # Users can see their own accessible experiments (filter using pre-computed permissions)
        list_experiments = [exp for exp in all_experiments if experiment_permissions[exp.experiment_id].permission.name != NO_PERMISSIONS.name]
    else:
        # For other users, only show experiments the current user can manage
        current_user_permissions = batch_resolve_experiment_permissions(current_username, all_experiments)
        list_experiments = [exp for exp in all_experiments if current_user_permissions[exp.experiment_id].permission.can_manage]

    # Format experiment information with permissions (reuse pre-computed permissions)
    return [
        ExperimentPermissionSummary(
            name=exp.name,
            id=exp.experiment_id,
            permission=experiment_permissions[exp.experiment_id].permission.name,
            kind=experiment_permissions[exp.experiment_id].kind,
        )
        for exp in list_experiments
    ]


@user_permissions_router.post(
    USER_EXPERIMENT_PERMISSION_DETAIL,
    response_model=MessageResponse,
    summary="Create experiment permission for a user",
    description="Creates a permission for a user to access a specific experiment.",
    tags=["user experiment permissions"],
)
async def create_user_experiment_permission(
    username: str = Path(..., description="The username to grant permissions to"),
    experiment_id: str = Path(..., description="The experiment ID to set permissions for"),
    permission_data: ExperimentPermission = Body(..., description="The permission level to grant"),
    _: None = Depends(check_experiment_manage_permission),
) -> MessageResponse:
    store.create_experiment_permission(
        experiment_id,
        username,
        permission_data.permission,
    )
    return MessageResponse(message="Experiment permission has been created.")


@user_permissions_router.get(
    USER_EXPERIMENT_PERMISSION_DETAIL,
    response_model=ExperimentPermissionResponse,
    summary="Get experiment permission for a user",
    description="Retrieves the permission for a user on a specific experiment.",
    tags=["user experiment permissions"],
)
async def get_user_experiment_permission(
    username: str = Path(..., description="The username to grant permissions to"),
    experiment_id: str = Path(..., description="The experiment ID to set permissions for"),
    _: None = Depends(check_experiment_manage_permission),
) -> ExperimentPermissionResponse:
    ep = store.get_experiment_permission(experiment_id, username)
    return ExperimentPermissionResponse(experiment_permission=ExperimentPermissionRecord(**ep.to_json()))


@user_permissions_router.patch(
    USER_EXPERIMENT_PERMISSION_DETAIL,
    response_model=MessageResponse,
    summary="Update experiment permission for a user",
    description="Updates the permission for a user on a specific experiment.",
    tags=["user experiment permissions"],
)
async def update_user_experiment_permission(
    username: str = Path(..., description="The username to grant permissions to"),
    experiment_id: str = Path(..., description="The experiment ID to set permissions for"),
    permission_data: ExperimentPermission = Body(..., description="The permission level to grant"),
    _: None = Depends(check_experiment_manage_permission),
) -> MessageResponse:
    store.update_experiment_permission(
        experiment_id,
        username,
        permission_data.permission,
    )
    return MessageResponse(message="Experiment permission has been changed.")


@user_permissions_router.delete(
    USER_EXPERIMENT_PERMISSION_DETAIL,
    response_model=MessageResponse,
    summary="Delete experiment permission for a user",
    description="Deletes the permission for a user on a specific experiment.",
    tags=["user experiment permissions"],
)
async def delete_user_experiment_permission(
    username: str = Path(..., description="The username to revoke permissions from"),
    experiment_id: str = Path(..., description="The experiment ID to revoke permissions for"),
    _: None = Depends(check_experiment_manage_permission),
) -> MessageResponse:
    store.delete_experiment_permission(experiment_id, username)
    return MessageResponse(message="Experiment permission has been deleted.")


@user_permissions_router.post(
    USER_EXPERIMENT_PATTERN_PERMISSIONS,
    status_code=201,
    summary="Create experiment pattern permission",
    description="Creates a new regex-based permission pattern for experiment access.",
    tags=["user experiment pattern permissions"],
)
async def create_user_experiment_pattern_permission(
    username: str = Path(..., description="The username to create pattern permission for"),
    pattern_data: ExperimentRegexCreate = Body(..., description="The regex pattern permission details"),
    _: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
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
        return StatusMessageResponse(message=f"Experiment pattern permission created for {username}")
    except Exception as e:
        logger.error(f"Error creating experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create experiment pattern permission")


@user_permissions_router.get(
    USER_EXPERIMENT_PATTERN_PERMISSIONS,
    response_model=List[ExperimentRegexPermission],
    summary="List experiment pattern permissions for a user",
    description="Retrieves a list of regex-based experiment permission patterns for the specified user.",
    tags=["user experiment pattern permissions"],
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
        return [ExperimentRegexPermission(id=str(perm.id), regex=perm.regex, priority=perm.priority, permission=perm.permission) for perm in permissions]
    except Exception as e:
        logger.error(f"Error listing experiment pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve experiment pattern permissions")


@user_permissions_router.get(
    USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    response_model=ExperimentRegexPermission,
    summary="Get experiment pattern permission for a user",
    description="Retrieves a specific regex-based experiment permission pattern for the specified user.",
    tags=["user experiment pattern permissions"],
)
async def get_user_experiment_pattern_permission(
    username: str = Path(..., description="The username to get pattern permission for"),
    id: str = Path(..., description="The pattern ID to retrieve"),
    admin_username: str = Depends(check_admin_permission),
) -> ExperimentRegexPermission:
    """
    Get a specific regex-based experiment permission pattern for a user.

    Parameters:
    -----------
    username : str
        The username to get the regex permission for.
    id : str
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
        permission = store.get_experiment_regex_permission(username, int(id))
        return ExperimentRegexPermission(id=str(permission.id), regex=permission.regex, priority=permission.priority, permission=permission.permission)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error getting experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Experiment pattern permission not found")


@user_permissions_router.patch(
    USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    summary="Update experiment pattern permission for a user",
    description="Updates a specific regex-based experiment permission pattern for the specified user.",
    tags=["user experiment pattern permissions"],
)
async def update_user_experiment_pattern_permission(
    username: str = Path(..., description="The username to update pattern permission for"),
    id: str = Path(..., description="The pattern ID to update"),
    pattern_data: ExperimentRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """
    Update a specific regex-based experiment permission pattern for a user.

    Parameters:
    -----------
    username : str
        The username to update the regex permission for.
    id : str
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
            id=int(id), regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission, username=username
        )
        return StatusMessageResponse(message=f"Experiment pattern permission updated for {username}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error updating experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update experiment pattern permission")


@user_permissions_router.delete(
    USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    summary="Delete experiment pattern permission for a user",
    description="Deletes a specific regex-based experiment permission pattern for the specified user.",
    tags=["user experiment pattern permissions"],
)
async def delete_user_experiment_pattern_permission(
    username: str = Path(..., description="The username to delete pattern permission for"),
    id: str = Path(..., description="The pattern ID to delete"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """
    Delete a specific regex-based experiment permission pattern for a user.

    Parameters:
    -----------
    username : str
        The username to delete the regex permission for.
    id : str
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
        store.delete_experiment_regex_permission(username, int(id))
        return StatusMessageResponse(message=f"Experiment pattern permission deleted for {username}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error deleting experiment pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete experiment pattern permission")


@user_permissions_router.get(
    USER_PROMPT_PERMISSIONS,
    response_model=List[NamedPermissionSummary],
    summary="List prompt permissions for a user",
    description="Retrieves a list of prompts with permission information for the specified user.",
    tags=["user prompt permissions"],
)
async def get_user_prompts(
    username: str = Path(..., description="The username to get prompt permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[NamedPermissionSummary]:
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

    # Batch resolve permissions for all prompts (fixed number of DB queries)
    prompt_permissions = batch_resolve_prompt_permissions(username, prompts)

    if is_admin:
        list_prompts = prompts
    elif current_username == username:
        list_prompts = [prompt for prompt in prompts if prompt_permissions[prompt.name].permission.name != "NO_PERMISSIONS"]
    else:
        current_user_permissions = batch_resolve_prompt_permissions(current_username, prompts)
        list_prompts = [prompt for prompt in prompts if current_user_permissions[prompt.name].permission.can_manage]

    # Format prompt information with permissions (reuse pre-computed permissions)
    return [
        NamedPermissionSummary(
            name=prompt.name,
            permission=prompt_permissions[prompt.name].permission.name,
            kind=prompt_permissions[prompt.name].kind,
        )
        for prompt in list_prompts
    ]


@user_permissions_router.post(
    USER_PROMPT_PERMISSION_DETAIL,
    status_code=201,
    response_model=StatusMessageResponse,
    summary="Create prompt permission for a user",
    description="Creates a new permission for a user to access a specific prompt.",
    tags=["user prompt permissions"],
)
async def create_user_prompt_permission(
    username: str = Path(..., description="The username to grant prompt permission to"),
    name: str = Path(..., description="The prompt name to set permissions for"),
    permission_data: PromptPermission = Body(..., description="The permission details"),
    _: str = Depends(check_registered_model_manage_permission),
) -> StatusMessageResponse:
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
        return StatusMessageResponse(message=f"Prompt permission created for {username} on {name}")
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
    USER_PROMPT_PERMISSION_DETAIL,
    response_model=PromptPermissionResponse,
    summary="Get prompt permission for a user",
    description="Retrieves the permission for a user on a specific prompt.",
    tags=["user prompt permissions"],
)
async def get_user_prompt_permission(
    username: str = Path(..., description="The username to get prompt permission for"),
    name: str = Path(..., description="The prompt name to get permissions for"),
    _: str = Depends(check_registered_model_manage_permission),
) -> PromptPermissionResponse:
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
        return PromptPermissionResponse(prompt_permission=RegisteredModelPermissionRecord(**rmp.to_json()))
    except Exception as e:
        logger.error(f"Error getting prompt permission: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Prompt permission not found")


@user_permissions_router.patch(
    USER_PROMPT_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Update prompt permission for a user",
    description="Updates the permission for a user on a specific prompt.",
    tags=["user prompt permissions"],
)
async def update_user_prompt_permission(
    username: str = Path(..., description="The username to update prompt permission for"),
    name: str = Path(..., description="The prompt name to update permissions for"),
    permission_data: PromptPermission = Body(..., description="Updated permission details"),
    _: str = Depends(check_registered_model_manage_permission),
) -> StatusMessageResponse:
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
        return StatusMessageResponse(message=f"Prompt permission updated for {username} on {name}")
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
    USER_PROMPT_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete prompt permission for a user",
    description="Deletes the permission for a user on a specific prompt.",
    tags=["user prompt permissions"],
)
async def delete_user_prompt_permission(
    username: str = Path(..., description="The username to delete prompt permission for"),
    name: str = Path(..., description="The prompt name to delete permissions for"),
    _: str = Depends(check_registered_model_manage_permission),
) -> StatusMessageResponse:
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
        return StatusMessageResponse(message=f"Prompt permission deleted for {username} on {name}")
    except Exception as e:
        logger.error(f"Error deleting prompt permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete prompt permission")


@user_permissions_router.get(
    USER_PROMPT_PATTERN_PERMISSIONS,
    response_model=List[RegisteredModelRegexPermissionRecord],
    summary="List prompt pattern permissions for a user",
    description="Retrieves a list of regex-based prompt permission patterns for the specified user.",
    tags=["user prompt pattern permissions"],
)
async def get_user_prompt_pattern_permissions(
    username: str = Path(..., description="The username to list prompt pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[RegisteredModelRegexPermissionRecord]:
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
        return [RegisteredModelRegexPermissionRecord(**r.to_json()) for r in rm]
    except Exception as e:
        logger.error(f"Error listing prompt pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve prompt pattern permissions")


@user_permissions_router.post(
    USER_PROMPT_PATTERN_PERMISSIONS,
    status_code=201,
    response_model=StatusMessageResponse,
    summary="Create prompt pattern permission for a user",
    description="Creates a new regex-based permission pattern for prompt access.",
    tags=["user prompt pattern permissions"],
)
async def create_user_prompt_regex_permission(
    username: str = Path(..., description="The username to create prompt pattern permission for"),
    pattern_data: PromptRegexCreate = Body(..., description="The regex pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
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
        return StatusMessageResponse(message=f"Prompt pattern permission created for {username}")
    except Exception as e:
        logger.error(f"Error creating prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create prompt pattern permission")


@user_permissions_router.get(
    USER_PROMPT_PATTERN_PERMISSION_DETAIL,
    response_model=PromptRegexPermissionResponse,
    summary="Get prompt pattern permission for a user",
    description="Retrieves a specific regex-based prompt permission pattern for the specified user.",
    tags=["user prompt pattern permissions"],
)
async def get_user_prompt_regex_permission(
    username: str = Path(..., description="The username to get prompt pattern permission for"),
    id: str = Path(..., description="The pattern ID to retrieve"),
    admin_username: str = Depends(check_admin_permission),
) -> PromptRegexPermissionResponse:
    """
    Get a specific regex-based prompt permission pattern for a user.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to get the regex permission for.
    id : str
        The unique identifier of the pattern to retrieve.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        The prompt regex permission details.
    """
    try:
        rm = store.get_prompt_regex_permission(id=int(id), username=username)
        return PromptRegexPermissionResponse(prompt_permission=RegisteredModelRegexPermissionRecord(**rm.to_json()))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error getting prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Prompt pattern permission not found")


@user_permissions_router.patch(
    USER_PROMPT_PATTERN_PERMISSION_DETAIL,
    response_model=PromptRegexPermissionResponse,
    summary="Update prompt pattern permission for a user",
    description="Updates a specific regex-based prompt permission pattern for the specified user.",
    tags=["user prompt pattern permissions"],
)
async def update_user_prompt_regex_permission(
    username: str = Path(..., description="The username to update prompt pattern permission for"),
    id: str = Path(..., description="The pattern ID to update"),
    pattern_data: PromptRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> PromptRegexPermissionResponse:
    """
    Update a specific regex-based prompt permission pattern for a user.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to update the regex permission for.
    id : str
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
            id=int(id),
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
            username=username,
        )
        return PromptRegexPermissionResponse(prompt_permission=RegisteredModelRegexPermissionRecord(**rm.to_json()))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error updating prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update prompt pattern permission")


@user_permissions_router.delete(
    USER_PROMPT_PATTERN_PERMISSION_DETAIL,
    response_model=StatusOnlyResponse,
    response_model_exclude_none=True,
    summary="Delete prompt pattern permission for a user",
    description="Deletes a specific regex-based prompt permission pattern for the specified user.",
    tags=["user prompt pattern permissions"],
)
async def delete_user_prompt_regex_permission(
    username: str = Path(..., description="The username to delete prompt pattern permission for"),
    id: str = Path(..., description="The pattern ID to delete"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusOnlyResponse:
    """
    Delete a specific regex-based prompt permission pattern for a user.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to delete the regex permission for.
    id : str
        The unique identifier of the pattern to delete.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        A response indicating success.
    """
    try:
        store.delete_prompt_regex_permission(id=int(id), username=username)
        return StatusOnlyResponse()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error deleting prompt pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete prompt pattern permission")


@user_permissions_router.get(
    USER_REGISTERED_MODEL_PERMISSIONS,
    response_model=List[NamedPermissionSummary],
    summary="List registered model permissions for a user",
    description="Retrieves a list of registered models with permission information for the specified user.",
    tags=["user registered model permissions"],
)
async def get_user_registered_models(
    username: str = Path(..., description="The username to get registered model permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[NamedPermissionSummary]:
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

    # Batch resolve permissions for all models (fixed number of DB queries)
    model_permissions = batch_resolve_model_permissions(username, models)

    if is_admin:
        list_models = models
    elif current_username == username:
        list_models = [model for model in models if model_permissions[model.name].permission.name != "NO_PERMISSIONS"]
    else:
        current_user_permissions = batch_resolve_model_permissions(current_username, models)
        list_models = [model for model in models if current_user_permissions[model.name].permission.can_manage]

    # Format model information with permissions (reuse pre-computed permissions)
    return [
        NamedPermissionSummary(
            name=model.name,
            permission=model_permissions[model.name].permission.name,
            kind=model_permissions[model.name].kind,
        )
        for model in list_models
    ]


@user_permissions_router.post(
    USER_REGISTERED_MODEL_PERMISSION_DETAIL,
    status_code=201,
    response_model=StatusMessageResponse,
    summary="Create registered model permission for a user",
    description="Creates a new permission for a user to access a specific registered model.",
    tags=["user registered model permissions"],
)
async def create_user_registered_model_permission(
    username: str = Path(..., description="The username to grant registered model permission to"),
    name: str = Path(..., description="The registered model name to set permissions for"),
    permission_data: RegisteredModelPermission = Body(..., description="The permission details"),
    _: str = Depends(check_registered_model_manage_permission),
) -> StatusMessageResponse:
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
        return StatusMessageResponse(message=f"Registered model permission created for {username} on {name}")
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
    response_model=RegisteredModelPermissionResponse,
    summary="Get registered model permission for a user",
    description="Retrieves the permission for a user on a specific registered model.",
    tags=["user registered model permissions"],
)
async def get_user_registered_model_permission(
    username: str = Path(..., description="The username to get registered model permission for"),
    name: str = Path(..., description="The registered model name to get permissions for"),
    _: str = Depends(check_registered_model_manage_permission),
) -> RegisteredModelPermissionResponse:
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
        return RegisteredModelPermissionResponse(registered_model_permission=RegisteredModelPermissionRecord(**rmp.to_json()))
    except Exception as e:
        logger.error(f"Error getting registered model permission: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Registered model permission not found")


@user_permissions_router.patch(
    USER_REGISTERED_MODEL_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Update registered model permission for a user",
    description="Updates the permission for a user on a specific registered model.",
    tags=["user registered model permissions"],
)
async def update_user_registered_model_permission(
    username: str = Path(..., description="The username to update registered model permission for"),
    name: str = Path(..., description="The registered model name to update permissions for"),
    permission_data: RegisteredModelPermission = Body(..., description="Updated permission details"),
    _: str = Depends(check_registered_model_manage_permission),
) -> StatusMessageResponse:
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
        return StatusMessageResponse(message=f"Registered model permission updated for {username} on {name}")
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
    response_model=StatusMessageResponse,
    summary="Delete registered model permission for a user",
    description="Deletes the permission for a user on a specific registered model.",
    tags=["user registered model permissions"],
)
async def delete_user_registered_model_permission(
    username: str = Path(..., description="The username to delete registered model permission for"),
    name: str = Path(..., description="The registered model name to delete permissions for"),
    _: str = Depends(check_registered_model_manage_permission),
) -> StatusMessageResponse:
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
        return StatusMessageResponse(message=f"Registered model permission deleted for {username} on {name}")
    except Exception as e:
        logger.error(f"Error deleting registered model permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete registered model permission")


@user_permissions_router.get(
    USER_SCORER_PERMISSIONS,
    response_model=List[ScorerPermissionRecord],
    summary="List scorer permissions for a user",
    description="Retrieves a list of scorers with permission information for the specified user.",
    tags=["user scorer permissions"],
)
async def get_user_scorer_permissions(
    username: str = Path(..., description="The username to get scorer permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[ScorerPermissionRecord]:
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
        return [ScorerPermissionRecord(**p.to_json()) for p in filtered]
    except Exception as e:
        logger.error(f"Error listing scorer permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve scorer permissions")


@user_permissions_router.post(
    USER_SCORER_PERMISSION_DETAIL,
    status_code=201,
    response_model=ScorerPermissionResponse,
    summary="Create scorer permission for a user",
    description="Creates a new permission for a user to access a specific scorer.",
    tags=["user scorer permissions"],
)
async def create_user_scorer_permission(
    username: str = Path(..., description="The username to grant scorer permission to"),
    experiment_id: str = Path(..., description="The experiment ID owning the scorer"),
    scorer_name: str = Path(..., description="The scorer name"),
    permission_data: ScorerPermission = Body(..., description="The permission details"),
    _: None = Depends(check_experiment_manage_permission),
) -> ScorerPermissionResponse:
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
        return ScorerPermissionResponse(scorer_permission=ScorerPermissionRecord(**sp.to_json()))
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
    response_model=ScorerPermissionResponse,
    summary="Get scorer permission for a user",
    description="Retrieves the permission for a user on a specific scorer.",
    tags=["user scorer permissions"],
)
async def get_user_scorer_permission(
    username: str = Path(..., description="The username to get scorer permission for"),
    experiment_id: str = Path(..., description="The experiment ID owning the scorer"),
    scorer_name: str = Path(..., description="The scorer name"),
    _: None = Depends(check_experiment_manage_permission),
) -> ScorerPermissionResponse:
    try:
        sp = store.get_scorer_permission(str(experiment_id), str(scorer_name), str(username))
        return ScorerPermissionResponse(scorer_permission=ScorerPermissionRecord(**sp.to_json()))
    except Exception as e:
        logger.error(f"Error getting scorer permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Scorer permission not found")


@user_permissions_router.patch(
    USER_SCORER_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Update scorer permission for a user",
    description="Updates the permission for a user on a specific scorer.",
    tags=["user scorer permissions"],
)
async def update_user_scorer_permission(
    username: str = Path(..., description="The username to update scorer permission for"),
    experiment_id: str = Path(..., description="The experiment ID owning the scorer"),
    scorer_name: str = Path(..., description="The scorer name"),
    permission_data: ScorerPermission = Body(..., description="Updated permission details"),
    _: None = Depends(check_experiment_manage_permission),
) -> StatusMessageResponse:
    try:
        store.update_scorer_permission(
            experiment_id=str(experiment_id),
            scorer_name=str(scorer_name),
            username=str(username),
            permission=str(permission_data.permission),
        )
        return StatusMessageResponse(message=f"Scorer permission updated for {username} on {scorer_name}")
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
    response_model=StatusMessageResponse,
    summary="Delete scorer permission for a user",
    description="Deletes the permission for a user on a specific scorer.",
    tags=["user scorer permissions"],
)
async def delete_user_scorer_permission(
    username: str = Path(..., description="The username to delete scorer permission for"),
    experiment_id: str = Path(..., description="The experiment ID owning the scorer"),
    scorer_name: str = Path(..., description="The scorer name"),
    _: None = Depends(check_experiment_manage_permission),
) -> StatusMessageResponse:
    try:
        store.delete_scorer_permission(str(experiment_id), str(scorer_name), str(username))
        return StatusMessageResponse(message=f"Scorer permission deleted for {username} on {scorer_name}")
    except Exception as e:
        logger.error(f"Error deleting scorer permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete scorer permission")


@user_permissions_router.get(
    USER_SCORER_PATTERN_PERMISSIONS,
    response_model=List[ScorerRegexPermissionRecord],
    summary="List scorer pattern permissions for a user",
    description="Retrieves a list of regex-based scorer permission patterns for the specified user.",
    tags=["user scorer pattern permissions"],
)
async def get_user_scorer_regex_permissions(
    username: str = Path(..., description="The username to list scorer pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[ScorerRegexPermissionRecord]:
    try:
        perms = store.list_scorer_regex_permissions(username=username)
        return [ScorerRegexPermissionRecord(**p.to_json()) for p in perms]
    except Exception as e:
        logger.error(f"Error listing scorer pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve scorer pattern permissions")


@user_permissions_router.post(
    USER_SCORER_PATTERN_PERMISSIONS,
    status_code=201,
    response_model=ScorerRegexPermissionResponse,
    summary="Create scorer pattern permission for a user",
    description="Creates a new regex-based permission pattern for scorer access.",
    tags=["user scorer pattern permissions"],
)
async def create_user_scorer_regex_permission(
    username: str = Path(..., description="The username to create scorer pattern permission for"),
    pattern_data: ScorerRegexCreate = Body(..., description="The regex pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> ScorerRegexPermissionResponse:
    try:
        perm = store.create_scorer_regex_permission(
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
            username=username,
        )
        return ScorerRegexPermissionResponse(pattern=ScorerRegexPermissionRecord(**perm.to_json()))
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
    response_model=ScorerRegexPermissionResponse,
    summary="Get specific scorer pattern permission for a user",
    description="Retrieves a specific scorer regex pattern permission for a user.",
    tags=["user scorer pattern permissions"],
)
async def get_user_scorer_pattern_permission(
    username: str = Path(..., description="The username"),
    id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> ScorerRegexPermissionResponse:
    try:
        perm = store.get_scorer_regex_permission(username=username, id=id)
        return ScorerRegexPermissionResponse(pattern=ScorerRegexPermissionRecord(**perm.to_json()))
    except Exception as e:
        logger.error(f"Error getting scorer pattern permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Scorer pattern permission not found")


@user_permissions_router.patch(
    USER_SCORER_PATTERN_PERMISSION_DETAIL,
    response_model=ScorerRegexPermissionResponse,
    summary="Update scorer pattern permission for a user",
    description="Updates a specific scorer regex pattern permission for a user.",
    tags=["user scorer pattern permissions"],
)
async def update_user_scorer_pattern_permission(
    username: str = Path(..., description="The username"),
    id: int = Path(..., description="The pattern ID"),
    pattern_data: ScorerRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> ScorerRegexPermissionResponse:
    try:
        perm = store.update_scorer_regex_permission(
            id=id,
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
            username=username,
        )
        return ScorerRegexPermissionResponse(pattern=ScorerRegexPermissionRecord(**perm.to_json()))
    except Exception as e:
        logger.error(f"Error updating scorer pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update scorer pattern permission")


@user_permissions_router.delete(
    USER_SCORER_PATTERN_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete scorer pattern permission for a user",
    description="Deletes a specific scorer regex pattern permission for a user.",
    tags=["user scorer pattern permissions"],
)
async def delete_user_scorer_pattern_permission(
    username: str = Path(..., description="The username"),
    id: int = Path(..., description="The pattern ID"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    try:
        store.delete_scorer_regex_permission(id=id, username=username)
        return StatusMessageResponse(message=f"Scorer pattern permission deleted for {username}")
    except Exception as e:
        logger.error(f"Error deleting scorer pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete scorer pattern permission")


@user_permissions_router.get(
    USER_REGISTERED_MODEL_PATTERN_PERMISSIONS,
    response_model=List[RegisteredModelRegexPermissionRecord],
    summary="List registered model pattern permissions for a user",
    description="Retrieves a list of regex-based registered model permission patterns for the specified user.",
    tags=["user registered model pattern permissions"],
)
async def get_user_registered_model_regex_permissions(
    username: str = Path(..., description="The username to list registered model pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[RegisteredModelRegexPermissionRecord]:
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
        return [RegisteredModelRegexPermissionRecord(**r.to_json()) for r in rm]
    except Exception as e:
        logger.error(f"Error listing registered model pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve registered model pattern permissions")


@user_permissions_router.post(
    USER_REGISTERED_MODEL_PATTERN_PERMISSIONS,
    status_code=201,
    response_model=StatusMessageResponse,
    summary="Create registered model pattern permission for a user",
    description="Creates a new regex-based permission pattern for registered model access.",
    tags=["user registered model pattern permissions"],
)
async def create_user_registered_model_regex_permission(
    username: str = Path(..., description="The username to create registered model pattern permission for"),
    pattern_data: RegisteredModelRegexCreate = Body(..., description="The regex pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
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
        return StatusMessageResponse(message=f"Registered model pattern permission created for {username}")
    except Exception as e:
        logger.error(f"Error creating registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create registered model pattern permission")


@user_permissions_router.get(
    USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    response_model=RegisteredModelRegexPermissionResponse,
    summary="Get registered model pattern permission for a user",
    description="Retrieves a specific regex-based registered model permission pattern for the specified user.",
    tags=["user registered model pattern permissions"],
)
async def get_user_registered_model_regex_permission(
    username: str = Path(..., description="The username to get registered model pattern permission for"),
    id: str = Path(..., description="The pattern ID to retrieve"),
    admin_username: str = Depends(check_admin_permission),
) -> RegisteredModelRegexPermissionResponse:
    """
    Get a specific regex-based registered model permission pattern for a user.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to get the regex permission for.
    id : str
        The unique identifier of the pattern to retrieve.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        The registered model regex permission details.
    """
    try:
        rm = store.get_registered_model_regex_permission(id=int(id), username=username)
        return RegisteredModelRegexPermissionResponse(registered_model_permission=RegisteredModelRegexPermissionRecord(**rm.to_json()))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error getting registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Registered model pattern permission not found")


@user_permissions_router.patch(
    USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    response_model=RegisteredModelRegexPermissionResponse,
    summary="Update registered model pattern permission for a user",
    description="Updates a specific regex-based registered model permission pattern for the specified user.",
    tags=["user registered model pattern permissions"],
)
async def update_user_registered_model_regex_permission(
    username: str = Path(..., description="The username to update registered model pattern permission for"),
    id: str = Path(..., description="The pattern ID to update"),
    pattern_data: RegisteredModelRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> RegisteredModelRegexPermissionResponse:
    """
    Update a specific regex-based registered model permission pattern for a user.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to update the regex permission for.
    id : str
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
            id=int(id),
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
            username=username,
        )
        return RegisteredModelRegexPermissionResponse(registered_model_permission=RegisteredModelRegexPermissionRecord(**rm.to_json()))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error updating registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update registered model pattern permission")


@user_permissions_router.delete(
    USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    response_model=StatusOnlyResponse,
    response_model_exclude_none=True,
    summary="Delete registered model pattern permission for a user",
    description="Deletes a specific regex-based registered model permission pattern for the specified user.",
    tags=["user registered model pattern permissions"],
)
async def delete_user_registered_model_regex_permission(
    username: str = Path(..., description="The username to delete registered model pattern permission for"),
    id: str = Path(..., description="The pattern ID to delete"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusOnlyResponse:
    """
    Delete a specific regex-based registered model permission pattern for a user.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to delete the regex permission for.
    id : str
        The unique identifier of the pattern to delete.
    admin_username : str
        The username of the admin performing the action (from dependency).

    Returns:
    --------
    JSONResponse
        A response indicating success.
    """
    try:
        store.delete_registered_model_regex_permission(id=int(id), username=username)
        return StatusOnlyResponse()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pattern ID format. Expected an integer.")
    except Exception as e:
        logger.error(f"Error deleting registered model pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete registered model pattern permission")


# ========================================================================================
# GATEWAY ENDPOINT PERMISSIONS
# ========================================================================================


@user_permissions_router.get(
    USER_GATEWAY_ENDPOINT_PERMISSIONS,
    response_model=List[NamedPermissionSummary],
    summary="List gateway endpoint permissions for a user",
    description="Retrieves a list of gateway endpoint permissions for the specified user.",
    tags=["user gateway endpoint permissions"],
)
async def get_user_gateway_endpoint_permissions(
    username: str = Path(..., description="The username to get gateway endpoint permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[NamedPermissionSummary]:
    """List gateway endpoint permissions for a user."""
    try:
        perms = store.list_gateway_endpoint_permissions(username=username)
        return [NamedPermissionSummary(name=p.endpoint_id, permission=p.permission, kind="user") for p in perms]
    except Exception as e:
        logger.error(f"Error listing gateway endpoint permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve gateway endpoint permissions")


@user_permissions_router.post(
    USER_GATEWAY_ENDPOINT_PERMISSION_DETAIL,
    status_code=201,
    response_model=NamedPermissionSummary,
    summary="Create gateway endpoint permission for a user",
    description="Creates a new permission for a user to access a specific gateway endpoint.",
    tags=["user gateway endpoint permissions"],
)
async def create_user_gateway_endpoint_permission(
    username: str = Path(..., description="The username to grant gateway endpoint permission to"),
    name: str = Path(..., description="The gateway endpoint name to set permissions for"),
    permission_data: GatewayPermission = Body(..., description="The permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> NamedPermissionSummary:
    """Create a gateway endpoint permission for a user."""
    try:
        perm = store.create_gateway_endpoint_permission(gateway_name=name, username=username, permission=permission_data.permission)
        return NamedPermissionSummary(name=perm.endpoint_id, permission=perm.permission, kind="user")
    except Exception as e:
        logger.error(f"Error creating gateway endpoint permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create gateway endpoint permission")


@user_permissions_router.get(
    USER_GATEWAY_ENDPOINT_PERMISSION_DETAIL,
    response_model=NamedPermissionSummary,
    summary="Get gateway endpoint permission for a user",
    description="Retrieves the permission for a user on a specific gateway endpoint.",
    tags=["user gateway endpoint permissions"],
)
async def get_user_gateway_endpoint_permission(
    username: str = Path(..., description="The username to get gateway endpoint permission for"),
    name: str = Path(..., description="The gateway endpoint name to get permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> NamedPermissionSummary:
    """Get a gateway endpoint permission for a user."""
    try:
        perm = store.get_gateway_endpoint_permission(gateway_name=name, username=username)
        return NamedPermissionSummary(name=perm.endpoint_id, permission=perm.permission, kind="user")
    except Exception as e:
        logger.error(f"Error getting gateway endpoint permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Gateway endpoint permission not found")


@user_permissions_router.patch(
    USER_GATEWAY_ENDPOINT_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Update gateway endpoint permission for a user",
    description="Updates the permission for a user on a specific gateway endpoint.",
    tags=["user gateway endpoint permissions"],
)
async def update_user_gateway_endpoint_permission(
    username: str = Path(..., description="The username to update gateway endpoint permission for"),
    name: str = Path(..., description="The gateway endpoint name to update permissions for"),
    permission_data: GatewayPermission = Body(..., description="Updated permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Update a gateway endpoint permission for a user."""
    try:
        store.update_gateway_endpoint_permission(gateway_name=name, username=username, permission=permission_data.permission)
        return StatusMessageResponse(message=f"Gateway endpoint permission updated for {username} on {name}")
    except Exception as e:
        logger.error(f"Error updating gateway endpoint permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update gateway endpoint permission")


@user_permissions_router.delete(
    USER_GATEWAY_ENDPOINT_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway endpoint permission for a user",
    description="Deletes the permission for a user on a specific gateway endpoint.",
    tags=["user gateway endpoint permissions"],
)
async def delete_user_gateway_endpoint_permission(
    username: str = Path(..., description="The username to delete gateway endpoint permission for"),
    name: str = Path(..., description="The gateway endpoint name to delete permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway endpoint permission for a user."""
    try:
        store.delete_gateway_endpoint_permission(gateway_name=name, username=username)
        return StatusMessageResponse(message=f"Gateway endpoint permission deleted for {username} on {name}")
    except Exception as e:
        logger.error(f"Error deleting gateway endpoint permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete gateway endpoint permission")


# ========================================================================================
# GATEWAY ENDPOINT PATTERN PERMISSIONS
# ========================================================================================


@user_permissions_router.get(
    USER_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS,
    response_model=List[UserGatewayRegexPermissionItem],
    summary="List gateway endpoint pattern permissions for a user",
    description="Retrieves a list of regex-based gateway endpoint permission patterns for the specified user.",
    tags=["user gateway endpoint pattern permissions"],
)
async def get_user_gateway_endpoint_pattern_permissions(
    username: str = Path(..., description="The username to list gateway endpoint pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[UserGatewayRegexPermissionItem]:
    """List gateway endpoint pattern permissions for a user."""
    try:
        perms = store.list_gateway_endpoint_regex_permissions(username=username)
        return [UserGatewayRegexPermissionItem(id=p.id, regex=p.regex, priority=p.priority, user_id=p.user_id, permission=p.permission) for p in perms]
    except Exception as e:
        logger.error(f"Error listing gateway endpoint pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve gateway endpoint pattern permissions")


@user_permissions_router.post(
    USER_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS,
    status_code=201,
    response_model=UserGatewayRegexPermissionItem,
    summary="Create gateway endpoint pattern permission for a user",
    description="Creates a new regex-based permission pattern for gateway endpoint access.",
    tags=["user gateway endpoint pattern permissions"],
)
async def create_user_gateway_endpoint_pattern_permission(
    username: str = Path(..., description="The username to create gateway endpoint pattern permission for"),
    pattern_data: GatewayRegexCreate = Body(..., description="The regex pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> UserGatewayRegexPermissionItem:
    """Create a gateway endpoint pattern permission for a user."""
    try:
        perm = store.create_gateway_endpoint_regex_permission(
            regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission, username=username
        )
        return UserGatewayRegexPermissionItem(id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.user_id, permission=perm.permission)
    except Exception as e:
        logger.error(f"Error creating gateway endpoint pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create gateway endpoint pattern permission")


@user_permissions_router.get(
    USER_GATEWAY_ENDPOINT_PATTERN_PERMISSION_DETAIL,
    response_model=UserGatewayRegexPermissionItem,
    summary="Get gateway endpoint pattern permission for a user",
    description="Retrieves a specific regex-based gateway endpoint permission pattern for the specified user.",
    tags=["user gateway endpoint pattern permissions"],
)
async def get_user_gateway_endpoint_pattern_permission(
    username: str = Path(..., description="The username to get gateway endpoint pattern permission for"),
    id: int = Path(..., description="The pattern ID to retrieve"),
    admin_username: str = Depends(check_admin_permission),
) -> UserGatewayRegexPermissionItem:
    """Get a gateway endpoint pattern permission for a user."""
    try:
        perm = store.get_gateway_endpoint_regex_permission(id=id, username=username)
        return UserGatewayRegexPermissionItem(id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.user_id, permission=perm.permission)
    except Exception as e:
        logger.error(f"Error getting gateway endpoint pattern permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Gateway endpoint pattern permission not found")


@user_permissions_router.patch(
    USER_GATEWAY_ENDPOINT_PATTERN_PERMISSION_DETAIL,
    response_model=UserGatewayRegexPermissionItem,
    summary="Update gateway endpoint pattern permission for a user",
    description="Updates a specific regex-based gateway endpoint permission pattern for the specified user.",
    tags=["user gateway endpoint pattern permissions"],
)
async def update_user_gateway_endpoint_pattern_permission(
    username: str = Path(..., description="The username to update gateway endpoint pattern permission for"),
    id: int = Path(..., description="The pattern ID to update"),
    pattern_data: GatewayRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> UserGatewayRegexPermissionItem:
    """Update a gateway endpoint pattern permission for a user."""
    try:
        perm = store.update_gateway_endpoint_regex_permission(
            id=id, regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission, username=username
        )
        return UserGatewayRegexPermissionItem(id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.user_id, permission=perm.permission)
    except Exception as e:
        logger.error(f"Error updating gateway endpoint pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update gateway endpoint pattern permission")


@user_permissions_router.delete(
    USER_GATEWAY_ENDPOINT_PATTERN_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway endpoint pattern permission for a user",
    description="Deletes a specific regex-based gateway endpoint permission pattern for the specified user.",
    tags=["user gateway endpoint pattern permissions"],
)
async def delete_user_gateway_endpoint_pattern_permission(
    username: str = Path(..., description="The username to delete gateway endpoint pattern permission for"),
    id: int = Path(..., description="The pattern ID to delete"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway endpoint pattern permission for a user."""
    try:
        store.delete_gateway_endpoint_regex_permission(id=id, username=username)
        return StatusMessageResponse(message=f"Gateway endpoint pattern permission deleted for {username}")
    except Exception as e:
        logger.error(f"Error deleting gateway endpoint pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete gateway endpoint pattern permission")


# ========================================================================================
# GATEWAY MODEL DEFINITION PERMISSIONS
# ========================================================================================


@user_permissions_router.get(
    USER_GATEWAY_MODEL_DEFINITION_PERMISSIONS,
    response_model=List[NamedPermissionSummary],
    summary="List gateway model definition permissions for a user",
    description="Retrieves a list of gateway model definition permissions for the specified user.",
    tags=["user gateway model definition permissions"],
)
async def get_user_gateway_model_definition_permissions(
    username: str = Path(..., description="The username to get gateway model definition permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[NamedPermissionSummary]:
    """List gateway model definition permissions for a user."""
    try:
        perms = store.list_gateway_model_definition_permissions(username=username)
        return [NamedPermissionSummary(name=p.model_definition_id, permission=p.permission, kind="user") for p in perms]
    except Exception as e:
        logger.error(f"Error listing gateway model definition permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve gateway model definition permissions")


@user_permissions_router.post(
    USER_GATEWAY_MODEL_DEFINITION_PERMISSION_DETAIL,
    status_code=201,
    response_model=NamedPermissionSummary,
    summary="Create gateway model definition permission for a user",
    description="Creates a new permission for a user to access a specific gateway model definition.",
    tags=["user gateway model definition permissions"],
)
async def create_user_gateway_model_definition_permission(
    username: str = Path(..., description="The username to grant gateway model definition permission to"),
    name: str = Path(..., description="The gateway model definition name to set permissions for"),
    permission_data: GatewayPermission = Body(..., description="The permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> NamedPermissionSummary:
    """Create a gateway model definition permission for a user."""
    try:
        perm = store.create_gateway_model_definition_permission(gateway_name=name, username=username, permission=permission_data.permission)
        return NamedPermissionSummary(name=perm.model_definition_id, permission=perm.permission, kind="user")
    except Exception as e:
        logger.error(f"Error creating gateway model definition permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create gateway model definition permission")


@user_permissions_router.get(
    USER_GATEWAY_MODEL_DEFINITION_PERMISSION_DETAIL,
    response_model=NamedPermissionSummary,
    summary="Get gateway model definition permission for a user",
    description="Retrieves the permission for a user on a specific gateway model definition.",
    tags=["user gateway model definition permissions"],
)
async def get_user_gateway_model_definition_permission(
    username: str = Path(..., description="The username to get gateway model definition permission for"),
    name: str = Path(..., description="The gateway model definition name to get permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> NamedPermissionSummary:
    """Get a gateway model definition permission for a user."""
    try:
        perm = store.get_gateway_model_definition_permission(gateway_name=name, username=username)
        return NamedPermissionSummary(name=perm.model_definition_id, permission=perm.permission, kind="user")
    except Exception as e:
        logger.error(f"Error getting gateway model definition permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Gateway model definition permission not found")


@user_permissions_router.patch(
    USER_GATEWAY_MODEL_DEFINITION_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Update gateway model definition permission for a user",
    description="Updates the permission for a user on a specific gateway model definition.",
    tags=["user gateway model definition permissions"],
)
async def update_user_gateway_model_definition_permission(
    username: str = Path(..., description="The username to update gateway model definition permission for"),
    name: str = Path(..., description="The gateway model definition name to update permissions for"),
    permission_data: GatewayPermission = Body(..., description="Updated permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Update a gateway model definition permission for a user."""
    try:
        store.update_gateway_model_definition_permission(gateway_name=name, username=username, permission=permission_data.permission)
        return StatusMessageResponse(message=f"Gateway model definition permission updated for {username} on {name}")
    except Exception as e:
        logger.error(f"Error updating gateway model definition permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update gateway model definition permission")


@user_permissions_router.delete(
    USER_GATEWAY_MODEL_DEFINITION_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway model definition permission for a user",
    description="Deletes the permission for a user on a specific gateway model definition.",
    tags=["user gateway model definition permissions"],
)
async def delete_user_gateway_model_definition_permission(
    username: str = Path(..., description="The username to delete gateway model definition permission for"),
    name: str = Path(..., description="The gateway model definition name to delete permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway model definition permission for a user."""
    try:
        store.delete_gateway_model_definition_permission(gateway_name=name, username=username)
        return StatusMessageResponse(message=f"Gateway model definition permission deleted for {username} on {name}")
    except Exception as e:
        logger.error(f"Error deleting gateway model definition permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete gateway model definition permission")


# ========================================================================================
# GATEWAY MODEL DEFINITION PATTERN PERMISSIONS
# ========================================================================================


@user_permissions_router.get(
    USER_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSIONS,
    response_model=List[UserGatewayRegexPermissionItem],
    summary="List gateway model definition pattern permissions for a user",
    description="Retrieves a list of regex-based gateway model definition permission patterns for the specified user.",
    tags=["user gateway model definition pattern permissions"],
)
async def get_user_gateway_model_definition_pattern_permissions(
    username: str = Path(..., description="The username to list gateway model definition pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[UserGatewayRegexPermissionItem]:
    """List gateway model definition pattern permissions for a user."""
    try:
        perms = store.list_gateway_model_definition_regex_permissions(username=username)
        return [UserGatewayRegexPermissionItem(id=p.id, regex=p.regex, priority=p.priority, user_id=p.user_id, permission=p.permission) for p in perms]
    except Exception as e:
        logger.error(f"Error listing gateway model definition pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve gateway model definition pattern permissions")


@user_permissions_router.post(
    USER_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSIONS,
    status_code=201,
    response_model=UserGatewayRegexPermissionItem,
    summary="Create gateway model definition pattern permission for a user",
    description="Creates a new regex-based permission pattern for gateway model definition access.",
    tags=["user gateway model definition pattern permissions"],
)
async def create_user_gateway_model_definition_pattern_permission(
    username: str = Path(..., description="The username to create gateway model definition pattern permission for"),
    pattern_data: GatewayRegexCreate = Body(..., description="The regex pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> UserGatewayRegexPermissionItem:
    """Create a gateway model definition pattern permission for a user."""
    try:
        perm = store.create_gateway_model_definition_regex_permission(
            regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission, username=username
        )
        return UserGatewayRegexPermissionItem(id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.user_id, permission=perm.permission)
    except Exception as e:
        logger.error(f"Error creating gateway model definition pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create gateway model definition pattern permission")


@user_permissions_router.get(
    USER_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSION_DETAIL,
    response_model=UserGatewayRegexPermissionItem,
    summary="Get gateway model definition pattern permission for a user",
    description="Retrieves a specific regex-based gateway model definition permission pattern for the specified user.",
    tags=["user gateway model definition pattern permissions"],
)
async def get_user_gateway_model_definition_pattern_permission(
    username: str = Path(..., description="The username to get gateway model definition pattern permission for"),
    id: int = Path(..., description="The pattern ID to retrieve"),
    admin_username: str = Depends(check_admin_permission),
) -> UserGatewayRegexPermissionItem:
    """Get a gateway model definition pattern permission for a user."""
    try:
        perm = store.get_gateway_model_definition_regex_permission(id=id, username=username)
        return UserGatewayRegexPermissionItem(id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.user_id, permission=perm.permission)
    except Exception as e:
        logger.error(f"Error getting gateway model definition pattern permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Gateway model definition pattern permission not found")


@user_permissions_router.patch(
    USER_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSION_DETAIL,
    response_model=UserGatewayRegexPermissionItem,
    summary="Update gateway model definition pattern permission for a user",
    description="Updates a specific regex-based gateway model definition permission pattern for the specified user.",
    tags=["user gateway model definition pattern permissions"],
)
async def update_user_gateway_model_definition_pattern_permission(
    username: str = Path(..., description="The username to update gateway model definition pattern permission for"),
    id: int = Path(..., description="The pattern ID to update"),
    pattern_data: GatewayRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> UserGatewayRegexPermissionItem:
    """Update a gateway model definition pattern permission for a user."""
    try:
        perm = store.update_gateway_model_definition_regex_permission(
            id=id, regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission, username=username
        )
        return UserGatewayRegexPermissionItem(id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.user_id, permission=perm.permission)
    except Exception as e:
        logger.error(f"Error updating gateway model definition pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update gateway model definition pattern permission")


@user_permissions_router.delete(
    USER_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway model definition pattern permission for a user",
    description="Deletes a specific regex-based gateway model definition permission pattern for the specified user.",
    tags=["user gateway model definition pattern permissions"],
)
async def delete_user_gateway_model_definition_pattern_permission(
    username: str = Path(..., description="The username to delete gateway model definition pattern permission for"),
    id: int = Path(..., description="The pattern ID to delete"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway model definition pattern permission for a user."""
    try:
        store.delete_gateway_model_definition_regex_permission(id=id, username=username)
        return StatusMessageResponse(message=f"Gateway model definition pattern permission deleted for {username}")
    except Exception as e:
        logger.error(f"Error deleting gateway model definition pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete gateway model definition pattern permission")


# ========================================================================================
# GATEWAY SECRET PERMISSIONS
# ========================================================================================


@user_permissions_router.get(
    USER_GATEWAY_SECRET_PERMISSIONS,
    response_model=List[NamedPermissionSummary],
    summary="List gateway secret permissions for a user",
    description="Retrieves a list of gateway secret permissions for the specified user.",
    tags=["user gateway secret permissions"],
)
async def get_user_gateway_secret_permissions(
    username: str = Path(..., description="The username to get gateway secret permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[NamedPermissionSummary]:
    """List gateway secret permissions for a user."""
    try:
        perms = store.list_gateway_secret_permissions(username=username)
        return [NamedPermissionSummary(name=p.secret_id, permission=p.permission, kind="user") for p in perms]
    except Exception as e:
        logger.error(f"Error listing gateway secret permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve gateway secret permissions")


@user_permissions_router.post(
    USER_GATEWAY_SECRET_PERMISSION_DETAIL,
    status_code=201,
    response_model=NamedPermissionSummary,
    summary="Create gateway secret permission for a user",
    description="Creates a new permission for a user to access a specific gateway secret.",
    tags=["user gateway secret permissions"],
)
async def create_user_gateway_secret_permission(
    username: str = Path(..., description="The username to grant gateway secret permission to"),
    name: str = Path(..., description="The gateway secret name to set permissions for"),
    permission_data: GatewayPermission = Body(..., description="The permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> NamedPermissionSummary:
    """Create a gateway secret permission for a user."""
    try:
        perm = store.create_gateway_secret_permission(gateway_name=name, username=username, permission=permission_data.permission)
        return NamedPermissionSummary(name=perm.secret_id, permission=perm.permission, kind="user")
    except Exception as e:
        logger.error(f"Error creating gateway secret permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create gateway secret permission")


@user_permissions_router.get(
    USER_GATEWAY_SECRET_PERMISSION_DETAIL,
    response_model=NamedPermissionSummary,
    summary="Get gateway secret permission for a user",
    description="Retrieves the permission for a user on a specific gateway secret.",
    tags=["user gateway secret permissions"],
)
async def get_user_gateway_secret_permission(
    username: str = Path(..., description="The username to get gateway secret permission for"),
    name: str = Path(..., description="The gateway secret name to get permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> NamedPermissionSummary:
    """Get a gateway secret permission for a user."""
    try:
        perm = store.get_gateway_secret_permission(gateway_name=name, username=username)
        return NamedPermissionSummary(name=perm.secret_id, permission=perm.permission, kind="user")
    except Exception as e:
        logger.error(f"Error getting gateway secret permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Gateway secret permission not found")


@user_permissions_router.patch(
    USER_GATEWAY_SECRET_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Update gateway secret permission for a user",
    description="Updates the permission for a user on a specific gateway secret.",
    tags=["user gateway secret permissions"],
)
async def update_user_gateway_secret_permission(
    username: str = Path(..., description="The username to update gateway secret permission for"),
    name: str = Path(..., description="The gateway secret name to update permissions for"),
    permission_data: GatewayPermission = Body(..., description="Updated permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Update a gateway secret permission for a user."""
    try:
        store.update_gateway_secret_permission(gateway_name=name, username=username, permission=permission_data.permission)
        return StatusMessageResponse(message=f"Gateway secret permission updated for {username} on {name}")
    except Exception as e:
        logger.error(f"Error updating gateway secret permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update gateway secret permission")


@user_permissions_router.delete(
    USER_GATEWAY_SECRET_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway secret permission for a user",
    description="Deletes the permission for a user on a specific gateway secret.",
    tags=["user gateway secret permissions"],
)
async def delete_user_gateway_secret_permission(
    username: str = Path(..., description="The username to delete gateway secret permission for"),
    name: str = Path(..., description="The gateway secret name to delete permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway secret permission for a user."""
    try:
        store.delete_gateway_secret_permission(gateway_name=name, username=username)
        return StatusMessageResponse(message=f"Gateway secret permission deleted for {username} on {name}")
    except Exception as e:
        logger.error(f"Error deleting gateway secret permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete gateway secret permission")


# ========================================================================================
# GATEWAY SECRET PATTERN PERMISSIONS
# ========================================================================================


@user_permissions_router.get(
    USER_GATEWAY_SECRET_PATTERN_PERMISSIONS,
    response_model=List[UserGatewayRegexPermissionItem],
    summary="List gateway secret pattern permissions for a user",
    description="Retrieves a list of regex-based gateway secret permission patterns for the specified user.",
    tags=["user gateway secret pattern permissions"],
)
async def get_user_gateway_secret_pattern_permissions(
    username: str = Path(..., description="The username to list gateway secret pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[UserGatewayRegexPermissionItem]:
    """List gateway secret pattern permissions for a user."""
    try:
        perms = store.list_gateway_secret_regex_permissions(username=username)
        return [UserGatewayRegexPermissionItem(id=p.id, regex=p.regex, priority=p.priority, user_id=p.user_id, permission=p.permission) for p in perms]
    except Exception as e:
        logger.error(f"Error listing gateway secret pattern permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve gateway secret pattern permissions")


@user_permissions_router.post(
    USER_GATEWAY_SECRET_PATTERN_PERMISSIONS,
    status_code=201,
    response_model=UserGatewayRegexPermissionItem,
    summary="Create gateway secret pattern permission for a user",
    description="Creates a new regex-based permission pattern for gateway secret access.",
    tags=["user gateway secret pattern permissions"],
)
async def create_user_gateway_secret_pattern_permission(
    username: str = Path(..., description="The username to create gateway secret pattern permission for"),
    pattern_data: GatewayRegexCreate = Body(..., description="The regex pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> UserGatewayRegexPermissionItem:
    """Create a gateway secret pattern permission for a user."""
    try:
        perm = store.create_gateway_secret_regex_permission(
            regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission, username=username
        )
        return UserGatewayRegexPermissionItem(id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.user_id, permission=perm.permission)
    except Exception as e:
        logger.error(f"Error creating gateway secret pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create gateway secret pattern permission")


@user_permissions_router.get(
    USER_GATEWAY_SECRET_PATTERN_PERMISSION_DETAIL,
    response_model=UserGatewayRegexPermissionItem,
    summary="Get gateway secret pattern permission for a user",
    description="Retrieves a specific regex-based gateway secret permission pattern for the specified user.",
    tags=["user gateway secret pattern permissions"],
)
async def get_user_gateway_secret_pattern_permission(
    username: str = Path(..., description="The username to get gateway secret pattern permission for"),
    id: int = Path(..., description="The pattern ID to retrieve"),
    admin_username: str = Depends(check_admin_permission),
) -> UserGatewayRegexPermissionItem:
    """Get a gateway secret pattern permission for a user."""
    try:
        perm = store.get_gateway_secret_regex_permission(id=id, username=username)
        return UserGatewayRegexPermissionItem(id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.user_id, permission=perm.permission)
    except Exception as e:
        logger.error(f"Error getting gateway secret pattern permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Gateway secret pattern permission not found")


@user_permissions_router.patch(
    USER_GATEWAY_SECRET_PATTERN_PERMISSION_DETAIL,
    response_model=UserGatewayRegexPermissionItem,
    summary="Update gateway secret pattern permission for a user",
    description="Updates a specific regex-based gateway secret permission pattern for the specified user.",
    tags=["user gateway secret pattern permissions"],
)
async def update_user_gateway_secret_pattern_permission(
    username: str = Path(..., description="The username to update gateway secret pattern permission for"),
    id: int = Path(..., description="The pattern ID to update"),
    pattern_data: GatewayRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> UserGatewayRegexPermissionItem:
    """Update a gateway secret pattern permission for a user."""
    try:
        perm = store.update_gateway_secret_regex_permission(
            id=id, regex=pattern_data.regex, priority=pattern_data.priority, permission=pattern_data.permission, username=username
        )
        return UserGatewayRegexPermissionItem(id=perm.id, regex=perm.regex, priority=perm.priority, user_id=perm.user_id, permission=perm.permission)
    except Exception as e:
        logger.error(f"Error updating gateway secret pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update gateway secret pattern permission")


@user_permissions_router.delete(
    USER_GATEWAY_SECRET_PATTERN_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway secret pattern permission for a user",
    description="Deletes a specific regex-based gateway secret permission pattern for the specified user.",
    tags=["user gateway secret pattern permissions"],
)
async def delete_user_gateway_secret_pattern_permission(
    username: str = Path(..., description="The username to delete gateway secret pattern permission for"),
    id: int = Path(..., description="The pattern ID to delete"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway secret pattern permission for a user."""
    try:
        store.delete_gateway_secret_regex_permission(id=id, username=username)
        return StatusMessageResponse(message=f"Gateway secret pattern permission deleted for {username}")
    except Exception as e:
        logger.error(f"Error deleting gateway secret pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete gateway secret pattern permission")
