"""Admin API for MLflow 3.18 recurring issue detection schedules.

Mounted at ``/api/3.0/mlflow/issue-detection-schedules``, administrators only. Lists every stored
schedule with its recorded writer and what the schedule guard makes of it, and runs the guard's
check on demand. See ``mlflow_oidc_auth.issue_detection_guard``.
"""

from typing import Dict, Optional

from fastapi import APIRouter, Depends

from mlflow_oidc_auth import issue_detection_guard as guard
from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models.issue_detection_schedule import (
    IssueDetectionScheduleEntry,
    IssueDetectionScheduleListResponse,
    IssueDetectionScheduleModel,
    IssueDetectionSchedulePaused,
    IssueDetectionScheduleSweepResponse,
)
from mlflow_oidc_auth.store import store

from ._prefix import ISSUE_DETECTION_SCHEDULES_ROUTER_PREFIX

issue_detection_schedules_router = APIRouter(
    prefix=ISSUE_DETECTION_SCHEDULES_ROUTER_PREFIX,
    tags=["issue detection schedules"],
    dependencies=[Depends(check_admin_permission)],
    responses={403: {"description": "Forbidden - administrators only"}},
)

SWEEP = "/check"

logger = get_logger()


def _text(value: object) -> Optional[str]:
    return value if isinstance(value, str) and value else None


def _model(state: guard.ScheduleState) -> Optional[IssueDetectionScheduleModel]:
    if state.model is None:
        return None
    secret_id = _text(state.model.get("secretId"))
    secret_name = None
    if secret_id:
        from mlflow_oidc_auth.validators.gateway import _resolve_secret_name_from_id

        with guard._in_workspace(state.workspace):
            secret_name = _resolve_secret_name_from_id(secret_id)
    return IssueDetectionScheduleModel(
        endpoint_name=_text(state.model.get("endpointName")),
        provider=_text(state.model.get("provider")),
        model=_text(state.model.get("model")),
        secret_id=secret_id,
        secret_name=secret_name,
    )


def _live_violation(state: guard.ScheduleState, record: object) -> Optional[str]:
    """The guard's verdict now, from the record already loaded; a check that errors is reported, not raised."""
    try:
        return guard.violation(state.experiment_id, state.workspace, state.raw, record=record)
    except Exception:
        logger.warning("Could not check the issue detection schedule of experiment %s", state.experiment_id, exc_info=True)
        return guard.REASON_CHECK_FAILED


@issue_detection_schedules_router.get("", response_model=IssueDetectionScheduleListResponse, summary="List issue detection schedules")
def list_issue_detection_schedules() -> IssueDetectionScheduleListResponse:
    """Every stored schedule on an active experiment, in every workspace, with its recorded writer."""
    supported = guard.scheduler_available()
    schedules = []
    if supported:
        records: Dict[str, object] = {record.experiment_id: record for record in store.list_detection_schedule_authors()}
        for state in guard.list_schedules():
            record = records.get(state.experiment_id)
            recorded = record.to_json() if record is not None else {}
            running = state.readable and not state.paused
            schedules.append(
                IssueDetectionScheduleEntry(
                    experiment_id=state.experiment_id,
                    experiment_name=state.experiment_name,
                    workspace=state.workspace,
                    readable=state.readable,
                    paused=state.paused,
                    uses_server_credentials=state.uses_server_credentials,
                    model=_model(state),
                    author=getattr(record, "author", None),
                    recorded_at=recorded.get("recorded_at"),
                    guard_paused_at=recorded.get("guard_paused_at"),
                    guard_reason=getattr(record, "guard_reason", None),
                    violation=_live_violation(state, record) if running else None,
                )
            )
    return IssueDetectionScheduleListResponse(
        supported=supported,
        guard_running=guard.guard_running(),
        guard_interval_seconds=config.ISSUE_DETECTION_SCHEDULE_GUARD_INTERVAL_SECONDS,
        server_credentials_admin_only=config.ISSUE_DETECTION_SERVER_CREDENTIALS_ADMIN_ONLY,
        schedules=schedules,
    )


@issue_detection_schedules_router.post(SWEEP, response_model=IssueDetectionScheduleSweepResponse, summary="Check issue detection schedules now")
def check_issue_detection_schedules(admin_username: str = Depends(check_admin_permission)) -> IssueDetectionScheduleSweepResponse:
    """Run the schedule guard's check once, now, and pause every schedule that may not keep running."""
    result = guard.sweep()
    emit_audit_event(
        "issue_detection_schedule.check",
        admin_username,
        detail={"checked": result.checked, "paused": len(result.paused), "failed": len(result.failed)},
    )
    return IssueDetectionScheduleSweepResponse(
        checked=result.checked,
        paused=[IssueDetectionSchedulePaused(**entry) for entry in result.paused],
        failed=result.failed,
    )
