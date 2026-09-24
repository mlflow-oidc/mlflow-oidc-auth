"""SCIM activity log and provisioning status (issue #325).

The recorder must write exactly one row per ``/scim/v2`` request — failures included — and must
never change a response. The status must say *when provisioning last worked* and *why it stopped*,
and must not call an unused SCIM endpoint unhealthy.
"""

from datetime import datetime, timedelta, timezone

import pytest

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.routers import scim as scim_module

from .conftest import USER_PASSWORD, basic, user_body

USERS = "/scim/v2/Users"
ACTIVITY = "/api/2.0/mlflow/scim/activity"
STATUS = "/api/2.0/mlflow/scim/status"
BOB = "bob@example.com"


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _rows(store, **filters):
    return store.list_scim_activity(limit=200, **filters)


@pytest.fixture
def bob(bound_store):
    bound_store.create_user(BOB, USER_PASSWORD, "Bob")
    return basic(BOB, USER_PASSWORD)


def _seed(store, *, at, outcome="ok", status=200, token_id=1, token_name="entra", error=None, path="/Users", resource_id=None):
    store.record_scim_activity(
        token_id=token_id,
        token_name=token_name,
        method="GET",
        path=path,
        resource_id=resource_id,
        status=status,
        outcome=outcome,
        error=error,
        duration_ms=1,
        at=at,
    )


class TestRecorder:
    def test_one_row_per_request_with_template_path_and_resource_id(self, client, scim, bound_store):
        assert client.post(USERS, headers=scim, json=user_body("alice@example.com")).status_code == 201
        assert client.get(f"{USERS}/alice@example.com", headers=scim).status_code == 200

        rows = _rows(bound_store)
        assert len(rows) == 2
        get, post = rows  # newest first
        assert (post.method, post.path, post.resource_id, post.status, post.outcome, post.token_name) == ("POST", "/Users", None, 201, "ok", "entra")
        assert (get.method, get.path, get.resource_id, get.status, get.outcome) == ("GET", "/Users/{user_id}", "alice@example.com", 200, "ok")
        assert "alice" not in get.path, "the path column holds the route template, never a username"
        assert post.error is None
        assert post.duration_ms is not None and post.duration_ms >= 0

    def test_client_errors_record_the_scim_detail(self, client, scim, bound_store):
        client.post(USERS, headers=scim, json=user_body("alice@example.com"))
        response = client.post(USERS, headers=scim, json=user_body("alice@example.com"))
        assert response.status_code == 409

        row = _rows(bound_store)[0]
        assert row.outcome == "client_error"
        assert row.status == 409
        assert row.error.startswith("uniqueness: ")
        assert len(row.error) <= 500

    def test_unknown_resource_is_a_client_error(self, client, scim, bound_store):
        assert client.get(f"{USERS}/nobody@example.com", headers=scim).status_code == 404
        row = _rows(bound_store)[0]
        assert (row.outcome, row.status, row.path, row.resource_id) == ("client_error", 404, "/Users/{user_id}", "nobody@example.com")

    def test_server_errors_are_recorded(self, client, scim, bound_store, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("database on fire: secret connection string")

        monkeypatch.setattr(scim_module, "_find_user", boom)
        response = client.get(f"{USERS}/alice@example.com", headers=scim)
        assert response.status_code == 500

        row = _rows(bound_store)[0]
        assert (row.outcome, row.status, row.error) == ("server_error", 500, "Internal error")
        assert "secret" not in (row.error or ""), "an exception's text never reaches the log"

    def test_auth_failures_are_recorded_on_the_audit_throttle(self, client, bound_store):
        presented = "scim_deadbeef_not-a-real-token"
        for _ in range(5):
            assert client.get(f"{USERS}/alice@example.com", headers={"Authorization": f"Bearer {presented}"}).status_code == 401

        rows = _rows(bound_store)
        assert len(rows) == 1, "an anonymous flood writes one row per client per window, like the audit log"
        row = rows[0]
        assert (row.outcome, row.status, row.token_id, row.token_name) == ("auth_failed", 401, None, None)
        assert presented not in str(row.to_json()), "a presented credential is never recorded"

    def test_auth_failures_follow_the_audit_window(self, client, bound_store, monkeypatch):
        from mlflow_oidc_auth.dependencies import scim_auth_failure_audit

        client.get(USERS)
        client.get(USERS)
        monkeypatch.setattr(scim_auth_failure_audit, "WINDOW_SECONDS", 0.0)
        client.get(USERS)

        assert [row.outcome for row in _rows(bound_store)] == ["auth_failed", "auth_failed"]

    def test_anonymous_rows_are_capped_across_clients(self, client, bound_store, monkeypatch):
        """An attacker rotating source addresses gets past the per-client throttle, not this cap."""
        from mlflow_oidc_auth.dependencies import scim_auth_failure_audit

        monkeypatch.setattr(scim_module, "ANONYMOUS_ACTIVITY_PER_MINUTE", 2)
        monkeypatch.setattr(scim_auth_failure_audit, "WINDOW_SECONDS", 0.0)  # every request looks like a new client
        for _ in range(5):
            assert client.get(USERS).status_code == 401

        assert len(_rows(bound_store, outcome="auth_failed")) == 2

    def test_authenticated_requests_are_not_capped(self, client, scim, bound_store, monkeypatch):
        monkeypatch.setattr(scim_module, "ANONYMOUS_ACTIVITY_PER_MINUTE", 1)
        for _ in range(3):
            client.get(USERS, headers=scim)
        assert len(_rows(bound_store, outcome="ok")) == 3

    def test_rate_limited_token_is_a_client_error_with_the_token(self, client, scim, bound_store, monkeypatch):
        monkeypatch.setattr(config, "SCIM_RATE_LIMIT_PER_MINUTE", 1)
        assert client.get(USERS, headers=scim).status_code == 200
        assert client.get(USERS, headers=scim).status_code == 429

        row = _rows(bound_store)[0]
        assert (row.outcome, row.status, row.token_name) == ("client_error", 429, "entra")

    def test_unsupported_endpoints_are_recorded(self, client, scim, bound_store):
        assert client.post("/scim/v2/Bulk", headers=scim, json={}).status_code == 404
        row = _rows(bound_store)[0]
        assert (row.path, row.resource_id, row.outcome) == ("/{unsupported}", "Bulk", "client_error")

    def test_a_recording_failure_never_changes_the_response(self, client, scim, bound_store, monkeypatch):
        def broken(**fields):
            raise RuntimeError("activity table is gone")

        monkeypatch.setattr(bound_store, "record_scim_activity", broken)
        response = client.post(USERS, headers=scim, json=user_body("alice@example.com"))
        assert response.status_code == 201
        assert response.json()["userName"] == "alice@example.com"
        assert client.get(f"{USERS}/nobody@example.com", headers=scim).status_code == 404

    def test_a_token_in_an_error_message_is_redacted(self):
        text = scim_module._activity_error(400, "bad value scim_deadbeef_abcdefghijk in body", "invalidValue")
        assert "abcdefghijk" not in text
        assert text.startswith("invalidValue: ")

    def test_error_is_capped(self):
        assert len(scim_module._activity_error(400, "x" * 2000, None)) == 500


class TestRetention:
    def test_the_recorder_sweeps_expired_rows_at_most_hourly(self, client, scim, bound_store, monkeypatch):
        monkeypatch.setattr(config, "SCIM_ACTIVITY_RETENTION_DAYS", 30, raising=False)
        _seed(bound_store, at=_now() - timedelta(days=31))
        _seed(bound_store, at=_now() - timedelta(days=29))

        client.get(USERS, headers=scim)
        assert len(_rows(bound_store)) == 2, "the 31-day-old row is swept, the 29-day-old one and the new one kept"

        _seed(bound_store, at=_now() - timedelta(days=40))
        client.get(USERS, headers=scim)
        assert len(_rows(bound_store)) == 4, "no second sweep within the hour"

    def test_zero_retention_keeps_everything(self, client, scim, bound_store, monkeypatch):
        monkeypatch.setattr(config, "SCIM_ACTIVITY_RETENTION_DAYS", 0, raising=False)
        _seed(bound_store, at=_now() - timedelta(days=400))
        client.get(USERS, headers=scim)
        assert len(_rows(bound_store)) == 2


class TestActivityApi:
    def test_newest_first_with_paging(self, client, admin, bound_store):
        for minutes in range(5, 0, -1):
            _seed(bound_store, at=_now() - timedelta(minutes=minutes), resource_id=str(minutes))

        first = client.get(ACTIVITY, headers=admin, params={"limit": 2}).json()
        assert [row["resource_id"] for row in first["activity"]] == ["1", "2"]
        assert first["next_before"] == first["activity"][-1]["id"]

        second = client.get(ACTIVITY, headers=admin, params={"limit": 2, "before": first["next_before"]}).json()
        assert [row["resource_id"] for row in second["activity"]] == ["3", "4"]
        last = client.get(ACTIVITY, headers=admin, params={"limit": 2, "before": second["next_before"]}).json()
        assert [row["resource_id"] for row in last["activity"]] == ["5"]
        assert last["next_before"] is None

    def test_filters(self, client, admin, bound_store):
        _seed(bound_store, at=_now(), outcome="ok", token_id=1)
        _seed(bound_store, at=_now(), outcome="client_error", status=409, token_id=1, error="uniqueness: taken")
        _seed(bound_store, at=_now(), outcome="ok", token_id=2, token_name="okta")
        _seed(bound_store, at=_now(), outcome="auth_failed", status=401, token_id=None, token_name=None)

        errors = client.get(ACTIVITY, headers=admin, params={"outcome": "client_error"}).json()["activity"]
        assert [(row["status"], row["error"]) for row in errors] == [(409, "uniqueness: taken")]
        okta = client.get(ACTIVITY, headers=admin, params={"token_id": 2}).json()["activity"]
        assert [row["token_name"] for row in okta] == ["okta"]
        failed = client.get(ACTIVITY, headers=admin, params={"outcome": "auth_failed"}).json()["activity"]
        assert [row["token_id"] for row in failed] == [None]

    def test_limit_is_capped_and_outcome_validated(self, client, admin):
        assert client.get(ACTIVITY, headers=admin, params={"limit": 201}).status_code == 422
        assert client.get(ACTIVITY, headers=admin, params={"outcome": "bogus"}).status_code == 400

    def test_non_admin_is_forbidden(self, client, admin, bob):
        assert client.get(ACTIVITY, headers=bob).status_code == 403

    def test_unauthenticated_is_refused(self, client):
        assert client.get(ACTIVITY).status_code == 401

    def test_a_scim_token_cannot_read_it(self, client, scim):
        assert client.get(ACTIVITY, headers={"Authorization": scim["Authorization"]}).status_code == 401


class TestStatus:
    def test_never_used_is_null(self, client, admin, scim_token):
        body = client.get(STATUS, headers=admin).json()
        assert body["provisioning_healthy"] is None
        assert body["last_success_at"] is None and body["last_error_at"] is None
        assert body["retention_days"] == config.SCIM_ACTIVITY_RETENTION_DAYS
        assert [(t["name"], t["active"], t["requests_24h"], t["last_used_at"]) for t in body["tokens"]] == [("entra", True, 0, None)]

    def test_healthy_after_a_success_with_24h_counts(self, client, admin, scim, bound_store):
        client.post(USERS, headers=scim, json=user_body("alice@example.com"))
        client.post(USERS, headers=scim, json=user_body("alice@example.com"))  # 409

        body = client.get(STATUS, headers=admin).json()
        assert body["provisioning_healthy"] is True
        assert body["requests_24h"] == 2 and body["errors_24h"] == 1
        (token,) = body["tokens"]
        assert token["requests_24h"] == 2 and token["errors_24h"] == 1
        assert token["last_success_at"] is not None and token["last_used_at"] is not None
        assert token["last_error"].startswith("uniqueness: ")
        assert token["last_error_status"] == 409
        assert body["last_error"] == token["last_error"]

    def test_counts_exclude_older_than_a_day(self, client, admin, scim_token, bound_store):
        token_id = bound_store.list_scim_tokens()[0].id
        _seed(bound_store, at=_now() - timedelta(hours=25), token_id=token_id)
        _seed(bound_store, at=_now() - timedelta(hours=23), token_id=token_id, outcome="server_error", status=500, error="Internal error")

        body = client.get(STATUS, headers=admin).json()
        (token,) = body["tokens"]
        assert (token["requests_24h"], token["errors_24h"]) == (1, 1)
        assert body["provisioning_healthy"] is False, "the last success is outside the healthy window"
        assert token["last_error"] == "Internal error"

    def test_healthy_window_is_configurable(self, client, admin, scim_token, bound_store, monkeypatch):
        token_id = bound_store.list_scim_tokens()[0].id
        _seed(bound_store, at=_now() - timedelta(hours=2), token_id=token_id)

        assert client.get(STATUS, headers=admin).json()["provisioning_healthy"] is True
        monkeypatch.setattr(config, "SCIM_ACTIVITY_HEALTHY_WINDOW_SECONDS", 3600, raising=False)
        body = client.get(STATUS, headers=admin).json()
        assert body["provisioning_healthy"] is False
        assert body["healthy_window_seconds"] == 3600

    def test_only_auth_failures_is_unhealthy_and_reported_separately(self, client, admin, scim_token):
        client.get(USERS, headers={"Authorization": "Bearer scim_deadbeef_wrong"})

        body = client.get(STATUS, headers=admin).json()
        assert body["provisioning_healthy"] is False, "a directory presenting a wrong token is a failure, not 'never used'"
        assert body["auth_failures_24h"] == 1
        assert body["last_auth_failure_at"] is not None
        assert body["tokens"][0]["requests_24h"] == 0

    def test_revoked_tokens_are_listed_inactive(self, client, admin, bound_store, scim_token):
        bound_store.revoke_scim_token(bound_store.list_scim_tokens()[0].id)
        assert [t["active"] for t in client.get(STATUS, headers=admin).json()["tokens"]] == [False]

    def test_non_admin_is_forbidden(self, client, admin, bob):
        assert client.get(STATUS, headers=bob).status_code == 403

    def test_unauthenticated_is_refused(self, client):
        assert client.get(STATUS).status_code == 401
