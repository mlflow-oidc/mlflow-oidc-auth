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


class FailedPermissionCleanup(ResponseModel):
    """An experiment that was permanently deleted but whose permission rows could not be removed."""

    experiment_id: str
    error: str


class TrashCleanupResponse(ResponseModel):
    """``POST /oidc/trash/cleanup``. ``failed_*`` are present only when something failed.

    A 200 with ``failed_*`` is a partial result: the entities listed there were kept, everything in
    ``deleted_*`` is gone.
    """

    __absent_fields__ = frozenset({"failed_runs", "failed_experiments", "failed_permission_cleanups"})

    deleted_runs: List[str]
    deleted_experiments: List[str]
    total_deleted_runs: int
    total_deleted_experiments: int
    failed_runs: Optional[List[FailedRun]] = None
    failed_experiments: Optional[List[FailedExperiment]] = None
    #: Experiments that were deleted (they are in ``deleted_experiments``) but whose permission rows
    #: could not be removed; ``POST /oidc/trash/permissions/sweep`` removes them later.
    failed_permission_cleanups: Optional[List[FailedPermissionCleanup]] = None


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


class PermissionSweepResponse(ResponseModel):
    """``POST /oidc/trash/permissions/sweep``.

    Attributes:
        dry_run: True when nothing was deleted.
        checked_experiments: Experiment ids decided in this call (those after the `after` cursor, up to the lookup budget).
        missing_experiments: Ids the tracking store definitively does not have (in any workspace).
        unresolved_experiments: Ids whose existence could not be established; their rows are kept.
        truncated: True when the lookup budget ran out before the last id; call again with `after=next_after`.
        next_after: When truncated, the last id fully decided in this call; None otherwise.
        removed_rows: Grant rows deleted (always 0 for a dry run).
        replica_reads: True when the tracking store reads from a read replica: a lagging replica reports a just-created experiment
            as missing, so `missing_experiments` of a dry run may include false positives (a deleting sweep is refused with 409).
    """

    dry_run: bool
    checked_experiments: int
    missing_experiments: List[str]
    unresolved_experiments: List[str]
    truncated: bool
    removed_rows: int
    replica_reads: bool = False
    next_after: Optional[str] = None


#: The 400/404 bodies every trash endpoint can return, for ``responses=``.
TRASH_ERROR_RESPONSES = {
    400: {"model": TrashErrorResponse, "description": "Invalid request"},
    404: {"model": TrashErrorResponse, "description": "Resource not found"},
}

# Cleanup answers its 500s in the same ``{"error": ...}`` shape: a failed lookup of candidates
# ("Failed to retrieve deleted runs/experiments") means nothing was deleted.
TRASH_CLEANUP_ERROR_RESPONSES = {
    **TRASH_ERROR_RESPONSES,
    409: {
        "model": TrashErrorResponse,
        "description": "A deleting permission sweep was refused: the tracking store reads from a replica, or the workspace store is not MLflow's built-in one",
    },
    500: {"model": TrashErrorResponse, "description": "Cleanup failed; after a failed lookup of candidates nothing was deleted"},
}
