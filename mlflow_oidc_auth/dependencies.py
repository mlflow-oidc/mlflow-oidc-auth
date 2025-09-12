"""
FastAPI dependency functions for the MLflow OIDC Auth Plugin.

This module provides dependency functions that can be used with FastAPI's
dependency injection system for common authorization and validation tasks.
"""

from fastapi import Depends, Request, HTTPException, Path

from mlflow_oidc_auth.utils import can_manage_experiment, get_username, get_is_admin, can_manage_registered_model


async def check_experiment_permission(
    experiment_id: str = Path(..., description="The experiment ID"), username: str = Path(..., description="The username to check permissions for")
) -> None:
    """
    Check if the user has permission to access or manage the specified experiment.

    This dependency validates that the authenticated user has the necessary
    permissions to perform operations on the specified experiment.

    Parameters:
    -----------
    experiment_id : str
        The ID of the experiment to check permissions for (from path).
    username : str
        The username of the user to check permissions for (from path).

    Raises:
    -------
    HTTPException
        If the user doesn't have permission to access the experiment.

    Returns:
    --------
    None
        If the user has permission to access the experiment.
    """
    if not can_manage_experiment(experiment_id, username):
        raise HTTPException(status_code=403, detail=f"User does not have sufficient permissions to access experiment {experiment_id}")
    return None


def create_experiment_permission_dependency(experiment_id_param: str = "experiment_id", username_param: str = "username"):
    """
    Create a dependency function for checking experiment permissions with custom parameter names.

    Parameters:
    -----------
    experiment_id_param : str
        The name of the path parameter containing the experiment ID.
    username_param : str
        The name of the path parameter containing the username.

    Returns:
    --------
    Callable
        A dependency function that validates experiment permissions.
    """

    async def dependency(
        experiment_id: str = Path(..., alias=experiment_id_param, description="The experiment ID"),
        username: str = Path(..., alias=username_param, description="The username to check permissions for"),
    ) -> None:
        """Check experiment permissions for the given user and experiment."""
        if not can_manage_experiment(experiment_id, username):
            raise HTTPException(status_code=403, detail=f"User does not have sufficient permissions to access experiment {experiment_id}")
        return None

    return dependency


async def check_current_user_experiment_permission(
    experiment_id: str = Path(..., description="The experiment ID"), current_username: str = Depends(get_username)
) -> None:
    """
    Check if the current authenticated user has permission to access the specified experiment.

    Parameters:
    -----------
    request : Request
        The FastAPI request object containing session information.
    experiment_id : str
        The ID of the experiment to check permissions for.

    Returns:
    --------
    str
        The username of the authenticated user who has permission.

    Raises:
    -------
    HTTPException
        If the user doesn't have permission to access the experiment.
    """
    if not can_manage_experiment(experiment_id, current_username):
        raise HTTPException(status_code=403, detail=f"User does not have sufficient permissions to access experiment {experiment_id}")
    return None


async def check_admin_permission(
    request: Request,
) -> str:
    """
    Verify that the current user has administrator privileges.

    This dependency checks if the authenticated user has admin permissions
    and raises an HTTPException if they don't.

    Parameters:
    -----------
    request : Request
        The FastAPI request object containing session information.

    Returns:
    --------
    str
        The username of the authenticated admin user.

    Raises:
    -------
    HTTPException
        If the user is not authenticated or doesn't have admin permissions.
    """
    # Check if user is authenticated and has admin permissions
    is_admin = await get_is_admin(request=request)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Administrator privileges required for this operation")

    # Return the username for use in the endpoint function
    return await get_username(request=request)


async def check_experiment_manage_permission(
    request: Request,
    experiment_id: str = Path(..., description="The experiment ID"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> None:
    """
    Check if the current user can manage the specified experiment.

    This dependency checks if the authenticated user is an admin or has
    manage permissions for the specified experiment.

    Parameters:
    -----------
    experiment_id : str
        The ID of the experiment to check permissions for.
    request : Request
        The FastAPI request object.

    Returns:
    --------
    str
        The username of the authenticated user.

    Raises:
    -------
    HTTPException
        If the user doesn't have management permission for the experiment.
    """
    if not is_admin and not can_manage_experiment(experiment_id, current_username):
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage experiment {experiment_id}")

    return None


async def check_registered_model_permission(
    model_name: str = Path(..., description="The model name"), current_username: str = Depends(get_username), is_admin: bool = Depends(get_is_admin)
) -> None:
    """
    Check if the current user can manage the specified registered model.

    This dependency checks if the authenticated user is an admin or has
    manage permissions for the specified registered model.

    Parameters:
    -----------
    model_name : str
        The name of the registered model to check permissions for.
    request : Request
        The FastAPI request object.

    Returns:
    --------
    None
    """
    if not is_admin and not can_manage_registered_model(model_name, current_username):
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage registered model {model_name}")

    return None
