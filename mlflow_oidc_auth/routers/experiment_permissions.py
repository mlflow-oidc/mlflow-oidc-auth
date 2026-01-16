from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.dependencies import check_experiment_manage_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import ExperimentSummary, GroupPermissionEntry, UserPermission
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import get_is_admin, get_username
from mlflow_oidc_auth.utils.batch_permissions import filter_manageable_experiments

from ._prefix import EXPERIMENT_PERMISSIONS_ROUTER_PREFIX

logger = get_logger()

experiment_permissions_router = APIRouter(
    prefix=EXPERIMENT_PERMISSIONS_ROUTER_PREFIX,
    tags=["experiment permissions"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)

LIST_EXPERIMENTS = ""
EXPERIMENT_USER_PERMISSIONS = "/{experiment_id}/users"
EXPERIMENT_GROUP_PERMISSIONS = "/{experiment_id}/groups"


@experiment_permissions_router.get(
    EXPERIMENT_USER_PERMISSIONS,
    response_model=List[UserPermission],
    summary="List users with permissions for an experiment",
    description="Retrieves a list of users who have permissions for the specified experiment.",
)
async def get_experiment_users(
    experiment_id: str = Path(..., description="The experiment ID to get permissions for"), _: str = Depends(check_experiment_manage_permission)
) -> List[UserPermission]:
    """
    List all users with permissions for a specific experiment.

    This endpoint returns all users who have explicitly assigned permissions
    for the specified experiment. The requesting user must be an admin or
    have management permissions for the experiment.

    Parameters:
    -----------
    experiment_id : str
        The ID of the experiment to get user permissions for.
    _ : str
        The authenticated username (injected by dependency, not used directly).

    Returns:
    --------
    List[UserPermission]
        A list of users with their permission levels for the experiment.

    Raises:
    -------
    HTTPException
        If the user doesn't have permission to access this information.
    """
    all_users = store.list_users(all=True)

    # Filter and format users with permissions for this experiment
    users_with_permissions = []

    for user in all_users:
        # Get experiment permissions for this user
        user_experiment_permissions = {str(exp.experiment_id): exp.permission for exp in (user.experiment_permissions or [])}

        # Check if user has permission for this experiment
        if experiment_id in user_experiment_permissions:
            users_with_permissions.append(
                UserPermission(
                    name=user.username,
                    permission=user_experiment_permissions[experiment_id],
                    kind="service-account" if user.is_service_account else "user",
                )
            )

    return users_with_permissions


@experiment_permissions_router.get(
    EXPERIMENT_GROUP_PERMISSIONS,
    response_model=List[GroupPermissionEntry],
    summary="List groups with permissions for an experiment",
    description="Retrieves a list of groups that have permissions for the specified experiment.",
)
async def get_experiment_groups(
    experiment_id: str = Path(..., description="The experiment ID to get group permissions for"),
    _: None = Depends(check_experiment_manage_permission),
) -> List[GroupPermissionEntry]:
    """List all groups with permissions for a specific experiment."""

    try:
        groups = store.experiment_group_repo.list_groups_for_experiment(str(experiment_id))
        return [GroupPermissionEntry(name=name, permission=permission) for name, permission in groups]
    except Exception as e:
        logger.error(f"Error retrieving experiment group permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve experiment group permissions")


@experiment_permissions_router.get(
    LIST_EXPERIMENTS,
    response_model=List[ExperimentSummary],
    summary="List accessible experiments",
    description="Retrieves a list of MLflow experiments that the user has access to.",
)
async def list_experiments(username: str = Depends(get_username), is_admin: bool = Depends(get_is_admin)) -> List[ExperimentSummary]:
    """
    List experiments accessible to the authenticated user.

    This endpoint returns experiments based on user permissions:
    - Administrators can see all experiments
    - Regular users only see experiments they have management permissions for

    Parameters:
    -----------
    username : str
        The authenticated username (injected by dependency).
    is_admin : bool
        Whether the user has admin privileges (injected by dependency).

    Returns:
    --------
    List[ExperimentSummary]
        A list of experiment summaries containing name, ID, and tags.

    Raises:
    -------
    HTTPException
        If there is an error retrieving or processing the experiments.
    """
    tracking_store = _get_tracking_store()
    all_experiments = tracking_store.search_experiments()

    # Filter experiments based on user permissions (batch resolution for efficiency)
    if is_admin:
        # Admins can see all experiments
        manageable_experiments = all_experiments
    else:
        # Regular users only see experiments they can manage
        manageable_experiments = filter_manageable_experiments(username, all_experiments)

    # Format the response
    return [ExperimentSummary(name=experiment.name, id=experiment.experiment_id, tags=experiment.tags) for experiment in manageable_experiments]
