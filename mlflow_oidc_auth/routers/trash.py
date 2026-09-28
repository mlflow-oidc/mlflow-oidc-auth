import os
import posixpath
import re
import urllib.parse
import warnings
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from mlflow.entities import ViewType
from mlflow.entities.lifecycle_stage import LifecycleStage
from mlflow.exceptions import InvalidUrlException, MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE
from mlflow.store.artifact.artifact_repository_registry import get_artifact_repository
from mlflow.tracking import _get_store
from mlflow.utils.time import get_current_time_millis

from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.utils.data_fetching import fetch_all_experiments

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
RUNS = "/runs"
CLEANUP = "/cleanup"
RESTORE_EXPERIMENT = f"{EXPERIMENTS}/{{experiment_id}}/restore"
RESTORE_RUN = f"{RUNS}/{{run_id}}/restore"


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
        deleted_experiments = fetch_all_experiments(view_type=ViewType.DELETED_ONLY)

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

    except Exception:
        logger.exception("Error listing deleted experiments for admin %s", admin_username)
        raise HTTPException(status_code=500, detail="Failed to retrieve deleted experiments")


@trash_router.get(
    RUNS,
    summary="List deleted runs",
    description="Retrieves a list of deleted runs in the MLflow tracking server.",
)
async def list_deleted_runs(
    admin_username: str = Depends(check_admin_permission),
    experiment_ids: Optional[str] = Query(None, description="Comma-separated list of experiment IDs to scope deleted runs"),
    older_than: Optional[str] = Query(
        None,
        description="Only include runs deleted more than this duration ago (e.g., '1d2h', '7d').",
    ),
) -> JSONResponse:
    """
    List deleted runs with optional experiment and age filters.

    Parameters
    ----------
    admin_username : str
        The authenticated admin username (injected by dependency).
    experiment_ids : Optional[str]
        Comma-separated list of experiment IDs to filter runs by.
    older_than : Optional[str]
        Time window threshold; runs deleted more recently than this are excluded when the backend
        supports `_get_deleted_runs`.
    """
    backend_store = _get_store()
    experiment_filter = _split_csv(experiment_ids)

    try:
        time_delta = _parse_time_delta(older_than) if older_than else 0
    except MlflowException as e:
        logger.error(f"Invalid time format '{older_than}': {str(e)}")
        return JSONResponse(status_code=400, content={"error": "Invalid time format"})

    try:
        run_ids: List[str] = []

        if hasattr(backend_store, "_get_deleted_runs"):
            run_ids = backend_store._get_deleted_runs(older_than=time_delta)
        else:
            # Fallback to search without age filtering when the backend lacks _get_deleted_runs
            target_experiment_ids = experiment_filter if experiment_filter else [exp.experiment_id for exp in fetch_all_experiments(view_type=ViewType.ALL)]

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

            run_ids = [run.info.run_id for run in fetch_runs()]

        runs_payload = []
        for run_id in run_ids:
            try:
                run = backend_store.get_run(run_id)
            except Exception as exc:  # pragma: no cover - defensive log path
                logger.warning(f"Could not fetch run {run_id}: {str(exc)}")
                continue

            if run.info.lifecycle_stage != LifecycleStage.DELETED:
                continue
            if experiment_filter and run.info.experiment_id not in experiment_filter:
                continue

            runs_payload.append(
                {
                    "run_id": run.info.run_id,
                    "experiment_id": run.info.experiment_id,
                    "run_name": run.info.run_name,
                    "status": run.info.status,
                    "start_time": run.info.start_time,
                    "end_time": run.info.end_time,
                    "lifecycle_stage": run.info.lifecycle_stage,
                }
            )

        logger.info(
            f"Admin user '{admin_username}' listed {len(runs_payload)} deleted runs"
            f" (experiments filter: {experiment_filter or 'all'}, older_than: {older_than or 'not set'})."
        )
        return JSONResponse(content={"deleted_runs": runs_payload})

    except Exception:
        logger.exception("Error listing deleted runs for admin %s", admin_username)
        raise HTTPException(status_code=500, detail="Failed to retrieve deleted runs")


@trash_router.post(
    CLEANUP,
    summary="Permanently delete trashed entities",
    description="Permanently deletes entities (experiments, runs) that are in the trash based on specified criteria.",
)
async def permanently_delete_all_trashed_entities(
    admin_username: str = Depends(check_admin_permission),
    older_than: Optional[str] = Query(
        None,
        description="Remove entities older than the specified time limit (e.g., '1d2h3m4s', '7d'). Float values are supported.",
    ),
    run_ids: Optional[str] = Query(
        None,
        description="Comma-separated list of specific run IDs to permanently delete",
    ),
    experiment_ids: Optional[str] = Query(
        None,
        description="Comma-separated list of specific experiment IDs to permanently delete (including all their runs)",
    ),
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
        backend_store = _get_store()

        if not hasattr(backend_store, "_hard_delete_run"):
            logger.error("Backend store does not support hard deletion of runs")
            return JSONResponse(
                status_code=400,
                content={"error": "Backend store does not support permanent deletion of runs"},
            )

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
        target_run_ids = _split_csv(run_ids) if run_ids else list(deleted_run_ids_older_than)

        # Handle experiment deletion
        target_experiment_ids: List[str] = []
        time_threshold = get_current_time_millis() - time_delta

        if not skip_experiments:
            if experiment_ids:
                target_experiment_ids = _split_csv(experiment_ids)
                experiments = []

                for exp_id in target_experiment_ids:
                    try:
                        exp = backend_store.get_experiment(exp_id)
                        experiments.append(exp)
                    except Exception as e:
                        logger.error(f"Could not fetch experiment {exp_id}: {str(e)}")
                        return JSONResponse(
                            status_code=404,
                            content={"error": f"Experiment {exp_id} not found"},
                        )

                # Ensure experiments are deleted
                active_experiment_ids = [e.experiment_id for e in experiments if e.lifecycle_stage != LifecycleStage.DELETED]
                if active_experiment_ids:
                    return JSONResponse(
                        status_code=400,
                        content={"error": f"Experiments {active_experiment_ids} are not in deleted lifecycle stage"},
                    )

                # Check age requirements
                if older_than:
                    non_old_experiment_ids = [e.experiment_id for e in experiments if e.last_update_time is None or e.last_update_time >= time_threshold]
                    if non_old_experiment_ids:
                        return JSONResponse(
                            status_code=400,
                            content={"error": f"Experiments {non_old_experiment_ids} are not older than {older_than}"},
                        )
            elif not run_ids:
                # Neither run_ids nor experiment_ids was given ("empty trash"): sweep every
                # deleted experiment. When run_ids is given without experiment_ids (e.g. the UI's
                # "delete selected runs"), leave target_experiment_ids empty instead - the caller
                # asked to delete specific runs only, not every other trashed experiment.
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
                    failed_runs.append(
                        {
                            "run_id": run_id,
                            "error": "Run is not in deleted lifecycle stage",
                        }
                    )
                    continue

                # Check age requirement
                if older_than and run_id not in deleted_run_ids_older_than:
                    failed_runs.append(
                        {
                            "run_id": run_id,
                            "error": f"Run is not older than {older_than}",
                        }
                    )
                    continue

                # Delete artifacts. Resolve proxied `mlflow-artifacts:` URIs to this server's
                # configured artifact destination first (see _resolve_run_artifact_repository) so
                # that hard-deleting the run's metadata does not orphan artifacts we never
                # actually removed.
                try:
                    artifact_repo = _resolve_run_artifact_repository(run.info.artifact_uri)
                    artifact_repo.delete_artifacts()
                except InvalidUrlException as e:
                    # The artifact URI itself is malformed or uses an unsupported scheme, so
                    # there is no storage location to act on - matches `mlflow gc`'s own
                    # behavior of bypassing artifact deletion and continuing.
                    logger.warning(f"Could not delete artifacts for run {run_id}: {str(e)}")
                except Exception as e:
                    # A real resolution or deletion failure: the artifacts may still exist.
                    # Fail safe by keeping the run's metadata and reporting the failure instead
                    # of hard-deleting a run whose artifacts were not actually removed.
                    logger.error(f"Error deleting artifacts for run {run_id}: {str(e)}")
                    failed_runs.append({"run_id": run_id, "error": f"Failed to delete artifacts: {str(e)}"})
                    continue

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
                # A run can be kept above for many reasons (artifact deletion failure, age
                # requirement not met, wrong lifecycle stage, a get_run error, or the paged
                # fetch helpers above silently swallowing a search error and returning no
                # runs). Rather than track every one of those paths individually, check
                # directly, right before hard-deleting the experiment, whether it still owns
                # any run at all: MLflow's SqlRun -> SqlExperiment relationship cascades on
                # delete, so hard-deleting an experiment that still has a run - kept for any
                # reason - would delete that run's metadata along with it.
                try:
                    remaining_runs = backend_store.search_runs(
                        experiment_ids=[experiment_id],
                        filter_string="",
                        run_view_type=ViewType.ALL,
                        max_results=1,
                    )
                except Exception as e:
                    # Can't confirm the experiment has no runs left - fail safe and skip it
                    # rather than risk cascading a hard delete onto a run we never checked.
                    logger.error(f"Could not verify experiment {experiment_id} has no remaining runs: {str(e)}")
                    failed_experiments.append({"experiment_id": experiment_id, "error": f"Could not verify no runs remain: {str(e)}"})
                    continue

                if remaining_runs:
                    logger.warning(f"Skipping hard delete of experiment {experiment_id}: run(s) remain")
                    failed_experiments.append({"experiment_id": experiment_id, "error": "Run(s) remain in this experiment"})
                    continue

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

        emit_audit_event(
            "trash.cleanup",
            admin_username,
            resource_type="trash",
            detail={
                "deleted_runs_count": len(deleted_runs),
                "deleted_experiments_count": len(deleted_experiments),
                "older_than": older_than,
            },
        )

        return JSONResponse(content=response_data)

    except Exception:
        logger.exception("Error in cleanup operation for admin %s", admin_username)
        raise HTTPException(status_code=500, detail="Cleanup operation failed")


@trash_router.post(
    RESTORE_EXPERIMENT,
    summary="Restore a deleted experiment",
    description="Restores a soft-deleted experiment and all of its runs.",
)
async def restore_experiment(
    experiment_id: str,
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Restore a deleted experiment.

    Parameters
    ----------
    experiment_id : str
        The experiment identifier to restore.
    admin_username : str
        The authenticated admin username (injected by dependency).
    """
    backend_store = _get_store()

    try:
        experiment = backend_store.get_experiment(experiment_id)
    except Exception as exc:
        logger.error(f"Experiment {experiment_id} not found for restore: {str(exc)}")
        return JSONResponse(status_code=404, content={"error": f"Experiment {experiment_id} not found"})

    if experiment.lifecycle_stage != LifecycleStage.DELETED:
        return JSONResponse(status_code=400, content={"error": "Experiment is not deleted"})

    try:
        backend_store.restore_experiment(experiment_id)
        restored = backend_store.get_experiment(experiment_id)
        logger.info(f"Admin user '{admin_username}' restored experiment {experiment_id}")
        emit_audit_event(
            "trash.restore",
            admin_username,
            resource_type="experiment",
            resource_id=experiment_id,
        )
        return JSONResponse(
            content={
                "experiment": {
                    "experiment_id": restored.experiment_id,
                    "name": restored.name,
                    "lifecycle_stage": restored.lifecycle_stage,
                    "last_update_time": restored.last_update_time,
                }
            }
        )
    except Exception:  # pragma: no cover - defensive log path
        logger.exception("Error restoring experiment %s", experiment_id)
        raise HTTPException(status_code=500, detail="Failed to restore experiment")


@trash_router.post(
    RESTORE_RUN,
    summary="Restore a deleted run",
    description="Restores a soft-deleted run.",
)
async def restore_run(
    run_id: str,
    admin_username: str = Depends(check_admin_permission),
) -> JSONResponse:
    """
    Restore a deleted run.

    Parameters
    ----------
    run_id : str
        Identifier of the run to restore.
    admin_username : str
        The authenticated admin username (injected by dependency).
    """
    backend_store = _get_store()

    try:
        run = backend_store.get_run(run_id)
    except Exception as exc:
        logger.error(f"Run {run_id} not found for restore: {str(exc)}")
        return JSONResponse(status_code=404, content={"error": f"Run {run_id} not found"})

    if run.info.lifecycle_stage != LifecycleStage.DELETED:
        return JSONResponse(status_code=400, content={"error": "Run is not deleted"})

    try:
        backend_store.restore_run(run_id)
        restored = backend_store.get_run(run_id)
        logger.info(f"Admin user '{admin_username}' restored run {run_id}")
        emit_audit_event(
            "trash.restore",
            admin_username,
            resource_type="run",
            resource_id=run_id,
        )
        return JSONResponse(
            content={
                "run": {
                    "run_id": restored.info.run_id,
                    "experiment_id": restored.info.experiment_id,
                    "run_name": restored.info.run_name,
                    "status": restored.info.status,
                    "lifecycle_stage": restored.info.lifecycle_stage,
                }
            }
        )
    except Exception:
        logger.exception("Error restoring run %s", run_id)
        raise HTTPException(status_code=500, detail="Failed to restore run")


def _resolve_run_artifact_repository(artifact_uri: str):
    """
    Resolve the artifact repository backing a run's artifact root, translating a proxied
    ``mlflow-artifacts:`` URI to this server's configured artifact destination.

    A run's ``artifact_uri`` uses the ``mlflow-artifacts`` scheme when the tracking server
    serves artifacts itself (``mlflow server --serve-artifacts``): the real storage location
    (e.g. ``s3://bucket/...``) is rewritten to ``mlflow-artifacts:/<path>`` and resolved back
    to the real location at request time using the server's ``--artifacts-destination`` root.
    ``get_artifact_repository`` alone cannot do this translation here: it falls back to
    resolving ``mlflow-artifacts:`` relative to the process-global tracking URI, which inside
    this server process is the backend-store URI (a database), not an HTTP(S) endpoint, so it
    raises. Resolve it the same way ``mlflow.server.handlers`` does when it serves or deletes
    proxied artifacts instead.

    Parameters
    ----------
    artifact_uri : str
        The run's artifact root URI, as returned by the backend store.

    Returns
    -------
    ArtifactRepository
        The repository backing the run's real artifact storage location.

    Raises
    ------
    MlflowException
        If ``artifact_uri`` uses the ``mlflow-artifacts`` scheme but this server has no
        ``--artifacts-destination`` configured, so the real storage location is unknown, or if
        it has no path component of its own, so it cannot be mapped to anything narrower than
        the whole ``--artifacts-destination`` root.
    """
    if urllib.parse.urlparse(artifact_uri).scheme != "mlflow-artifacts":
        return get_artifact_repository(artifact_uri)

    from mlflow.server import ARTIFACTS_DESTINATION_ENV_VAR
    from mlflow.server.handlers import _get_proxied_run_artifact_destination_path

    destination_root = os.environ.get(ARTIFACTS_DESTINATION_ENV_VAR)
    if not destination_root:
        raise MlflowException(
            f"Cannot resolve proxied artifact URI '{artifact_uri}': this server is not "
            "configured with --artifacts-destination, so the underlying storage location "
            "for proxied artifacts is unknown.",
            error_code=INVALID_PARAMETER_VALUE,
        )

    relative_path = _get_proxied_run_artifact_destination_path(artifact_uri)
    if not relative_path:
        # An empty relative path means the URI names no location under the destination root at
        # all (e.g. "mlflow-artifacts:/" or "mlflow-artifacts://host"). Falling back to the
        # destination root itself would treat every other run's artifacts under it as this
        # run's own - raise instead so the run is kept rather than deleting unrelated artifacts.
        raise MlflowException(
            f"Cannot resolve proxied artifact URI '{artifact_uri}': it has no path component, "
            "so it cannot be mapped to a location under --artifacts-destination without "
            "resolving to the destination root itself.",
            error_code=INVALID_PARAMETER_VALUE,
        )

    resolved_uri = posixpath.join(destination_root, relative_path)
    return get_artifact_repository(resolved_uri)


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


def _split_csv(raw: Optional[str]) -> List[str]:
    """Split a comma-separated query parameter into trimmed, non-empty values."""
    if not raw:
        return []
    return [value.strip() for value in raw.split(",") if value.strip()]
