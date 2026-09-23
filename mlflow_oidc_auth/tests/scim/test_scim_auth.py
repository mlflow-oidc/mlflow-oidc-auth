"""SCIM endpoint authentication (issue #321): the dedicated token is the only way in, and it is
no way in anywhere else."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.repository.scim_token import parse_prefix

from .conftest import ADMIN, LOGIN, PROTECTED, USER_PASSWORD, basic

SPC = "/scim/v2/ServiceProviderConfig"
USERS = "/scim/v2/Users"
TOKENS = "/api/2.0/mlflow/scim/tokens"
ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def assert_scim_401(response):
    assert response.status_code == 401
    assert response.headers["www-authenticate"].lower().startswith("bearer")
    assert response.headers["content-type"].startswith("application/scim+json")
    assert response.json()["schemas"] == [ERROR_SCHEMA]
    assert response.json()["status"] == "401"


class TestTokenFormatAndStorage:
    def test_plaintext_format(self, bound_store):
        record, plaintext = bound_store.create_scim_token("okta", created_by=ADMIN)
        assert plaintext.startswith("scim_")
        assert parse_prefix(plaintext) == record.token_prefix
        assert len(record.token_prefix) == 8

    def test_only_a_hash_is_stored(self, bound_store):
        _, plaintext = bound_store.create_scim_token("okta", created_by=ADMIN)
        with bound_store.engine.connect() as conn:
            stored = conn.execute(text("SELECT token_hash FROM scim_tokens")).scalar()
        assert plaintext not in stored
        assert stored.startswith("pbkdf2:sha256:")

    def test_names_are_unique(self, bound_store):
        from mlflow.exceptions import MlflowException

        bound_store.create_scim_token("okta", created_by=ADMIN)
        with pytest.raises(MlflowException):
            bound_store.create_scim_token("okta", created_by=ADMIN)

    def test_last_used_is_throttled(self, bound_store):
        record, plaintext = bound_store.create_scim_token("okta", created_by=ADMIN)
        first = bound_store.authenticate_scim_token(plaintext).last_used_at
        assert first is not None
        second = bound_store.authenticate_scim_token(plaintext).last_used_at
        assert second == first, "last_used_at must not be rewritten on every request"


class TestScimTokenAuthentication:
    def test_valid_token_is_accepted(self, client, scim_token):
        response = client.get(SPC, headers=bearer(scim_token))
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/scim+json")

    def test_missing_token_is_refused(self, client, bound_store):
        assert_scim_401(client.get(USERS))

    @pytest.mark.parametrize(
        "presented",
        [
            "not-a-scim-token",
            "scim_deadbeef_wrongsecret",
            "scim_",
            "",
        ],
    )
    def test_unknown_token_is_refused(self, client, scim_token, presented):
        assert_scim_401(client.get(USERS, headers=bearer(presented)))

    def test_right_prefix_wrong_secret_is_refused(self, client, scim_token):
        prefix = parse_prefix(scim_token)
        assert_scim_401(client.get(USERS, headers=bearer(f"scim_{prefix}_{'A' * 43}")))

    def test_basic_scheme_carrying_the_token_is_refused(self, client, scim_token):
        assert_scim_401(client.get(USERS, headers={"Authorization": f"Basic {scim_token}"}))

    def test_revoked_token_is_refused(self, client, bound_store):
        record, plaintext = bound_store.create_scim_token("okta", created_by=ADMIN)
        assert client.get(USERS, headers=bearer(plaintext)).status_code == 200
        bound_store.revoke_scim_token(record.id)
        assert_scim_401(client.get(USERS, headers=bearer(plaintext)))

    def test_expired_token_is_refused(self, client, bound_store):
        record, plaintext = bound_store.create_scim_token("okta", created_by=ADMIN, expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        assert client.get(USERS, headers=bearer(plaintext)).status_code == 200
        with bound_store.engine.begin() as conn:
            conn.execute(text("UPDATE scim_tokens SET expires_at = :t WHERE id = :i"), {"t": "2000-01-01 00:00:00", "i": record.id})
        assert_scim_401(client.get(USERS, headers=bearer(plaintext)))


class TestUserCredentialsDoNotAuthenticateScim:
    """The carve-out's negative half: nothing the OIDC chain accepts works on /scim/v2."""

    def test_admin_basic_auth_is_refused(self, client, admin):
        assert client.get(PROTECTED, headers=admin).status_code == 200, "precondition: the credential is valid"
        assert_scim_401(client.get(USERS, headers=admin))

    def test_session_cookie_is_refused(self, client, admin):
        client.get(LOGIN, params={"username": ADMIN})
        assert client.get(PROTECTED).status_code == 200, "precondition: the session is live"
        assert_scim_401(client.get(USERS))
        assert_scim_401(client.post(USERS, json={"userName": "x@example.com"}))

    def test_user_token_as_bearer_is_refused(self, client, bound_store):
        bound_store.create_user("u@example.com", USER_PASSWORD, "U")
        assert_scim_401(client.get(USERS, headers=bearer(USER_PASSWORD)))


class TestScimTokenDoesNotAuthenticateElsewhere:
    def test_scim_token_is_not_a_user_credential(self, client, scim_token):
        assert client.get(PROTECTED, headers=bearer(scim_token)).status_code == 401

    def test_scim_token_cannot_reach_the_admin_api(self, client, scim_token):
        assert client.get(TOKENS, headers=bearer(scim_token)).status_code in (401, 403)

    def test_sibling_prefix_is_still_protected(self, client, scim_token):
        """The carve-out is "/scim/v2/", so "/scim/v2x" stays behind the middleware."""
        assert client.get("/scim/v2x/Users", headers=bearer(scim_token)).status_code == 401


class TestUnmatchedScimPaths:
    def test_unsupported_resource_is_a_scim_404(self, client, scim):
        response = client.get("/scim/v2/Groups", headers=scim)
        assert response.status_code == 404
        assert response.json()["schemas"] == [ERROR_SCHEMA]

    def test_unsupported_resource_still_requires_the_token(self, client, bound_store):
        """The catch-all is what keeps an unmatched path from reaching the Flask mount unauthenticated."""
        assert_scim_401(client.get("/scim/v2/Groups"))
        assert_scim_401(client.post("/scim/v2/Bulk", json={}))


class TestRateLimit:
    def test_exhausted_budget_returns_429(self, client, scim, monkeypatch):
        monkeypatch.setattr(config, "SCIM_RATE_LIMIT_PER_MINUTE", 2)
        assert client.get(SPC, headers=scim).status_code == 200
        assert client.get(SPC, headers=scim).status_code == 200
        response = client.get(SPC, headers=scim)
        assert response.status_code == 429
        assert response.json()["schemas"] == [ERROR_SCHEMA]

    def test_budgets_are_per_token(self, client, bound_store, scim, monkeypatch):
        monkeypatch.setattr(config, "SCIM_RATE_LIMIT_PER_MINUTE", 1)
        _, other = bound_store.create_scim_token("okta", created_by=ADMIN)
        assert client.get(SPC, headers=scim).status_code == 200
        assert client.get(SPC, headers=scim).status_code == 429
        assert client.get(SPC, headers=bearer(other)).status_code == 200


class TestRotation:
    def test_old_token_works_during_overlap_then_stops(self, client, bound_store):
        record, old = bound_store.create_scim_token("entra-prod", created_by=ADMIN)
        replacement, new = bound_store.rotate_scim_token(record.id, overlap_seconds=3600)

        assert replacement.name == "entra-prod", "the replacement keeps the name operators know"
        assert client.get(USERS, headers=bearer(old)).status_code == 200, "old token must survive the overlap"
        assert client.get(USERS, headers=bearer(new)).status_code == 200

        # The overlap elapses.
        with bound_store.engine.begin() as conn:
            conn.execute(text("UPDATE scim_tokens SET expires_at = :t WHERE id = :i"), {"t": "2000-01-01 00:00:00", "i": record.id})

        assert_scim_401(client.get(USERS, headers=bearer(old)))
        assert client.get(USERS, headers=bearer(new)).status_code == 200

    def test_zero_overlap_ends_the_old_token_at_once(self, client, bound_store):
        record, old = bound_store.create_scim_token("entra-prod", created_by=ADMIN)
        bound_store.rotate_scim_token(record.id, overlap_seconds=0)
        assert_scim_401(client.get(USERS, headers=bearer(old)))

    def test_revoked_token_cannot_be_rotated_back_to_life(self, bound_store):
        from mlflow.exceptions import MlflowException

        record, _ = bound_store.create_scim_token("entra-prod", created_by=ADMIN)
        bound_store.revoke_scim_token(record.id)
        with pytest.raises(MlflowException):
            bound_store.rotate_scim_token(record.id, overlap_seconds=3600)

    def test_replacement_never_outlives_the_original_policy(self, bound_store):
        expiry = datetime.now(timezone.utc) + timedelta(days=30)
        record, _ = bound_store.create_scim_token("entra-prod", created_by=ADMIN, expires_at=expiry)
        replacement, _ = bound_store.rotate_scim_token(record.id, overlap_seconds=3600)
        assert replacement.expires_at == expiry.replace(tzinfo=None)


class TestTokenAdminApi:
    def test_non_admin_is_forbidden(self, client, bound_store, admin):
        bound_store.create_user("u@example.com", USER_PASSWORD, "U")
        user = basic("u@example.com", USER_PASSWORD)
        assert client.get(TOKENS, headers=user).status_code == 403
        response = client.post(TOKENS, headers=user, json={"name": "x"})
        assert response.status_code == 403
        record, _ = bound_store.create_scim_token("okta", created_by=ADMIN)
        response = client.post(f"{TOKENS}/{record.id}/rotate", headers=user)
        assert response.status_code == 403
        response = client.delete(f"{TOKENS}/{record.id}", headers=user)
        assert response.status_code == 403
        assert bound_store.list_scim_tokens()[0].revoked_at is None

    def test_unauthenticated_is_refused(self, client, bound_store):
        assert client.get(TOKENS).status_code == 401

    def test_lifecycle(self, client, admin, audit_events):
        created = client.post(TOKENS, headers=admin, json={"name": "entra"})
        assert created.status_code == 201
        assert created.headers["cache-control"] == "no-store"
        body = created.json()
        plaintext, token_id = body["token"], body["id"]
        assert client.get(SPC, headers=bearer(plaintext)).status_code == 200

        listed = client.get(TOKENS, headers=admin).json()
        assert [t["name"] for t in listed] == ["entra"]
        assert "token" not in listed[0] and "token_hash" not in listed[0]
        assert plaintext not in created.text.replace(plaintext, "", 1), "plaintext appears exactly once"

        rotated = client.post(f"{TOKENS}/{token_id}/rotate", headers=admin)
        assert rotated.status_code == 201
        new_plaintext = rotated.json()["token"]
        assert client.get(SPC, headers=bearer(new_plaintext)).status_code == 200

        revoked = client.delete(f"{TOKENS}/{rotated.json()['id']}", headers=admin)
        assert revoked.status_code == 200 and revoked.json()["active"] is False
        assert_scim_401(client.get(SPC, headers=bearer(new_plaintext)))

        events = [e["event"] for e in audit_events]
        assert {"scim_token.create", "scim_token.rotate", "scim_token.revoke"} <= set(events)
        assert all(plaintext not in str(e) and new_plaintext not in str(e) for e in audit_events), "never audit a plaintext"

    def test_duplicate_name_is_a_conflict(self, client, admin):
        response = client.post(TOKENS, headers=admin, json={"name": "entra"})
        assert response.status_code == 201
        response = client.post(TOKENS, headers=admin, json={"name": "entra"})
        assert response.status_code == 409

    def test_past_expiry_is_rejected(self, client, admin):
        response = client.post(TOKENS, headers=admin, json={"name": "entra", "expires_at": "2000-01-01T00:00:00Z"})
        assert response.status_code == 400

    def test_unknown_token_is_404(self, client, admin):
        response = client.delete(f"{TOKENS}/9999", headers=admin)
        assert response.status_code == 404
        response = client.post(f"{TOKENS}/9999/rotate", headers=admin)
        assert response.status_code == 404


class TestRequestAudit:
    def test_every_request_is_audited_with_token_and_status(self, client, scim, audit_events):
        client.get(USERS, headers=scim)
        event = [e for e in audit_events if e["event"] == "scim.request"][-1]
        assert event["detail"]["token"] == "entra"
        assert event["detail"]["method"] == "GET"
        assert event["detail"]["path"] == USERS
        assert event["detail"]["status"] == 200
        assert event["status"] == "success"

    def test_refused_requests_are_audited_once_per_client_per_window(self, client, bound_store, audit_events):
        for _ in range(5):
            client.get(USERS, headers=bearer("scim_deadbeef_nope"))

        failed = [e for e in audit_events if e["event"] == "scim.auth_failed"]
        assert len(failed) == 1, "an anonymous flood must not write one audit line per request"
        assert failed[0]["actor"] == "anonymous"
        assert failed[0]["status"] == "denied"
        assert "scim_deadbeef_nope" not in str(failed[0]), "a presented credential is never audited"
        assert not [e for e in audit_events if e["event"] == "scim.request"]

    def test_the_next_window_reports_the_suppressed_count(self, client, bound_store, audit_events, monkeypatch):
        from mlflow_oidc_auth.dependencies import scim_auth_failure_audit

        for _ in range(3):
            client.get(USERS)
        monkeypatch.setattr(scim_auth_failure_audit, "WINDOW_SECONDS", 0.0)
        client.get(USERS)

        failed = [e for e in audit_events if e["event"] == "scim.auth_failed"]
        assert [e["detail"]["failures_in_previous_window"] for e in failed] == [0, 3]


class TestFailedAuthLimit:
    def test_failures_are_limited_per_client(self, client, bound_store, monkeypatch):
        monkeypatch.setattr(config, "SCIM_AUTH_FAILURE_LIMIT_PER_MINUTE", 3)
        statuses = [client.get(USERS, headers=bearer("scim_deadbeef_nope")).status_code for _ in range(5)]
        assert statuses == [401, 401, 401, 429, 429]

    def test_a_valid_token_from_the_same_client_is_not_locked_out(self, client, scim, monkeypatch):
        """The limit bounds noise; it must not let an attacker behind the same NAT stop the sync."""
        monkeypatch.setattr(config, "SCIM_AUTH_FAILURE_LIMIT_PER_MINUTE", 1)
        for _ in range(3):
            client.get(USERS, headers=bearer("scim_deadbeef_nope"))
        assert client.get(USERS, headers=scim).status_code == 200


class TestNothingReachesTheMount:
    """Every method on every path under /scim/v2 stays in the SCIM router — with or without a
    token — and never reaches the WSGI app mounted at "/", which AuthMiddleware did not
    authenticate for these paths."""

    METHODS = ["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE", "TRACE", "PROPFIND", "MKCOL", "FOO"]
    PATHS = ["/scim/v2/Users", "/scim/v2/Users/x@example.com", "/scim/v2/Groups", "/scim/v2/", "/scim/v2/ServiceProviderConfig", "/scim/v2//Users"]

    @pytest.fixture
    def mounted(self, app):
        from starlette.middleware.wsgi import WSGIMiddleware

        calls = []

        def flask_stand_in(environ, start_response):
            calls.append((environ["REQUEST_METHOD"], environ["PATH_INFO"]))
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"reached the mount"]

        app.mount("/", WSGIMiddleware(flask_stand_in))
        return calls

    @pytest.mark.parametrize("with_token", [False, True])
    def test_no_method_reaches_the_mount(self, app, mounted, bound_store, with_token):
        from fastapi.testclient import TestClient

        headers = {}
        if with_token:
            _, plaintext = bound_store.create_scim_token("probe", created_by=ADMIN)
            headers = bearer(plaintext)
        with TestClient(app) as c:
            for path in self.PATHS:
                for method in self.METHODS:
                    response = c.request(method, path, headers=headers)
                    assert response.status_code != 200 or response.text != "reached the mount", (method, path)
        assert mounted == [], f"reached the unauthenticated mount: {mounted}"

    def test_the_stand_in_is_reachable_elsewhere(self, app, mounted, bound_store):
        """Guards the test itself: the mount must actually be live for the assertion to mean anything."""
        from fastapi.testclient import TestClient

        with TestClient(app) as c:
            c.get("/login/anything-else")
        assert mounted, "the stand-in mount never saw a request; the test above would pass vacuously"
