"""MLflow v3 scorer permission routes.

This router implements the scorer permission endpoints introduced in newer MLflow
versions under `/api/3.0/mlflow/permissions/scorers/*`.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.dependencies import check_scorer_manage_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import GroupPermissionEntry, ScorerSummary, UserPermission
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import get_is_admin, get_username
from mlflow_oidc_auth.utils.permissions import can_manage_scorer

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

LIST_SCORERS = "/{experiment_id}"
SCORER_USER_PERMISSIONS = "/{experiment_id}/{scorer_name:path}/users"
SCORER_GROUP_PERMISSIONS = "/{experiment_id}/{scorer_name:path}/groups"


@scorers_permissions_router.get(
    LIST_SCORERS,
    summary="List accessible scorers",
    description="Retrieves scorers for an experiment that the requester can manage.",
)
async def list_scorers(
    experiment_id: str = Path(..., description="The experiment ID owning the scorers"),
    username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[ScorerSummary]:
    """List scorers for an experiment filtered by permissions.

    Administrators see every scorer in the experiment. Non-admins only see scorers
    they can manage according to effective scorer permissions.
    """

    try:
        tracking_store = _get_tracking_store()
        all_scorers = tracking_store.list_scorers(experiment_id)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to list scorers for experiment {experiment_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve scorers") from exc

    if is_admin:
        visible_scorers = all_scorers
    else:
        visible_scorers = [scorer for scorer in all_scorers if can_manage_scorer(str(experiment_id), scorer.scorer_name, username)]

    return [
        ScorerSummary(
            experiment_id=scorer.experiment_id,
            name=scorer.scorer_name,
            version=scorer.scorer_version,
            creation_time=scorer.creation_time,
            scorer_id=scorer.scorer_id,
        )
        for scorer in visible_scorers
    ]


@scorers_permissions_router.get(
    SCORER_USER_PERMISSIONS,
    response_model=List[UserPermission],
    summary="List users with permissions for a scorer",
    description="Retrieves users that have explicit permissions for the given scorer.",
)
async def get_scorer_users(
    experiment_id: str = Path(..., description="The experiment ID owning the scorer"),
    scorer_name: str = Path(..., description="The scorer name"),
    _: None = Depends(check_scorer_manage_permission),
) -> List[UserPermission]:
    """List all users with explicit permissions for a scorer.

    The dependency enforces that only admins or users who can manage the scorer
    may access this information.
    """

    try:
        users = store.list_users(all=True)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to list scorer users for {experiment_id}/{scorer_name}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve scorer user permissions") from exc

    scorer_users: List[UserPermission] = []
    for user in users:
        scorer_permissions = {
            (str(permission.experiment_id), str(permission.scorer_name)): str(permission.permission)
            for permission in getattr(user, "scorer_permissions", []) or []
        }

        if (str(experiment_id), str(scorer_name)) in scorer_permissions:
            scorer_users.append(
                UserPermission(
                    name=user.username,
                    permission=scorer_permissions[(str(experiment_id), str(scorer_name))],
                    kind="service-account" if user.is_service_account else "user",
                )
            )

    return scorer_users


@scorers_permissions_router.get(
    SCORER_GROUP_PERMISSIONS,
    response_model=List[GroupPermissionEntry],
    summary="List groups with permissions for a scorer",
    description="Retrieves groups that have explicit permissions for the given scorer.",
)
async def get_scorer_groups(
    experiment_id: str = Path(..., description="The experiment ID owning the scorer"),
    scorer_name: str = Path(..., description="The scorer name"),
    _: None = Depends(check_scorer_manage_permission),
) -> List[GroupPermissionEntry]:
    """List all groups with explicit permissions for a scorer.

    Errors during lookup are surfaced as HTTP 500 responses with a concise message.
    """

    try:
        groups = store.scorer_group_repo.list_groups_for_scorer(str(experiment_id), str(scorer_name))
        return [GroupPermissionEntry(name=name, permission=permission) for name, permission in groups]
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to list scorer groups for {experiment_id}/{scorer_name}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve scorer group permissions") from exc
