"""Response models for the trash router (#458).

The trash router returns ``JSONResponse`` objects; these document the bodies it already builds
and list exactly those fields.
"""

from typing import Dict, List, Optional

from pydantic import Field

from mlflow_oidc_auth.models._base import ResponseModel


class TrashErrorResponse(ResponseModel):
    """The ``{"error": ...}`` body the trash endpoints return for a 400 or 404."""

    error: str


class DeletedExperiment(ResponseModel):
    """A soft-deleted experiment."""

    experiment_id: str
    name: str
    lifecycle_stage: str
    artifact_location: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    creation_time: Optional[int] = None
    last_update_time: Optional[int] = None


class DeletedExperimentListResponse(ResponseModel):
    """``GET /oidc/trash/experiments``."""

    deleted_experiments: List[DeletedExperiment]


class DeletedRun(ResponseModel):
    """A soft-deleted run."""

    run_id: str
    experiment_id: str
    run_name: Optional[str] = None
    status: Optional[str] = None
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    lifecycle_stage: str


class DeletedRunListResponse(ResponseModel):
    """``GET /oidc/trash/runs``."""

    deleted_runs: List[DeletedRun]


class FailedRun(ResponseModel):
    """A run the cleanup could not delete."""

    run_id: str
    error: str


class FailedExperiment(ResponseModel):
    """An experiment the cleanup could not delete."""

    experiment_id: str
    error: str


class TrashCleanupResponse(ResponseModel):
    """``POST /oidc/trash/cleanup``. ``failed_*`` are present only when something failed."""

    __absent_fields__ = frozenset({"failed_runs", "failed_experiments"})

    deleted_runs: List[str]
    deleted_experiments: List[str]
    total_deleted_runs: int
    total_deleted_experiments: int
    failed_runs: Optional[List[FailedRun]] = None
    failed_experiments: Optional[List[FailedExperiment]] = None


class RestoredExperiment(ResponseModel):
    """The experiment a restore brought back."""

    experiment_id: str
    name: str
    lifecycle_stage: str
    last_update_time: Optional[int] = None


class RestoredExperimentResponse(ResponseModel):
    """``POST /oidc/trash/experiments/{experiment_id}/restore``."""

    experiment: RestoredExperiment


class RestoredRun(ResponseModel):
    """The run a restore brought back."""

    run_id: str
    experiment_id: str
    run_name: Optional[str] = None
    status: Optional[str] = None
    lifecycle_stage: str


class RestoredRunResponse(ResponseModel):
    """``POST /oidc/trash/runs/{run_id}/restore``."""

    run: RestoredRun


#: The 400/404 bodies every trash endpoint can return, for ``responses=``.
TRASH_ERROR_RESPONSES = {
    400: {"model": TrashErrorResponse, "description": "Invalid request"},
    404: {"model": TrashErrorResponse, "description": "Resource not found"},
}
