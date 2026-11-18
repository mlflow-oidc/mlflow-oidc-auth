"""The schedule guard: stop MLflow 3.18 recurring issue detection whose writer lost access.

MLflow keeps an experiment's recurring issue detection in the ``mlflow.issueDetection.schedule``
experiment tag, and its scheduler (in MLflow's job consumer, where this plugin is not loaded) runs
every occurrence on the model the tag names with no user identity. The plugin authorizes the write
of that tag (``mlflow_oidc_auth.validators._detection_schedule``), but a stored schedule kept
running after its writer lost the access the write needed.

So the plugin records who wrote each schedule (``record_author``, from the after-request hook), and
this module re-checks every active schedule against its recorded writer, as if that writer were
writing it again now. A schedule is paused (MLflow's own ``paused`` flag, rewritten through MLflow's
tracking store, never its database) when:

* no writer was recorded for it (it predates this check, or was written some other way);
* the model it names is not the one its recorded writer stored;
* the writer's account no longer exists, or is deactivated;
* the writer may no longer update the experiment;
* the writer may no longer use the gateway endpoint or secret it names;
* it runs on the server's own provider credentials, its writer is not an administrator, and
  ``ISSUE_DETECTION_SERVER_CREDENTIALS_ADMIN_ONLY`` is on.

Administrators' schedules are not paused for the last three: an administrator may write any.
Resuming a paused schedule is an ordinary write of the tag, authorized like any other, and makes
the person resuming it its recorded writer.

The check runs in a background thread of each server process every
``ISSUE_DETECTION_SCHEDULE_GUARD_INTERVAL_SECONDS``, shortly after any permission change seen by
that process, and on demand from the admin API. Each pass is idempotent, so several replicas
running it is safe. A revoke is therefore enforced within one interval at worst (sooner on the
replica that made it), and before then by the permission cache's TTL like any other decision.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import threading
import time
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from typing import Any, Iterator, List, Optional

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.validators._detection_schedule import (
    DETECTION_SCHEDULE_TAG,
    _mlflow_schedule_parser,
    detection_schedules_permitted,
    schedule_uses_server_credentials,
)

logger = get_logger()

REASON_UNKNOWN_AUTHOR = "unknown_author"
REASON_MODEL_CHANGED = "model_changed"
REASON_AUTHOR_DELETED = "author_deleted"
REASON_AUTHOR_INACTIVE = "author_deactivated"
REASON_NO_EXPERIMENT_UPDATE = "author_cannot_update_experiment"
REASON_NO_MODEL_USE = "author_cannot_use_model"
REASON_SERVER_CREDENTIALS = "server_credentials_admin_only"
#: Reported by the admin listing only: the check raised (a transient fault); nothing is paused for it.
REASON_CHECK_FAILED = "check_failed"

REASONS = (
    REASON_UNKNOWN_AUTHOR,
    REASON_MODEL_CHANGED,
    REASON_AUTHOR_DELETED,
    REASON_AUTHOR_INACTIVE,
    REASON_NO_EXPERIMENT_UPDATE,
    REASON_NO_MODEL_USE,
    REASON_SERVER_CREDENTIALS,
)

#: A permission change is followed by a pass this many seconds later, so a burst of changes (a
#: group sync, a bulk grant) costs one pass rather than one each.
TRIGGER_DELAY_SECONDS = 5.0

#: Least time between two passes started by permission changes, so a client writing grants in a
#: loop (every created experiment grants its creator) cannot keep the guard sweeping.
TRIGGER_MIN_GAP_SECONDS = 60.0

#: The shortest background interval honoured; a smaller positive setting is raised to it.
MIN_INTERVAL_SECONDS = 30

_PAGE_SIZE = 100
_SCHEDULED_EXPERIMENTS_FILTER = f"tags.`{DETECTION_SCHEDULE_TAG}` != ''"


def scheduler_available() -> bool:
    """Whether the installed MLflow has recurring issue detection at all."""
    try:
        return importlib.util.find_spec("mlflow.genai.discovery.schedule") is not None
    except ModuleNotFoundError:
        return False


def model_fingerprint(raw: Optional[str]) -> str:
    """A digest of the model a stored schedule value names, as stored.

    Only the model is fingerprinted: the cadence, time and paused flag change when a run happens,
    not what it runs on or whose credential it spends. A value that is not a JSON object is
    fingerprinted whole, so it never matches a schedule's.
    """
    try:
        envelope = json.loads(raw or "")
    except (ValueError, RecursionError):
        envelope = None
    if isinstance(envelope, dict):
        material = json.dumps({"model": envelope.get("model")}, sort_keys=True, separators=(",", ":"))
    else:
        material = "raw:" + (raw or "")
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def record_author(experiment_id: str, workspace: Optional[str], username: str, raw: Optional[str]) -> None:
    """Credit the schedule value ``raw`` now stored on ``experiment_id`` to ``username``."""
    from mlflow_oidc_auth.store import store

    store.record_detection_schedule_author(str(experiment_id), workspace, username, model_fingerprint(raw))


def forget_author(experiment_id: str) -> None:
    from mlflow_oidc_auth.store import store

    store.delete_detection_schedule_author(str(experiment_id))


@dataclass(frozen=True)
class ScheduleState:
    """One stored schedule as the guard sees it."""

    experiment_id: str
    experiment_name: str
    workspace: Optional[str]
    raw: str
    readable: bool
    paused: bool
    uses_server_credentials: bool
    model: Optional[dict]


def _parse(raw: str) -> tuple[bool, bool, Optional[dict]]:
    """``(readable, paused, model)`` for a stored value: readable means MLflow's scheduler would run it.

    When MLflow's parser cannot be loaded at all (internals moved), every JSON-object value counts
    as readable and is checked: the authorization check then refuses it and the guard pauses it,
    rather than skipping schedules the scheduler may still run.
    """
    try:
        envelope = json.loads(raw)
    except (ValueError, RecursionError):
        envelope = None
    model = envelope.get("model") if isinstance(envelope, dict) and isinstance(envelope.get("model"), dict) else None
    try:
        parser = _mlflow_schedule_parser()
    except Exception:
        logger.error("Issue detection schedule guard cannot load MLflow's schedule parser; checking every schedule as stored", exc_info=True)
        if not isinstance(envelope, dict):
            return False, False, model
        return True, envelope.get("paused") is True, model
    try:
        schedule = parser(raw) if parser is not None else None
    except Exception:
        schedule = None
    if schedule is None:
        return False, False, model
    return True, bool(schedule.paused), model


def _workspaces() -> List[Optional[str]]:
    """The workspaces MLflow's scheduler walks: every workspace, or none when workspaces are off."""
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return [None]
    from mlflow.server.handlers import _get_workspace_store

    return [workspace.name for workspace in _get_workspace_store().list_workspaces()]


@contextmanager
def _in_workspace(workspace: Optional[str]) -> Iterator[None]:
    if workspace is None:
        with nullcontext():
            yield
        return
    from mlflow.utils.workspace_context import ServerWorkspaceContext

    with ServerWorkspaceContext(workspace):
        yield


@contextmanager
def _as_user(username: str, is_admin: bool, workspace: Optional[str]) -> Iterator[None]:
    """Resolve permissions as ``username`` writing in ``workspace``, the way a request would."""
    from mlflow_oidc_auth.bridge.user import clear_auth_context, set_auth_context
    from mlflow_oidc_auth.entities.auth_context import AuthContext

    token = set_auth_context(AuthContext(username=username, is_admin=is_admin, workspace=workspace))
    try:
        yield
    finally:
        clear_auth_context(token)


def _tracking_store():
    from mlflow.server.handlers import _get_tracking_store

    return _get_tracking_store()


def _scheduled_experiments() -> Iterator[tuple[Optional[str], Any]]:
    from mlflow.entities import ViewType

    tracking_store = _tracking_store()
    for workspace in _workspaces():
        with _in_workspace(workspace):
            page_token = None
            while True:
                page = tracking_store.search_experiments(
                    view_type=ViewType.ACTIVE_ONLY,
                    max_results=_PAGE_SIZE,
                    filter_string=_SCHEDULED_EXPERIMENTS_FILTER,
                    page_token=page_token,
                )
                for experiment in page:
                    yield workspace, experiment
                if not (page_token := page.token):
                    break


def list_schedules() -> List[ScheduleState]:
    """Every stored schedule on an active experiment, in every workspace."""
    states = []
    for workspace, experiment in _scheduled_experiments():
        raw = experiment.tags.get(DETECTION_SCHEDULE_TAG) or ""
        readable, paused, model = _parse(raw)
        states.append(
            ScheduleState(
                experiment_id=str(experiment.experiment_id),
                experiment_name=experiment.name,
                workspace=workspace,
                raw=raw,
                readable=readable,
                paused=paused,
                uses_server_credentials=schedule_uses_server_credentials(raw),
                model=model,
            )
        )
    return states


_UNLOADED = object()


def violation(experiment_id: str, workspace: Optional[str], raw: str, record: Any = _UNLOADED) -> Optional[str]:
    """Why the schedule ``raw`` on ``experiment_id`` may not keep running, or None if it may.

    The recorded writer is checked as if writing the value again now, through the same checks a
    write goes through. Those checks deny on what they cannot resolve; an error escaping them (a
    database outage, say) raises, so the pass reports the schedule as failed and retries it next
    pass instead of pausing every schedule for a transient fault.
    """
    from mlflow_oidc_auth.store import store
    from mlflow_oidc_auth.utils.permissions import effective_experiment_permission

    if record is _UNLOADED:
        record = store.get_detection_schedule_author(experiment_id)
    if record is None or not record.author:
        return REASON_UNKNOWN_AUTHOR
    if record.model_fingerprint != model_fingerprint(raw):
        return REASON_MODEL_CHANGED
    try:
        user = store.get_user(record.author)
    except MlflowException as e:
        if e.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
            return REASON_AUTHOR_DELETED
        raise
    if not getattr(user, "active", True):
        return REASON_AUTHOR_INACTIVE
    if user.is_admin:
        return None
    request_workspace = workspace if config.MLFLOW_ENABLE_WORKSPACES else None
    with _in_workspace(workspace), _as_user(record.author, False, request_workspace):
        if not effective_experiment_permission(experiment_id, record.author).permission.can_update:
            return REASON_NO_EXPERIMENT_UPDATE
        if config.ISSUE_DETECTION_SERVER_CREDENTIALS_ADMIN_ONLY and schedule_uses_server_credentials(raw):
            return REASON_SERVER_CREDENTIALS
        if not detection_schedules_permitted([raw], record.author):
            return REASON_NO_MODEL_USE
    return None


@dataclass
class SweepResult:
    checked: int = 0
    paused: List[dict] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)


def _pause(experiment_id: str, workspace: Optional[str], raw: str, reason: str) -> bool:
    """Set MLflow's ``paused`` flag on the schedule, unless it changed since it was read."""
    from mlflow.entities import ExperimentTag

    from mlflow_oidc_auth.audit import emit_audit_event
    from mlflow_oidc_auth.store import store

    tracking_store = _tracking_store()
    with _in_workspace(workspace):
        current = tracking_store.get_experiment(experiment_id).tags.get(DETECTION_SCHEDULE_TAG)
        if current != raw:
            # Rewritten since it was read: that write was authorized and recorded on its own, and
            # the next pass checks the new value.
            return False
        # MLflow's store has no compare-and-set: a write landing between this read and the write
        # below is replaced by the old value, paused. That fails closed (nothing runs that was not
        # checked) and the writer can set the schedule again.
        envelope = json.loads(raw)
        envelope["paused"] = True
        tracking_store.set_experiment_tag(experiment_id, ExperimentTag(DETECTION_SCHEDULE_TAG, json.dumps(envelope)))
    store.mark_detection_schedule_guard_paused(experiment_id, workspace, reason)
    logger.warning("Paused the issue detection schedule of experiment %s (%s)", experiment_id, reason)
    try:
        emit_audit_event(
            "issue_detection_schedule.paused",
            "system:issue-detection-schedule-guard",
            resource_type="experiment",
            resource_id=experiment_id,
            detail={"workspace": workspace, "reason": reason},
        )
    except Exception:
        logger.debug("Audit event for a paused issue detection schedule could not be emitted", exc_info=True)
    return True


def sweep() -> SweepResult:
    """Check every active, unpaused schedule once and pause each one that may not keep running."""
    result = SweepResult()
    if not scheduler_available():
        return result
    for state in list_schedules():
        if not state.readable or state.paused:
            continue
        result.checked += 1
        try:
            reason = violation(state.experiment_id, state.workspace, state.raw)
            if reason and _pause(state.experiment_id, state.workspace, state.raw, reason):
                result.paused.append({"experiment_id": state.experiment_id, "workspace": state.workspace, "reason": reason})
        except Exception:
            logger.warning("Issue detection schedule guard failed on experiment %s", state.experiment_id, exc_info=True)
            result.failed.append(state.experiment_id)
    return result


class _Guard:
    """The background thread: one pass every interval, and one shortly after a permission change."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._interval = 0.0
        self._last_pass = 0.0
        self._schedules_seen = True

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, interval_seconds: int) -> bool:
        if interval_seconds <= 0 or not scheduler_available():
            return False
        with self._lock:
            if self.running:
                return True
            self._interval = float(max(interval_seconds, MIN_INTERVAL_SECONDS))
            # Each thread gets its own stop and wake events, so a thread a slow stop() left
            # finishing a pass can never be revived by the next start().
            self._stop = threading.Event()
            self._wake = threading.Event()
            # A first pass soon after startup covers schedules stored before this server started.
            self._wake.set()
            self._thread = threading.Thread(target=self._run, args=(self._stop, self._wake), name="issue-detection-schedule-guard", daemon=True)
            self._thread.start()
            return True

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            self._stop.set()
            self._wake.set()
            self._thread = None
        if thread is not None:
            thread.join(timeout=5)

    def trigger(self) -> None:
        # Nothing to re-check when the last pass found no running schedule; the periodic pass
        # still picks up schedules written since.
        if self.running and self._schedules_seen:
            self._wake.set()

    def _run(self, stop: threading.Event, wake: threading.Event) -> None:
        while not stop.is_set():
            if wake.wait(self._interval):
                wake.clear()
                delay = max(TRIGGER_DELAY_SECONDS, self._last_pass + TRIGGER_MIN_GAP_SECONDS - time.monotonic())
                if stop.wait(delay):
                    break
                wake.clear()
            if stop.is_set():
                break
            self._last_pass = time.monotonic()
            try:
                result = sweep()
                self._schedules_seen = result.checked > 0 or bool(result.failed)
                if result.paused or result.failed:
                    logger.info("Issue detection schedule guard: %d checked, %d paused, %d failed", result.checked, len(result.paused), len(result.failed))
            except Exception:
                logger.warning("Issue detection schedule guard pass failed", exc_info=True)


_guard = _Guard()


def start_guard() -> bool:
    """Start the background check (no-op without MLflow's scheduler, or with the interval at 0)."""
    return _guard.start(config.ISSUE_DETECTION_SCHEDULE_GUARD_INTERVAL_SECONDS)


def stop_guard() -> None:
    _guard.stop()


def guard_running() -> bool:
    return _guard.running


def permissions_changed() -> None:
    """Ask for a pass soon: grants, memberships or users changed. Never raises."""
    try:
        _guard.trigger()
    except Exception:
        pass
