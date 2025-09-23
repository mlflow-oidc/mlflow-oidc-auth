from typing import List

from fastapi import APIRouter, Depends, Path
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.dependencies import check_experiment_manage_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import ExperimentSummary, ExperimentUserPermission
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import can_manage_experiment, get_is_admin, get_username

from ._prefix import EXPERIMENT_PERMISSIONS_ROUTER_PREFIX

logger = get_logger()

experiment_permissions_router = APIRouter(
    prefix=EXPERIMENT_PERMISSIONS_ROUTER_PREFIX,
    tags=["permissions"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)

LIST_EXPERIMENTS = ""
EXPERIMENT_USER_PERMISSIONS = "/{experiment_id}/users"


@experiment_permissions_router.get(
    EXPERIMENT_USER_PERMISSIONS,
    response_model=List[ExperimentUserPermission],
    summary="List users with permissions for an experiment",
    description="Retrieves a list of users who have permissions for the specified experiment.",
)
async def get_experiment_users(
    experiment_id: str = Path(..., description="The experiment ID to get permissions for"), _: str = Depends(check_experiment_manage_permission)
) -> List[ExperimentUserPermission]:
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
    List[ExperimentUserPermission]
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
                ExperimentUserPermission(
                    username=user.username,
                    permission=user_experiment_permissions[experiment_id],
                    kind="service-account" if user.is_service_account else "user",
                )
            )

    return users_with_permissions


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

    # Filter experiments based on user permissions
    if is_admin:
        # Admins can see all experiments
        manageable_experiments = all_experiments
    else:
        # Regular users only see experiments they can manage
        manageable_experiments = [experiment for experiment in all_experiments if can_manage_experiment(experiment.experiment_id, username)]

    # Format the response
    return [ExperimentSummary(name=experiment.name, id=experiment.experiment_id, tags=experiment.tags) for experiment in manageable_experiments]
