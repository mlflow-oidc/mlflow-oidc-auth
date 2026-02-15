"""
FastAPI dependency functions for the MLflow OIDC Auth Plugin.

This module provides dependency functions that can be used with FastAPI's
dependency injection system for common authorization and validation tasks.
"""

from fastapi import Depends, Request, HTTPException, Path

from mlflow_oidc_auth.utils import can_manage_experiment, can_manage_registered_model, can_manage_scorer, get_is_admin, get_username


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


async def check_prompt_manage_permission(
    prompt_name: str = Path(..., description="Prompt name"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> None:
    """Check if the current user can manage the specified prompt.

    This mirrors registered model checks because prompts are stored as registered models
    in the system. Users with admin rights or explicit manage permission can proceed.
    """

    if not is_admin and not can_manage_registered_model(prompt_name, current_username):
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage {prompt_name}")

    return None


async def check_gateway_endpoint_manage_permission(
    name: str = Path(..., description="Gateway endpoint name"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> None:
    """Check if the current user can manage the specified gateway endpoint.

    This mirrors gateway checks but targets endpoint-scoped permissions.
    """
    from mlflow_oidc_auth.utils.permissions import can_manage_gateway_endpoint

    if not is_admin and not can_manage_gateway_endpoint(name, current_username):
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage endpoint {name}")

    return None


async def check_gateway_secret_manage_permission(
    name: str = Path(..., description="Gateway secret name"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> None:
    """Check if the current user can manage the specified gateway secret.

    This mirrors gateway checks but targets secret-scoped permissions.
    """
    from mlflow_oidc_auth.utils.permissions import can_manage_gateway_secret

    if not is_admin and not can_manage_gateway_secret(name, current_username):
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage secret {name}")

    return None


async def check_gateway_model_definition_manage_permission(
    name: str = Path(..., description="Gateway model definition name"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> None:
    """Check if the current user can manage the specified gateway model definition.

    This mirrors gateway checks but targets model definition-scoped permissions.
    """
    from mlflow_oidc_auth.utils.permissions import can_manage_gateway_model_definition

    if not is_admin and not can_manage_gateway_model_definition(name, current_username):
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage model definition {name}")

    return None


async def check_scorer_manage_permission(
    request: Request,
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> None:
    """Check if the current user can manage the scorer from the incoming request.

    This dependency supports MLflow v3 scorer permission routes:
    - GET: parameters in query string
    - POST/PATCH/DELETE: parameters in JSON body (with query fallback)
    """

    experiment_id = request.query_params.get("experiment_id") or request.path_params.get("experiment_id")
    scorer_name = request.query_params.get("scorer_name") or request.path_params.get("scorer_name")

    if request.method in {"POST", "PATCH", "DELETE"}:
        try:
            body = await request.json()
        except Exception:
            body = None

        if isinstance(body, dict):
            experiment_id = experiment_id or body.get("experiment_id")
            scorer_name = scorer_name or body.get("scorer_name")

    if not experiment_id or not scorer_name:
        raise HTTPException(status_code=400, detail="Missing required parameters: experiment_id and scorer_name")

    if not is_admin and not can_manage_scorer(str(experiment_id), str(scorer_name), str(current_username)):
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage scorer {scorer_name}")

    return None
