"""
FastAPI dependency functions for the MLflow OIDC Auth Plugin.

This module provides dependency functions that can be used with FastAPI's
dependency injection system for common authorization and validation tasks.
"""

from fastapi import Depends, Request, HTTPException, Path

from mlflow_oidc_auth.utils import can_manage_experiment, get_username, get_is_admin, can_manage_registered_model


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
    try:
        username = await get_username(request=request)
        is_admin = await get_is_admin(request=request)
    except Exception:
        # Keep behavior simple for callers: admin-only endpoints always respond
        # with 403 when the user cannot be identified or checked.
        raise HTTPException(status_code=403, detail="Administrator privileges required for this operation")

    if not is_admin:
        raise HTTPException(status_code=403, detail="Administrator privileges required for this operation")

    return username


async def check_experiment_manage_permission(
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


async def check_registered_model_manage_permission(
    name: str = Path(..., description="Registered model or prompt name"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
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
    if not is_admin and not can_manage_registered_model(name, current_username):
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage {name}")

    return None
