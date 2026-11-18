"""The issue detection schedule guard: a stored schedule stops when its writer could no longer write it.

MLflow 3.18's scheduler runs a stored schedule with no identity. The plugin records who wrote each
one and the guard re-checks it against that writer, through the same permission checks a write goes
through, pausing it (MLflow's own ``paused`` flag) when the writer lost what writing it needed.
Driven with the real permission store (see ``hooks/authz_harness``) and a fake tracking store.
"""

import json
import threading
from types import SimpleNamespace

import pytest
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST
from mlflow.store.entities.paged_list import PagedList

from mlflow_oidc_auth import issue_detection_guard as guard
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
from mlflow_oidc_auth.tests.hooks.authz_harness import ADMIN, EDITOR, OUTSIDER, OWN, VICTIM, BaseFakeTrackingStore, install_permission_store

TAG = "mlflow.issueDetection.schedule"

pytestmark = pytest.mark.skipif(not guard.scheduler_available(), reason="MLflow's issue detection schedule arrived in 3.18")


def _schedule(model, paused=False):
    envelope = {"version": 1, "cadence": "daily", "timezone": "UTC", "paused": paused, "fireTime": "09:00", "weekday": 0}
    if model is not None:
        envelope["model"] = model
    return json.dumps(envelope)


class _TrackingStore(BaseFakeTrackingStore):
    def __init__(self):
        self.tags = {}
        self.writes = []

    def get_experiment(self, experiment_id):
        if experiment_id not in self.tags:
            raise MlflowException(f"no experiment {experiment_id}", RESOURCE_DOES_NOT_EXIST)
        return SimpleNamespace(experiment_id=experiment_id, name=f"experiment-{experiment_id}", workspace=None, tags=dict(self.tags[experiment_id]))

    def search_experiments(self, view_type=None, max_results=None, filter_string=None, page_token=None):
        assert filter_string == f"tags.`{TAG}` != ''"
        listed = [SimpleNamespace(experiment_id=e, name=f"experiment-{e}", workspace=None, tags=dict(tags)) for e, tags in sorted(self.tags.items())]
        return PagedList([experiment for experiment in listed if experiment.tags.get(TAG)], None)

    def set_experiment_tag(self, experiment_id, tag):
        self.writes.append((experiment_id, tag.key, tag.value))
        self.tags.setdefault(experiment_id, {})[tag.key] = tag.value

    def get_secret_info(self, secret_id=None, **_):
        if secret_id == "sec-1":
            return SimpleNamespace(secret_name="shared-key", auth_config={})
        raise MlflowException("no secret", RESOURCE_DOES_NOT_EXIST)

    def _get_decrypted_secret(self, secret_id):
        if secret_id == "sec-1":
            return {"api_key": "placeholder-value"}  # a placeholder, never a credential
        raise MlflowException("no secret", RESOURCE_DOES_NOT_EXIST)


@pytest.fixture
def tracking():
    return _TrackingStore()


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch, tracking):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    s = install_permission_store(tmp_path, monkeypatch, tracking)
    s.create_gateway_endpoint_permission("shared-endpoint", OUTSIDER, "NO_PERMISSIONS")
    s.create_gateway_secret_permission("shared-key", OUTSIDER, "NO_PERMISSIONS")
    flush_permission_cache()
    yield s
    flush_permission_cache()


def _store(tracking, experiment_id, value, author=None):
    tracking.tags.setdefault(experiment_id, {})[TAG] = value
    if author is not None:
        guard.record_author(experiment_id, None, author, value)


def _paused(tracking, experiment_id):
    return json.loads(tracking.tags[experiment_id][TAG])["paused"] is True


def _revoke(permission_store, **grants):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    for kind, (name, user) in grants.items():
        getattr(permission_store, f"create_{kind}_permission")(name, user, "NO_PERMISSIONS")
    flush_permission_cache()


# --- what keeps running ------------------------------------------------------------------------


def test_a_schedule_its_recorded_writer_may_still_write_keeps_running(tracking, permission_store):
    _store(tracking, VICTIM, _schedule({"endpointName": "open-endpoint"}), author=EDITOR)
    _store(tracking, OWN, _schedule({"provider": "openai", "model": "m"}), author=OUTSIDER)

    result = guard.sweep()

    assert result.checked == 2 and result.paused == [] and result.failed == []
    assert tracking.writes == []


def test_an_administrators_schedule_keeps_running(tracking):
    _store(tracking, OWN, _schedule({"endpointName": "shared-endpoint"}), author=ADMIN)
    assert guard.sweep().paused == []


def test_paused_and_unreadable_schedules_are_left_alone(tracking):
    _store(tracking, VICTIM, _schedule({"endpointName": "shared-endpoint"}, paused=True))
    _store(tracking, OWN, json.dumps({"version": 99, "cadence": "daily"}))
    result = guard.sweep()
    assert result.checked == 0 and tracking.writes == []


# --- what is paused ----------------------------------------------------------------------------


def test_a_schedule_with_no_recorded_writer_is_paused_and_keeps_its_settings(tracking, permission_store):
    value = _schedule({"provider": "openai", "model": "m", "secretId": "sec-1"})
    _store(tracking, VICTIM, value)

    result = guard.sweep()

    assert result.paused == [{"experiment_id": VICTIM, "workspace": None, "reason": guard.REASON_UNKNOWN_AUTHOR}]
    stored = json.loads(tracking.tags[VICTIM][TAG])
    assert stored == {**json.loads(value), "paused": True}
    record = permission_store.get_detection_schedule_author(VICTIM)
    assert record.author is None and record.guard_reason == guard.REASON_UNKNOWN_AUTHOR and record.guard_paused_at is not None


def test_a_writer_who_loses_use_of_the_endpoint_has_the_schedule_paused(tracking, permission_store):
    _store(tracking, OWN, _schedule({"endpointName": "team-endpoint"}), author=OUTSIDER)
    assert guard.sweep().paused == []

    _revoke(permission_store, gateway_endpoint=("team-endpoint", OUTSIDER))

    assert [p["reason"] for p in guard.sweep().paused] == [guard.REASON_NO_MODEL_USE]
    assert _paused(tracking, OWN)


def test_a_writer_who_loses_use_of_the_secret_has_the_schedule_paused(tracking, permission_store):
    _store(tracking, VICTIM, _schedule({"provider": "openai", "model": "m", "secretId": "sec-1"}), author=EDITOR)
    assert guard.sweep().paused == []

    _revoke(permission_store, gateway_secret=("shared-key", EDITOR))

    assert [p["reason"] for p in guard.sweep().paused] == [guard.REASON_NO_MODEL_USE]


def test_a_writer_who_loses_the_experiment_has_the_schedule_paused(tracking, permission_store):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    _store(tracking, VICTIM, _schedule({"endpointName": "open-endpoint"}), author=EDITOR)
    permission_store.update_experiment_permission(VICTIM, EDITOR, "READ")
    flush_permission_cache()

    assert [p["reason"] for p in guard.sweep().paused] == [guard.REASON_NO_EXPERIMENT_UPDATE]


def test_a_deleted_writer_has_the_schedule_paused(tracking, permission_store):
    _store(tracking, OWN, _schedule({"endpointName": "open-endpoint"}), author=OUTSIDER)
    permission_store.delete_user(OUTSIDER)
    assert [p["reason"] for p in guard.sweep().paused] == [guard.REASON_AUTHOR_DELETED]


def test_a_deactivated_writer_has_the_schedule_paused(tracking, permission_store):
    _store(tracking, VICTIM, _schedule({"endpointName": "open-endpoint"}), author=EDITOR)
    permission_store.update_user(EDITOR, active=False)
    assert [p["reason"] for p in guard.sweep().paused] == [guard.REASON_AUTHOR_INACTIVE]


def test_a_model_its_recorded_writer_did_not_store_is_not_credited_to_them(tracking):
    _store(tracking, OWN, _schedule({"endpointName": "open-endpoint"}), author=OUTSIDER)
    tracking.tags[OWN][TAG] = _schedule({"endpointName": "shared-endpoint"})
    assert [p["reason"] for p in guard.sweep().paused] == [guard.REASON_MODEL_CHANGED]


def test_the_cadence_is_not_part_of_what_is_credited(tracking):
    _store(tracking, OWN, _schedule({"endpointName": "open-endpoint"}), author=OUTSIDER)
    tracking.tags[OWN][TAG] = json.dumps({**json.loads(_schedule({"endpointName": "open-endpoint"})), "cadence": "hourly"})
    assert guard.sweep().paused == []


def test_server_credentials_are_paused_for_non_administrators_when_configured(tracking, monkeypatch):
    monkeypatch.setattr(config, "ISSUE_DETECTION_SERVER_CREDENTIALS_ADMIN_ONLY", True)
    _store(tracking, VICTIM, _schedule(None), author=EDITOR)
    _store(tracking, OWN, _schedule({"provider": "openai", "model": "m"}), author=ADMIN)

    result = guard.sweep()

    assert result.paused == [{"experiment_id": VICTIM, "workspace": None, "reason": guard.REASON_SERVER_CREDENTIALS}]
    assert not _paused(tracking, OWN)


def test_a_schedule_rewritten_while_being_checked_is_not_overwritten(tracking, monkeypatch):
    _store(tracking, VICTIM, _schedule({"endpointName": "shared-endpoint"}))
    original = tracking.get_experiment
    newer = _schedule({"endpointName": "open-endpoint"})

    def rewritten_meanwhile(experiment_id):
        experiment = original(experiment_id)
        experiment.tags[TAG] = newer
        return experiment

    monkeypatch.setattr(tracking, "get_experiment", rewritten_meanwhile)
    assert guard.sweep().paused == []
    assert tracking.writes == []


def test_a_failure_while_checking_pauses_rather_than_keeps_running(tracking, monkeypatch):
    from mlflow_oidc_auth.utils import permissions

    _store(tracking, OWN, _schedule({"endpointName": "open-endpoint"}), author=OUTSIDER)

    def broken(*_args, **_kwargs):
        raise RuntimeError("permission store unavailable")

    monkeypatch.setattr(permissions, "effective_experiment_permission", broken)
    assert [p["reason"] for p in guard.sweep().paused] == [guard.REASON_NO_MODEL_USE]


def test_resuming_a_paused_schedule_credits_whoever_resumed_it(tracking, permission_store):
    value = _schedule({"endpointName": "open-endpoint"})
    _store(tracking, OWN, value)
    guard.sweep()

    guard.record_author(OWN, None, OUTSIDER, value)

    record = permission_store.get_detection_schedule_author(OWN)
    assert record.author == OUTSIDER and record.guard_reason is None and record.guard_paused_at is None


def test_the_check_runs_as_the_writer_not_as_the_caller(tracking):
    """The admin API runs the check inside an administrator's request: the writer's own grants decide."""
    from mlflow_oidc_auth.bridge.user import clear_auth_context, get_auth_context, set_auth_context

    _store(tracking, OWN, _schedule({"endpointName": "shared-endpoint"}), author=OUTSIDER)
    token = set_auth_context(AuthContext(username=ADMIN, is_admin=True))
    try:
        assert guard.violation(OWN, None, tracking.tags[OWN][TAG]) == guard.REASON_NO_MODEL_USE
        assert get_auth_context().username == ADMIN
    finally:
        clear_auth_context(token)


# --- the fingerprint and the server-credential reading ---------------------------------------


def test_the_fingerprint_covers_the_model_only():
    a = _schedule({"endpointName": "e"})
    assert guard.model_fingerprint(a) == guard.model_fingerprint(json.dumps({**json.loads(a), "cadence": "hourly", "paused": True}))
    assert guard.model_fingerprint(a) != guard.model_fingerprint(_schedule({"endpointName": "f"}))
    assert guard.model_fingerprint(a) != guard.model_fingerprint(_schedule(None))
    assert guard.model_fingerprint("not json") != guard.model_fingerprint(_schedule(None))


@pytest.mark.parametrize(
    "model, expected",
    [
        (None, True),
        ({"provider": "openai", "model": "m"}, True),
        ({"provider": "openai", "model": "m", "secretId": "  "}, True),
        ({"provider": "openai", "model": "m", "secretId": "sec-1"}, False),
        ({"endpointName": "e"}, False),
        ({"provider": "Gateway", "model": "e"}, False),
        ("openai:/m", True),
    ],
)
def test_server_credentials_reading(model, expected):
    from mlflow_oidc_auth.validators._detection_schedule import schedule_uses_server_credentials

    assert schedule_uses_server_credentials(_schedule(model)) is expected


def test_an_unreadable_value_counts_as_server_credentials():
    from mlflow_oidc_auth.validators._detection_schedule import schedule_uses_server_credentials

    assert schedule_uses_server_credentials("not json") is True
    assert schedule_uses_server_credentials("[]") is True


def test_schedules_are_still_checked_when_mlflows_parser_cannot_be_loaded(tracking, monkeypatch):
    """MLflow internals moving must not leave every schedule running unchecked."""
    _store(tracking, OWN, _schedule({"endpointName": "open-endpoint"}), author=OUTSIDER)
    _store(tracking, VICTIM, _schedule({"endpointName": "open-endpoint"}, paused=True), author=OUTSIDER)

    def moved():
        raise AttributeError("parse_detection_schedule")

    monkeypatch.setattr(guard, "_mlflow_schedule_parser", moved)
    monkeypatch.setattr("mlflow_oidc_auth.validators._detection_schedule._mlflow_schedule_parser", moved)
    result = guard.sweep()
    assert result.checked == 1 and [p["experiment_id"] for p in result.paused] == [OWN]
    assert _paused(tracking, OWN)


# --- recording the writer (after-request hook) -----------------------------------------------


def _after(path, username, body, response=None):
    from flask import Response
    from mlflow.server import app as mlflow_app

    from mlflow_oidc_auth.hooks.after_request import after_request_hook

    environ = {AUTH_CONTEXT_KEY: AuthContext(username=username, is_admin=username == ADMIN)}
    with mlflow_app.test_request_context(path, method="POST", environ_base=environ, json=body):
        return after_request_hook(Response(json.dumps(response or {}), status=200, mimetype="application/json"))


SET_TAG = "/api/2.0/mlflow/experiments/set-experiment-tag"
DELETE_TAG = "/api/2.0/mlflow/experiments/delete-experiment-tag"
CREATE = "/api/2.0/mlflow/experiments/create"


def test_writing_the_schedule_tag_records_its_writer(tracking, permission_store):
    value = _schedule({"endpointName": "open-endpoint"})
    tracking.tags[OWN] = {TAG: value}

    _after(SET_TAG, OUTSIDER, {"experiment_id": OWN, "key": TAG, "value": value})

    record = permission_store.get_detection_schedule_author(OWN)
    assert record.author == OUTSIDER and record.model_fingerprint == guard.model_fingerprint(value)
    assert guard.sweep().paused == []


def test_a_value_another_write_replaced_is_not_credited_to_this_writer(tracking, permission_store):
    """Two writes racing: the one whose value MLflow no longer holds credits nobody."""
    stored = _schedule({"endpointName": "shared-endpoint"})
    tracking.tags[OWN] = {TAG: stored}

    _after(SET_TAG, ADMIN, {"experiment_id": OWN, "key": TAG, "value": _schedule({"endpointName": "open-endpoint"})})

    assert permission_store.get_detection_schedule_author(OWN) is None
    assert [p["reason"] for p in guard.sweep().paused] == [guard.REASON_UNKNOWN_AUTHOR]


def test_the_camel_case_experiment_id_is_recorded_too(tracking, permission_store):
    value = _schedule({"endpointName": "open-endpoint"})
    _store(tracking, OWN, _schedule({"endpointName": "shared-endpoint"}), author=ADMIN)
    tracking.tags[OWN][TAG] = value

    _after(SET_TAG, OUTSIDER, {"experimentId": OWN, "key": TAG, "value": value})

    assert permission_store.get_detection_schedule_author(OWN).author == OUTSIDER

    del tracking.tags[OWN][TAG]
    _after(DELETE_TAG, OUTSIDER, {"experimentId": OWN, "key": TAG})
    assert permission_store.get_detection_schedule_author(OWN) is None


def test_other_tags_record_nothing(tracking, permission_store):
    tracking.tags[OWN] = {"note": "v"}
    _after(SET_TAG, OUTSIDER, {"experiment_id": OWN, "key": "note", "value": "v"})
    assert permission_store.get_detection_schedule_author(OWN) is None


def test_deleting_the_schedule_tag_forgets_its_writer(tracking, permission_store):
    _store(tracking, OWN, _schedule({"endpointName": "open-endpoint"}), author=OUTSIDER)
    del tracking.tags[OWN][TAG]

    _after(DELETE_TAG, OUTSIDER, {"experiment_id": OWN, "key": TAG})

    assert permission_store.get_detection_schedule_author(OWN) is None


def test_creating_an_experiment_with_a_schedule_records_its_writer(tracking, permission_store, monkeypatch):
    monkeypatch.setattr("mlflow_oidc_auth.hooks.after_request.store", permission_store)
    value = _schedule({"endpointName": "open-endpoint"})
    tracking.tags["3"] = {TAG: value}

    _after(CREATE, OUTSIDER, {"name": "mine", "tags": [{"key": TAG, "value": value}]}, response={"experiment_id": "3"})

    assert permission_store.get_detection_schedule_author("3").author == OUTSIDER


def test_a_writer_that_cannot_be_recorded_leaves_the_schedule_to_be_paused(tracking, permission_store, monkeypatch):
    value = _schedule({"endpointName": "open-endpoint"})
    tracking.tags[OWN] = {TAG: value}

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    with monkeypatch.context() as patched:
        patched.setattr(permission_store, "record_detection_schedule_author", unavailable)
        _after(SET_TAG, OUTSIDER, {"experiment_id": OWN, "key": TAG, "value": value})

    assert [p["reason"] for p in guard.sweep().paused] == [guard.REASON_UNKNOWN_AUTHOR]


# --- the background thread -------------------------------------------------------------------


def test_the_background_check_is_off_at_interval_zero():
    background = guard._Guard()
    assert background.start(0) is False and not background.running
    background.trigger()  # never raises without a thread


def test_the_background_check_runs_once_at_startup_and_again_when_triggered(monkeypatch):
    passes = []
    ran = threading.Event()

    def counting_sweep():
        passes.append(1)
        ran.set()
        return guard.SweepResult()

    monkeypatch.setattr(guard, "sweep", counting_sweep)
    monkeypatch.setattr(guard, "TRIGGER_DELAY_SECONDS", 0.01)
    monkeypatch.setattr(guard, "TRIGGER_MIN_GAP_SECONDS", 0.0)
    background = guard._Guard()
    try:
        assert background.start(3600) is True and background.running
        assert ran.wait(5), "the first pass runs soon after startup"
        ran.clear()
        background.trigger()
        assert ran.wait(5), "a permission change brings the next pass forward"
        assert len(passes) == 2
    finally:
        background.stop()
    assert not background.running


def test_triggered_passes_are_spaced_out(monkeypatch):
    """A client writing grants in a loop cannot keep the guard sweeping."""
    import time

    starts = []
    ran = threading.Event()

    def counting_sweep():
        starts.append(time.monotonic())
        ran.set()
        return guard.SweepResult()

    monkeypatch.setattr(guard, "sweep", counting_sweep)
    monkeypatch.setattr(guard, "TRIGGER_DELAY_SECONDS", 0.01)
    monkeypatch.setattr(guard, "TRIGGER_MIN_GAP_SECONDS", 0.5)
    background = guard._Guard()
    try:
        background.start(3600)
        assert ran.wait(5)
        ran.clear()
        background.trigger()
        assert ran.wait(5)
        assert starts[1] - starts[0] >= 0.45
    finally:
        background.stop()


def test_a_permission_change_asks_for_a_pass(monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    asked = []
    monkeypatch.setattr(guard._guard, "trigger", lambda: asked.append(1))
    flush_permission_cache()
    assert asked
