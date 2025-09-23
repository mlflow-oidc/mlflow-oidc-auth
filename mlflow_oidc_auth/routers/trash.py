import re
import warnings
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from mlflow.entities import ViewType
from mlflow.entities.lifecycle_stage import LifecycleStage
from mlflow.exceptions import InvalidUrlException, MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE
from mlflow.store.artifact.artifact_repository_registry import get_artifact_repository
from mlflow.tracking import _get_store
from mlflow.utils.time import get_current_time_millis

from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.logger import get_logger

from ._prefix import TRASH_ROUTER_PREFIX

logger = get_logger()

trash_router = APIRouter(
    prefix=TRASH_ROUTER_PREFIX,
    tags=["trash"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)


EXPERIMENTS = "/experiments"
CLEANUP = "/cleanup"


@trash_router.get(
    EXPERIMENTS,
    summary="List deleted experiments",
    description="Retrieves a list of deleted experiments in the MLflow tracking server.",
)
async def list_deleted_experiments(
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    List all deleted experiments.

    This endpoint returns all experiments that have been deleted (moved to trash).
    The requesting user must be an admin.

    Parameters:
    -----------
    admin_username : str
        The authenticated admin username (injected by dependency).

    Returns:
    --------
    JSONResponse
        A JSON response containing a list of deleted experiments with their details.

    Raises:
    -------
    HTTPException
        403 - If the user does not have admin permissions.
    """
    try:
        # Fetch all deleted experiments using view_type=2 for DELETED_ONLY
        from mlflow_oidc_auth.utils.data_fetching import fetch_all_experiments

        deleted_experiments = fetch_all_experiments(view_type=2)  # ViewType.DELETED_ONLY

        # Format the response data
        experiments_list = []
        for exp in deleted_experiments:
            experiment_data = {
                "experiment_id": exp.experiment_id,
                "name": exp.name,
                "lifecycle_stage": exp.lifecycle_stage,
                "artifact_location": exp.artifact_location,
                "tags": exp.tags if exp.tags else {},
                "creation_time": exp.creation_time,
                "last_update_time": exp.last_update_time,
            }
            experiments_list.append(experiment_data)

        logger.info(f"Admin user '{admin_username}' listed {len(experiments_list)} deleted experiments.")
        return JSONResponse(content={"deleted_experiments": experiments_list})

    except Exception as e:
        logger.error(f"Error listing deleted experiments for admin '{admin_username}': {str(e)}")
        return JSONResponse(status_code=500, content={"error": "Failed to retrieve deleted experiments."})


@trash_router.post(
    CLEANUP,
    summary="Permanently delete trashed entities",
    description="Permanently deletes entities (experiments, runs) that are in the trash based on specified criteria.",
)
async def permanently_delete_all_trashed_entities(
    admin_username: str = Depends(check_admin_permission),
    older_than: Optional[str] = Query(
        None, description="Remove entities older than the specified time limit (e.g., '1d2h3m4s', '7d'). Float values are supported."
    ),
    run_ids: Optional[str] = Query(None, description="Comma-separated list of specific run IDs to permanently delete"),
    experiment_ids: Optional[str] = Query(None, description="Comma-separated list of specific experiment IDs to permanently delete (including all their runs)"),
) -> JSONResponse:
    """
    Permanently delete entities in the trash.

    This endpoint permanently deletes entities (experiments, runs) that are currently
    in the trash. The requesting user must be an admin. This is equivalent to
    MLflow's 'mlflow gc' command.

    Parameters:
    -----------
    admin_username : str
        The authenticated admin username (injected by dependency).
    older_than : Optional[str]
        Time limit for deletion (e.g., '1d', '2h', '30m', '1d2h3m4s').
    run_ids : Optional[str]
        Comma-separated list of specific run IDs to delete.
    experiment_ids : Optional[str]
        Comma-separated list of specific experiment IDs to delete.

    Returns:
    --------
    JSONResponse
        A JSON response indicating the result of the cleanup operation.

    Raises:
    -------
    HTTPException
        403 - If the user does not have admin permissions.
        500 - If the cleanup operation fails.
    """
    try:
        # Get the backend store
        backend_store = _get_store()

        # Check if the store supports hard deletion
        if not hasattr(backend_store, "_hard_delete_run"):
            logger.error("Backend store does not support hard deletion of runs")
            return JSONResponse(status_code=400, content={"error": "Backend store does not support permanent deletion of runs"})

        skip_experiments = False
        if not hasattr(backend_store, "_hard_delete_experiment"):
            warnings.warn(
                "The backend store does not allow hard-deleting experiments. Experiments will be skipped.",
                FutureWarning,
                stacklevel=2,
            )
            skip_experiments = True
            logger.warning("Backend store does not support hard deletion of experiments - skipping experiments")

        # Parse time delta if older_than is provided
        time_delta = 0
        if older_than is not None:
            try:
                time_delta = _parse_time_delta(older_than)
            except MlflowException as e:
                logger.error(f"Invalid time format '{older_than}': {str(e)}")
                return JSONResponse(status_code=400, content={"error": f"Invalid time format"})

        # Get deleted runs that match the time criteria
        try:
            deleted_run_ids_older_than = backend_store._get_deleted_runs(older_than=time_delta)
        except Exception as e:
            logger.warning(f"Could not fetch deleted runs by time criteria: {str(e)}")
            deleted_run_ids_older_than = []

        # Determine which run IDs to delete
        target_run_ids = []
        if run_ids:
            target_run_ids = [rid.strip() for rid in run_ids.split(",")]
        else:
            target_run_ids = deleted_run_ids_older_than

        # Handle experiment deletion
        target_experiment_ids = []
        time_threshold = get_current_time_millis() - time_delta

        if not skip_experiments:
            if experiment_ids:
                # Validate specified experiment IDs
                target_experiment_ids = [eid.strip() for eid in experiment_ids.split(",")]
                experiments = []

                for exp_id in target_experiment_ids:
                    try:
                        exp = backend_store.get_experiment(exp_id)
                        experiments.append(exp)
                    except Exception as e:
                        logger.error(f"Could not fetch experiment {exp_id}: {str(e)}")
                        return JSONResponse(status_code=404, content={"error": f"Experiment {exp_id} not found"})

                # Ensure experiments are deleted
                active_experiment_ids = [e.experiment_id for e in experiments if e.lifecycle_stage != LifecycleStage.DELETED]
                if active_experiment_ids:
                    return JSONResponse(status_code=400, content={"error": f"Experiments {active_experiment_ids} are not in deleted lifecycle stage"})

                # Check age requirements
                if older_than:
                    non_old_experiment_ids = [e.experiment_id for e in experiments if e.last_update_time is None or e.last_update_time >= time_threshold]
                    if non_old_experiment_ids:
                        return JSONResponse(status_code=400, content={"error": f"Experiments {non_old_experiment_ids} are not older than {older_than}"})
            else:
                # Get all deleted experiments
                filter_string = f"last_update_time < {time_threshold}" if older_than else None

                def fetch_experiments(token=None):
                    try:
                        page = backend_store.search_experiments(
                            view_type=ViewType.DELETED_ONLY,
                            filter_string=filter_string,
                            page_token=token,
                        )
                        return (page + fetch_experiments(page.token)) if page.token else page
                    except Exception:
                        return []

                experiment_list = fetch_experiments()
                target_experiment_ids = [exp.experiment_id for exp in experiment_list]

            # Get runs from target experiments
            if target_experiment_ids:

                def fetch_runs(token=None):
                    try:
                        page = backend_store.search_runs(
                            experiment_ids=target_experiment_ids,
                            filter_string="",
                            run_view_type=ViewType.DELETED_ONLY,
                            page_token=token,
                        )
                        return (page + fetch_runs(page.token)) if page.token else page
                    except Exception:
                        return []

                runs_from_experiments = fetch_runs()
                target_run_ids.extend([run.info.run_id for run in runs_from_experiments])

        # Delete runs
        deleted_runs = []
        failed_runs = []

        for run_id in set(target_run_ids):
            try:
                run = backend_store.get_run(run_id)

                # Validate run is deleted
                if run.info.lifecycle_stage != LifecycleStage.DELETED:
                    failed_runs.append({"run_id": run_id, "error": "Run is not in deleted lifecycle stage"})
                    continue

                # Check age requirement
                if older_than and run_id not in deleted_run_ids_older_than:
                    failed_runs.append({"run_id": run_id, "error": f"Run is not older than {older_than}"})
                    continue

                # Delete artifacts
                try:
                    artifact_repo = get_artifact_repository(run.info.artifact_uri)
                    artifact_repo.delete_artifacts()
                except InvalidUrlException as e:
                    logger.warning(f"Could not delete artifacts for run {run_id}: {str(e)}")
                except Exception as e:
                    logger.warning(f"Error deleting artifacts for run {run_id}: {str(e)}")

                # Hard delete the run
                backend_store._hard_delete_run(run_id)
                deleted_runs.append(run_id)
                logger.info(f"Permanently deleted run {run_id}")

            except Exception as e:
                logger.error(f"Error deleting run {run_id}: {str(e)}")
                failed_runs.append({"run_id": run_id, "error": str(e)})

        # Delete experiments
        deleted_experiments = []
        failed_experiments = []

        if not skip_experiments:
            for experiment_id in target_experiment_ids:
                try:
                    backend_store._hard_delete_experiment(experiment_id)
                    deleted_experiments.append(experiment_id)
                    logger.info(f"Permanently deleted experiment {experiment_id}")
                except Exception as e:
                    logger.error(f"Error deleting experiment {experiment_id}: {str(e)}")
                    failed_experiments.append({"experiment_id": experiment_id, "error": str(e)})

        # Prepare response
        response_data = {
            "deleted_runs": deleted_runs,
            "deleted_experiments": deleted_experiments,
            "total_deleted_runs": len(deleted_runs),
            "total_deleted_experiments": len(deleted_experiments),
        }

        if failed_runs:
            response_data["failed_runs"] = failed_runs

        if failed_experiments:
            response_data["failed_experiments"] = failed_experiments

        logger.info(f"Admin user '{admin_username}' completed cleanup: " f"{len(deleted_runs)} runs, {len(deleted_experiments)} experiments deleted")

        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error(f"Error in cleanup operation for admin '{admin_username}': {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"Cleanup operation failed"})


def _parse_time_delta(older_than: str) -> int:
    """
    Parse time delta string (e.g., '1d2h3m4s') and return milliseconds.

    Parameters:
    -----------
    older_than : str
        Time string in format #d#h#m#s

    Returns:
    --------
    int
        Time delta in milliseconds

    Raises:
    -------
    MlflowException
        If the time format is invalid
    """
    regex = re.compile(r"^((?P<days>[\.\d]+?)d)?((?P<hours>[\.\d]+?)h)?((?P<minutes>[\.\d]+?)m)" r"?((?P<seconds>[\.\d]+?)s)?$")
    parts = regex.match(older_than)
    if parts is None:
        raise MlflowException(
            f"Could not parse any time information from '{older_than}'. " "Examples of valid strings: '8h', '2d8h5m20s', '2m4s'",
            error_code=INVALID_PARAMETER_VALUE,
        )
    time_params = {name: float(param) for name, param in parts.groupdict().items() if param}
    time_delta = int(timedelta(**time_params).total_seconds() * 1000)
    return time_delta
