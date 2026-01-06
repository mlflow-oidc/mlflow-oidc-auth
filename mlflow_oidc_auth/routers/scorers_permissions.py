"""MLflow v3 scorer permission routes.

This router implements the scorer permission endpoints introduced in newer MLflow
versions under `/api/3.0/mlflow/permissions/scorers/*`.
"""

from typing import Optional

from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.dependencies import check_scorer_manage_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import GroupPermissionEntry, ScorerPermissionRequest
from mlflow_oidc_auth.store import store

from ._prefix import SCORERS_ROUTER_PREFIX

logger = get_logger()

scorers_permissions_router = APIRouter(
    prefix=SCORERS_ROUTER_PREFIX,
    tags=["scorer permissions"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)


CREATE_SCORER_PERMISSION = "/create"
GET_SCORER_PERMISSION = "/get"
UPDATE_SCORER_PERMISSION = "/update"
DELETE_SCORER_PERMISSION = "/delete"
SCORER_GROUP_PERMISSIONS = "/{experiment_id}/{scorer_name}/groups"


@scorers_permissions_router.post(
    CREATE_SCORER_PERMISSION,
    summary="Create scorer permission",
    description="Create a new scorer permission for a user.",
)
async def create_scorer_permission(
    permission_request: ScorerPermissionRequest = Body(..., description="Scorer permission create request"),
    _: None = Depends(check_scorer_manage_permission),
) -> JSONResponse:
    """Create a scorer permission record."""

    try:
        sp = store.create_scorer_permission(
            experiment_id=str(permission_request.experiment_id),
            scorer_name=str(permission_request.scorer_name),
            username=str(permission_request.username),
            permission=str(permission_request.permission),
        )
        return JSONResponse(content={"scorer_permission": sp.to_json()})
    except MlflowException as e:
        logger.error(f"Error creating scorer permission: {str(e)}")
        if getattr(e, "error_code", None) == RESOURCE_ALREADY_EXISTS:
            raise HTTPException(status_code=409, detail="Scorer permission already exists")
        if getattr(e, "error_code", None) == INVALID_PARAMETER_VALUE:
            raise HTTPException(status_code=400, detail=str(e))
        raise
    except Exception as e:
        logger.error(f"Error creating scorer permission: {e}")
        raise HTTPException(status_code=500, detail="Failed to create scorer permission")


@scorers_permissions_router.get(
    GET_SCORER_PERMISSION,
    summary="Get scorer permission",
    description="Get an existing scorer permission for a user.",
)
async def get_scorer_permission(
    experiment_id: str = Query(..., description="Experiment ID"),
    scorer_name: str = Query(..., description="Scorer name"),
    username: str = Query(..., description="Target username"),
    _: None = Depends(check_scorer_manage_permission),
) -> JSONResponse:
    """Get a scorer permission record."""

    try:
        sp = store.get_scorer_permission(str(experiment_id), str(scorer_name), str(username))
        return JSONResponse(content={"scorer_permission": sp.to_json()})
    except MlflowException as e:
        logger.error(f"Error getting scorer permission: {str(e)}")
        if getattr(e, "error_code", None) == RESOURCE_DOES_NOT_EXIST:
            raise HTTPException(status_code=404, detail="Scorer permission not found")
        if getattr(e, "error_code", None) == INVALID_PARAMETER_VALUE:
            raise HTTPException(status_code=400, detail=str(e))
        raise
    except Exception as e:
        logger.error(f"Error getting scorer permission: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scorer permission")


@scorers_permissions_router.patch(
    UPDATE_SCORER_PERMISSION,
    summary="Update scorer permission",
    description="Update an existing scorer permission for a user.",
)
async def update_scorer_permission(
    permission_request: ScorerPermissionRequest = Body(..., description="Scorer permission update request"),
    _: None = Depends(check_scorer_manage_permission),
) -> JSONResponse:
    """Update a scorer permission record."""

    try:
        store.update_scorer_permission(
            experiment_id=str(permission_request.experiment_id),
            scorer_name=str(permission_request.scorer_name),
            username=str(permission_request.username),
            permission=str(permission_request.permission),
        )
        return JSONResponse(content={})
    except MlflowException as e:
        logger.error(f"Error updating scorer permission: {str(e)}")
        if getattr(e, "error_code", None) == RESOURCE_DOES_NOT_EXIST:
            raise HTTPException(status_code=404, detail="Scorer permission does not exist")
        if getattr(e, "error_code", None) == INVALID_PARAMETER_VALUE:
            raise HTTPException(status_code=400, detail=str(e))
        raise
    except Exception as e:
        logger.error(f"Error updating scorer permission: {e}")
        raise HTTPException(status_code=500, detail="Failed to update scorer permission")


@scorers_permissions_router.delete(
    DELETE_SCORER_PERMISSION,
    summary="Delete scorer permission",
    description="Delete an existing scorer permission for a user.",
)
async def delete_scorer_permission(
    permission_request: Optional[ScorerPermissionRequest] = Body(None, description="Optional scorer permission request body"),
    experiment_id: Optional[str] = Query(None, description="Experiment ID (query fallback)"),
    scorer_name: Optional[str] = Query(None, description="Scorer name (query fallback)"),
    username: Optional[str] = Query(None, description="Target username (query fallback)"),
    _: None = Depends(check_scorer_manage_permission),
) -> JSONResponse:
    """Delete a scorer permission record.

    MLflow's DELETE endpoints sometimes send params via JSON body. We support both
    JSON body and query-parameter forms.
    """

    try:
        req = permission_request
        resolved_experiment_id = (
            str(req.experiment_id) if req and req.experiment_id is not None else (str(experiment_id) if experiment_id is not None else None)
        )
        resolved_scorer_name = str(req.scorer_name) if req and req.scorer_name is not None else (str(scorer_name) if scorer_name is not None else None)
        resolved_username = str(req.username) if req and req.username is not None else (str(username) if username is not None else None)

        if not resolved_experiment_id or not resolved_scorer_name or not resolved_username:
            raise HTTPException(status_code=400, detail="Missing required parameters")

        store.delete_scorer_permission(resolved_experiment_id, resolved_scorer_name, resolved_username)
        return JSONResponse(content={})
    except MlflowException as e:
        logger.error(f"Error deleting scorer permission: {str(e)}")
        if getattr(e, "error_code", None) == RESOURCE_DOES_NOT_EXIST:
            raise HTTPException(status_code=404, detail="Scorer permission does not exist")
        if getattr(e, "error_code", None) == INVALID_PARAMETER_VALUE:
            raise HTTPException(status_code=400, detail=str(e))
        raise
    except Exception as e:
        logger.error(f"Error deleting scorer permission: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete scorer permission")


@scorers_permissions_router.get(
    SCORER_GROUP_PERMISSIONS,
    response_model=List[GroupPermissionEntry],
    summary="List groups with permissions for a scorer",
    description="Retrieves a list of groups that have permissions for the specified scorer.",
)
async def list_scorer_groups(
    experiment_id: str = Path(..., description="Experiment ID"),
    scorer_name: str = Path(..., description="Scorer name"),
    _: None = Depends(check_scorer_manage_permission),
) -> List[GroupPermissionEntry]:
    """List groups with explicit permissions for a scorer."""

    try:
        groups = store.scorer_group_repo.list_groups_for_scorer(str(experiment_id), str(scorer_name))
        return [GroupPermissionEntry(name=name, permission=permission) for name, permission in groups]
    except Exception as e:
        logger.error(f"Error listing scorer group permissions: {e}")
        raise HTTPException(status_code=500, detail="Failed to list scorer group permissions")


# Backwards-compatible alias within this package (router package imports this name).
scorers_router = scorers_permissions_router
