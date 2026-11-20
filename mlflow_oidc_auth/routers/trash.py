import os
import posixpath
import re
import urllib.parse
import warnings
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional, Set

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
from mlflow_oidc_auth.models.trash import (
    PermissionSweepResponse,
    TRASH_CLEANUP_ERROR_RESPONSES,
    TRASH_ERROR_RESPONSES,
    DeletedExperimentListResponse,
    DeletedRunListResponse,
    RestoredExperimentResponse,
    RestoredRunResponse,
    TrashCleanupResponse,
)
from mlflow_oidc_auth.orphans import (
    experiments_definitively_missing,
    order_experiment_ids,
    read_replica_configured,
    sweep_workspaces,
    workspace_listing_is_authoritative,
)
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils.data_fetching import fetch_all_experiments
from mlflow_oidc_auth.utils.pagination import NO_PAGE, PageQuery, paginate_with_headers

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
PERMISSIONS_SWEEP = "/permissions/sweep"
#: Most experiment ids an audit event carries; the event also states the total and whether it was cut.
_AUDIT_ID_SAMPLE = 100


_REPLICA_REFUSAL = (
    "the tracking store reads from a replica, which cannot prove an experiment is gone; run with dry_run=true and remove rows "
    "from the cleanup endpoint, or run the sweep against a server without a read replica"
)
_WORKSPACE_STORE_REFUSAL = (
    "the workspace store is not MLflow's built-in one, whose listing may hide workspaces, so an experiment cannot be proven gone; "
    "run with dry_run=true and remove rows from the cleanup endpoint"
)


def _capped_ids(ids: List[str]) -> dict:
    """The audit-event fragment for a possibly long id list: a capped sample plus a truncation flag."""
    return {"experiment_ids": list(ids[:_AUDIT_ID_SAMPLE]), "experiment_ids_truncated": len(ids) > _AUDIT_ID_SAMPLE}


@trash_router.get(
    EXPERIMENTS,
    response_model=DeletedExperimentListResponse,
    summary="List deleted experiments",
    description="Retrieves a list of deleted experiments in the MLflow tracking server.",
)
async def list_deleted_experiments(
    admin_username: str = Depends(check_admin_permission),
    page: PageQuery = NO_PAGE,
) -> JSONResponse:
    """
    List all deleted experiments.

    This endpoint returns all experiments that have been deleted (moved to trash).
    The requesting user must be an admin.

    Parameters:
    -----------
    admin_username : str
        The authenticated admin username (injected by dependency).
    page : PageParams
        Opt-in ``limit`` / ``offset`` / ``search`` on the experiment name (see
        ``utils/pagination.py``). The total is returned in ``X-Total-Count``.

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

        experiments_list, headers = paginate_with_headers(experiments_list, key=lambda e: e["name"], params=page, tiebreak=lambda e: e["experiment_id"])

        logger.info(f"Admin user '{admin_username}' listed {len(experiments_list)} deleted experiments.")
        return JSONResponse(content={"deleted_experiments": experiments_list}, headers=headers)

    except Exception:
        logger.exception("Error listing deleted experiments for admin %s", admin_username)
        raise HTTPException(status_code=500, detail="Failed to retrieve deleted experiments")


@trash_router.get(
    RUNS,
    response_model=DeletedRunListResponse,
    responses=TRASH_ERROR_RESPONSES,
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
    page: PageQuery = NO_PAGE,
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
    page : PageParams
        Opt-in ``limit`` / ``offset`` / ``search`` on the run name (see ``utils/pagination.py``).
        The total is returned in ``X-Total-Count``.

    Returns
    -------
    JSONResponse
        ``{"deleted_runs": [...]}``; 400 for an unparseable ``older_than``.

    Raises
    ------
    HTTPException
        500 when the runs cannot be read.
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
            # Fallback to search without age filtering when the backend lacks _get_deleted_runs. A
            # page that cannot be read fails the listing rather than show part of the trash.
            run_ids = _search_deleted_run_ids(backend_store, experiment_filter or None)

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

        runs_payload, headers = paginate_with_headers(runs_payload, key=lambda r: r["run_name"], params=page, tiebreak=lambda r: r["run_id"])

        logger.info(
            f"Admin user '{admin_username}' listed {len(runs_payload)} deleted runs"
            f" (experiments filter: {experiment_filter or 'all'}, older_than: {older_than or 'not set'})."
        )
        return JSONResponse(content={"deleted_runs": runs_payload}, headers=headers)

    except Exception:
        logger.exception("Error listing deleted runs for admin %s", admin_username)
        raise HTTPException(status_code=500, detail="Failed to retrieve deleted runs")


@trash_router.post(
    CLEANUP,
    response_model=TrashCleanupResponse,
    responses=TRASH_CLEANUP_ERROR_RESPONSES,
    summary="Permanently delete trashed entities",
    description=(
        "Permanently deletes entities (experiments, runs) that are in the trash based on specified criteria. "
        "With `run_ids` or `experiment_ids`, only the named runs, and the named experiments with their own runs, are deleted; "
        "with neither, the whole trash is emptied (limited by `older_than` if given). "
        "The response is 200 even when some named entities were kept: they are listed in `failed_runs` and `failed_experiments`."
    ),
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
        A JSON response indicating the result of the cleanup operation. It is 200 even when some
        entities were kept, which ``failed_runs`` and ``failed_experiments`` list. Every error,
        500 included, is ``{"error": ...}``; a 500 from a failed lookup of candidates means
        nothing was deleted.

    Raises:
    -------
    HTTPException
        403 - If the user does not have admin permissions.
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

        # Neither run_ids nor experiment_ids given ("empty trash"): sweep every trashed run and
        # experiment. Naming either limits the call to what was named, plus the named experiments'
        # own runs - a trashed run or experiment elsewhere must stay restorable (#484). A parameter
        # that is present but names nothing (``run_ids=``) deletes nothing; it never empties the
        # trash. Both sweeps below are driven by this one flag so they cannot disagree.
        empty_trash = run_ids is None and experiment_ids is None
        named_experiment_ids = _split_csv(experiment_ids)
        time_threshold = get_current_time_millis() - time_delta

        # The named experiments are checked first: it is cheap, and an unknown or active experiment
        # is the same 404/400 on every store, whatever a later lookup would do.
        if named_experiment_ids:
            experiments = []
            for exp_id in named_experiment_ids:
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

        # Get deleted runs that match the time criteria: the empty-trash candidates, and the age
        # check below. Neither is needed otherwise, so the scan over every trashed run is skipped.
        # Without it the call cannot tell which runs to empty or which are old enough, so it stops
        # before deleting anything rather than report every run as "not older than" or empty only
        # part of the trash.
        deleted_run_ids_older_than: Set[str] = set()
        if empty_trash or older_than:
            if hasattr(backend_store, "_get_deleted_runs"):
                try:
                    deleted_run_ids_older_than = set(backend_store._get_deleted_runs(older_than=time_delta))
                except Exception:
                    logger.exception("Could not fetch deleted runs by time criteria")
                    raise _CandidateLookupError("Failed to retrieve deleted runs")
            elif older_than:
                # Without _get_deleted_runs a run's deletion time cannot be read at all.
                return JSONResponse(
                    status_code=400,
                    content={"error": "Backend store does not support older_than for runs"},
                )
            else:
                # Same fallback as listing deleted runs: every experiment's deleted runs.
                deleted_run_ids_older_than = set(_search_deleted_run_ids(backend_store, None))

        target_run_ids = list(deleted_run_ids_older_than) if empty_trash else _split_csv(run_ids)

        # Handle experiment deletion
        target_experiment_ids: List[str] = []
        failed_experiments: List[dict] = []
        if named_experiment_ids:
            candidate_experiment_ids = named_experiment_ids
        elif empty_trash:
            # Sweep every deleted experiment. When run_ids is given without experiment_ids (e.g. the
            # UI's "delete selected runs"), there is none - the caller asked for specific runs only.
            filter_string = f"last_update_time < {time_threshold}" if older_than else None
            experiment_list = _fetch_all_pages(
                lambda token: backend_store.search_experiments(view_type=ViewType.DELETED_ONLY, filter_string=filter_string, page_token=token),
                "Failed to retrieve deleted experiments",
            )
            candidate_experiment_ids = [exp.experiment_id for exp in experiment_list]
        else:
            candidate_experiment_ids = []

        if skip_experiments:
            # Neither these experiments nor their runs are touched: report them rather than answer as
            # if they were deleted, whether they were named or found by emptying the trash.
            failed_experiments = [{"experiment_id": exp_id, "error": "Store cannot permanently delete experiments"} for exp_id in candidate_experiment_ids]
        else:
            target_experiment_ids = candidate_experiment_ids

        # Get runs from target experiments
        if target_experiment_ids:
            target_run_ids.extend(_search_deleted_run_ids(backend_store, target_experiment_ids))

        # Snapshot the grant rows of every target experiment once, before anything at all is deleted
        # (runs included): only rows that existed now are removed later, so a new experiment that reuses
        # an id (SQLite) keeps its creator's grant. If the rows cannot be read nothing is deleted: a
        # delete whose permission rows cannot be scoped is not worth the risk of a stale or over-broad
        # cleanup.
        grant_snapshot: Dict[str, Dict[str, List[int]]] = {}
        if target_experiment_ids:
            try:
                grant_snapshot = store.snapshot_experiment_grant_rows(list(target_experiment_ids))
            except Exception:
                logger.exception("Could not snapshot the permission rows of %d trashed experiments; nothing will be deleted", len(target_experiment_ids))
                raise _CandidateLookupError("Could not read permission rows; nothing was deleted")

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
                    failed_runs.append({"run_id": run_id, "error": "Failed to delete artifacts"})
                    continue

                # Hard delete the run
                backend_store._hard_delete_run(run_id)
                deleted_runs.append(run_id)
                logger.info(f"Permanently deleted run {run_id}")

            except Exception as e:
                logger.error(f"Error deleting run {run_id}: {str(e)}")
                # The client gets a fixed, classified message; the exception text stays in the
                # server log above because it can carry store or storage internals.
                not_found = isinstance(e, MlflowException) and e.error_code == "RESOURCE_DOES_NOT_EXIST"
                failed_runs.append({"run_id": run_id, "error": "Run not found" if not_found else "Failed to delete run"})

        # Delete experiments
        deleted_experiments = []
        failed_permission_cleanups: List[dict] = []

        if not skip_experiments:
            for experiment_id in target_experiment_ids:
                # A run can be kept above for many reasons (artifact deletion failure, age
                # requirement not met, wrong lifecycle stage, or a get_run error). Rather than track every one of those paths individually, check
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
                    failed_experiments.append({"experiment_id": experiment_id, "error": "Could not verify no runs remain"})
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
                    failed_experiments.append({"experiment_id": experiment_id, "error": "Failed to delete experiment"})

            # One batched delete for the experiments actually hard-deleted that had rows: at most one
            # permission-cache flush per call, none when there is nothing to remove. A failure must not
            # undo or hide the successful deletes, so it is reported separately and the sweep endpoint
            # can finish the job later.
            deleted_set = set(deleted_experiments)
            with_rows = sorted({eid for per_experiment in grant_snapshot.values() for eid in per_experiment if eid in deleted_set})
            if with_rows:
                try:
                    removed = store.delete_experiment_grant_rows(grant_snapshot, only_experiments=with_rows)
                    if removed:
                        emit_audit_event(
                            "trash.permissions_cleanup",
                            admin_username,
                            resource_type="experiment_permission",
                            detail={"removed_rows": removed, "experiments_with_rows": len(with_rows), **_capped_ids(with_rows)},
                        )
                except Exception:
                    logger.exception("Could not remove the permission rows of %d permanently deleted experiments", len(with_rows))
                    failed_permission_cleanups.extend({"experiment_id": eid, "error": "Failed to remove permission rows"} for eid in with_rows)

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

        if failed_permission_cleanups:
            response_data["failed_permission_cleanups"] = failed_permission_cleanups

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

    except _CandidateLookupError as e:
        # Raised before anything was deleted.
        return JSONResponse(status_code=500, content={"error": e.message})
    except Exception:
        logger.exception("Error in cleanup operation for admin %s", admin_username)
        return JSONResponse(status_code=500, content={"error": "Cleanup operation failed"})


@trash_router.post(
    PERMISSIONS_SWEEP,
    response_model=PermissionSweepResponse,
    responses=TRASH_CLEANUP_ERROR_RESPONSES,
    summary="Remove permission rows of experiments that no longer exist",
    description=(
        "Finds experiment and scorer grant rows whose experiment id is not in the tracking store (for example after "
        "`mlflow gc`) and, unless `dry_run` is true, deletes them. An id is removed only when every workspace "
        "reports it does not exist, in two passes over the same workspace set; any other answer or error keeps it, and it is listed in "
        "`unresolved_experiments`. The workspaces asked are the ones MLflow lists united with every workspace this plugin records "
        "grants for; if the listing changes between the passes, nothing is removed by that call. "
        "A trashed experiment still exists and is kept. Regex grants are patterns and are never touched. `dry_run` defaults to true. "
        "At most 1000 tracking-store lookups are made per call, over ids in ascending order (numeric when all ids are digits). "
        "When the budget runs out `truncated` is true and `next_after` is the last id fully decided: call again with `after=<next_after>` "
        "to continue with the ids after it. "
        "Only rows that existed when the sweep started are deleted. On stores that reuse experiment ids (SQLite), an id removed by `mlflow gc` "
        "and already reused by a new experiment looks like an existing experiment, so its stale grants cannot be told apart and are kept: "
        "run the sweep promptly, or use the cleanup endpoint instead of `mlflow gc`. "
        "A sweep with `dry_run=false` is refused with 409 when the tracking store reads from a read replica "
        "(a lagging replica says an experiment that was just created does not exist) and, with workspaces enabled, "
        "when the workspace store is not MLflow's built-in one (a third-party provider may hide workspaces from the listing); "
        "a dry run still works and sets `replica_reads` when a replica is configured, since its results may then include false positives."
    ),
)
def sweep_orphaned_experiment_permissions(
    admin_username: str = Depends(check_admin_permission),
    dry_run: bool = Query(True, description="Only report what would be removed (default). Pass false to delete."),
    after: Optional[str] = Query(None, description="Resume cursor: only experiment ids after this one are checked. Pass the previous response's `next_after`."),
) -> JSONResponse:
    """Remove grant rows that name experiments the tracking store no longer has.

    Parameters:
        admin_username: The authenticated admin username (injected by dependency).
        dry_run: When true (the default) nothing is deleted and no rows are snapshotted. False is refused with 409 when
            the tracking store reads from a replica or, with workspaces enabled, the workspace store is not MLflow's built-in one.
        after: The experiment id to resume after (the previous page's ``next_after``); None starts from the beginning.

    Returns:
        A ``PermissionSweepResponse`` body; a 409 ``{"error": ...}`` for a deleting sweep that cannot be trusted; a 500 ``{"error": ...}`` when the grant rows cannot be
        listed or deleted.

    Raises:
        Nothing: failures are returned as the 500 body.
    """
    replica_reads = read_replica_configured()
    if not dry_run:
        # Fail closed before anything is read or snapshotted: these two setups cannot prove an experiment is gone.
        if replica_reads:
            return JSONResponse(status_code=409, content={"error": _REPLICA_REFUSAL})
        if not workspace_listing_is_authoritative():
            return JSONResponse(status_code=409, content={"error": _WORKSPACE_STORE_REFUSAL})
    try:
        page_ids = order_experiment_ids(store.list_experiment_ids_with_grants(), after)
        # A real sweep snapshots the rows before any tracking-store lookup and deletes only those rows: a
        # grant created afterwards (an experiment id reused by a new experiment) is never touched. A dry
        # run deletes nothing, so it takes no snapshot.
        snapshot = {} if dry_run else store.snapshot_experiment_grant_rows(page_ids)
        workspaces = sweep_workspaces(store)
        first = experiments_definitively_missing(page_ids, workspaces)
        missing_set, unresolved_set = set(first.missing), set(first.unresolved)
        removed = 0
        if missing_set and not dry_run:
            # Confirm again right before deleting, over the workspaces as they are now: an id that exists by
            # now (moved between workspaces, or recreated) is dropped, and if the workspace set changed
            # since the first pass nothing is confirmed. The confirmation has its own budget, sized to the
            # candidates alone, so it never eats into the next page's.
            candidates = order_experiment_ids(missing_set)
            confirm_workspaces = sweep_workspaces(store)
            if confirm_workspaces is None or confirm_workspaces != workspaces:
                unresolved_set |= missing_set
                missing_set = set()
            else:
                confirmed = experiments_definitively_missing(candidates, confirm_workspaces, limit=len(candidates) * len(confirm_workspaces.checked))
                # An id the confirmation could not settle is kept, and reported as unresolved.
                unresolved_set |= confirmed.unresolved
                missing_set = set(confirmed.missing)
            if missing_set:
                removed = store.delete_experiment_grant_rows(snapshot, only_experiments=missing_set)
        missing, unresolved = order_experiment_ids(missing_set), order_experiment_ids(unresolved_set)
    except Exception:
        logger.exception("Error sweeping orphaned experiment permissions for admin %s", admin_username)
        return JSONResponse(status_code=500, content={"error": "Permission sweep failed"})

    logger.info(f"Admin user '{admin_username}' swept experiment permissions (dry_run={dry_run}): {len(missing)} missing experiments, {removed} rows removed")
    emit_audit_event(
        "trash.permissions_sweep",
        admin_username,
        resource_type="experiment_permission",
        detail={
            "dry_run": dry_run,
            "missing_count": len(missing),
            "unresolved_count": len(unresolved),
            "truncated": first.truncated,
            "next_after": first.next_after,
            "after": after,
            "removed_rows": removed,
            **_capped_ids(missing),
        },
    )
    return JSONResponse(
        content={
            "dry_run": dry_run,
            "checked_experiments": first.checked,
            "missing_experiments": missing,
            "unresolved_experiments": unresolved,
            "truncated": first.truncated,
            "next_after": first.next_after,
            "removed_rows": removed,
            "replica_reads": replica_reads,
        }
    )


@trash_router.post(
    RESTORE_EXPERIMENT,
    response_model=RestoredExperimentResponse,
    responses=TRASH_ERROR_RESPONSES,
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
    response_model=RestoredRunResponse,
    responses=TRASH_ERROR_RESPONSES,
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
    """Split a comma-separated query parameter into trimmed, non-empty, distinct values, in order."""
    if not raw:
        return []
    return list(dict.fromkeys(value.strip() for value in raw.split(",") if value.strip()))


class _CandidateLookupError(Exception):
    """A lookup of cleanup candidates failed; ``message`` is the client-facing reason."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _fetch_all_pages(fetch_page: Callable[[Optional[str]], Any], error: str) -> List[Any]:
    """Collect every page of a paged store search.

    Parameters:
        fetch_page: Returns the page for a page token (None for the first page).
        error: The client-facing reason if the pages cannot all be fetched.

    Returns:
        The items of every page, in order.

    Raises:
        _CandidateLookupError: With ``error``, when a page fails or the store hands back a page
            token it already gave - a partial list must never be taken for the whole.
    """
    items: List[Any] = []
    seen_tokens: Set[str] = set()
    token = None
    while True:
        try:
            page = fetch_page(token)
        except Exception:
            logger.exception(error)
            raise _CandidateLookupError(error)
        items.extend(page)
        # Only a real page token continues; anything else (a store that pages differently) ends
        # the search.
        token = getattr(page, "token", None)
        if not isinstance(token, str) or not token:
            return items
        if token in seen_tokens:
            logger.error(f"{error}: the store repeated a page token")
            raise _CandidateLookupError(error)
        seen_tokens.add(token)


def _search_deleted_run_ids(backend_store: Any, experiment_ids: Optional[List[str]]) -> List[str]:
    """The ids of the deleted runs of ``experiment_ids``, or of every experiment when None.

    Raises:
        _CandidateLookupError: When the experiments or any page of runs cannot be read.
    """
    if experiment_ids is None:
        try:
            experiment_ids = [exp.experiment_id for exp in fetch_all_experiments(view_type=ViewType.ALL)]
        except Exception:
            logger.exception("Could not list experiments")
            raise _CandidateLookupError("Failed to retrieve deleted runs")
    if not experiment_ids:
        return []
    runs = _fetch_all_pages(
        lambda token: backend_store.search_runs(
            experiment_ids=experiment_ids,
            filter_string="",
            run_view_type=ViewType.DELETED_ONLY,
            page_token=token,
        ),
        "Failed to retrieve deleted runs",
    )
    return [run.info.run_id for run in runs]
