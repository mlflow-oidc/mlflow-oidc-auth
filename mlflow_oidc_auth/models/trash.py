"""Response models for the trash router (#458).

The trash router returns ``JSONResponse`` objects; these document the bodies it already builds
and list exactly those fields.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TrashErrorResponse(BaseModel):
    """The ``{"error": ...}`` body the trash endpoints return for a 400 or 404."""

    error: str


class DeletedExperiment(BaseModel):
    """A soft-deleted experiment."""

    experiment_id: str
    name: str
    lifecycle_stage: str
    artifact_location: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    creation_time: Optional[int] = None
    last_update_time: Optional[int] = None


class DeletedExperimentListResponse(BaseModel):
    """``GET /oidc/trash/experiments``."""

    deleted_experiments: List[DeletedExperiment]


class DeletedRun(BaseModel):
    """A soft-deleted run."""

    run_id: str
    experiment_id: str
    run_name: Optional[str] = None
    status: Optional[str] = None
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    lifecycle_stage: str


class DeletedRunListResponse(BaseModel):
    """``GET /oidc/trash/runs``."""

    deleted_runs: List[DeletedRun]


class FailedRun(BaseModel):
    """A run the cleanup could not delete."""

    run_id: str
    error: str


class FailedExperiment(BaseModel):
    """An experiment the cleanup could not delete."""

    experiment_id: str
    error: str


class TrashCleanupResponse(BaseModel):
    """``POST /oidc/trash/cleanup``. ``failed_*`` are present only when something failed."""

    deleted_runs: List[str]
    deleted_experiments: List[str]
    total_deleted_runs: int
    total_deleted_experiments: int
    failed_runs: Optional[List[FailedRun]] = None
    failed_experiments: Optional[List[FailedExperiment]] = None


class RestoredExperiment(BaseModel):
    """The experiment a restore brought back."""

    experiment_id: str
    name: str
    lifecycle_stage: str
    last_update_time: Optional[int] = None


class RestoredExperimentResponse(BaseModel):
    """``POST /oidc/trash/experiments/{experiment_id}/restore``."""

    experiment: RestoredExperiment


class RestoredRun(BaseModel):
    """The run a restore brought back."""

    run_id: str
    experiment_id: str
    run_name: Optional[str] = None
    status: Optional[str] = None
    lifecycle_stage: str


class RestoredRunResponse(BaseModel):
    """``POST /oidc/trash/runs/{run_id}/restore``."""

    run: RestoredRun


#: The 400/404 bodies every trash endpoint can return, for ``responses=``.
TRASH_ERROR_RESPONSES = {
    400: {"model": TrashErrorResponse, "description": "Invalid request"},
    404: {"model": TrashErrorResponse, "description": "Resource not found"},
}
