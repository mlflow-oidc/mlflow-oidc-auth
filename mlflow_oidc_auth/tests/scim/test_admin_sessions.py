"""Admin session list and revocation (issue #325).

A session id is a bearer credential: the list must never return one. Revocation is addressed by
an opaque primary key that must be scoped to the user named in the path, so a key read off one
user's list cannot end another user's session.
"""

import pytest
from fastapi.testclient import TestClient

from .conftest import ADMIN, LOGIN, PROTECTED, USER_PASSWORD, basic

USERS_API = "/api/2.0/mlflow/users"
BOB = "bob@example.com"
CAROL = "carol@example.com"


@pytest.fixture
def bob(bound_store):
    bound_store.create_user(BOB, USER_PASSWORD, "Bob")
    return basic(BOB, USER_PASSWORD)


@pytest.fixture
def carol(bound_store):
    bound_store.create_user(CAROL, USER_PASSWORD, "Carol")
    return basic(CAROL, USER_PASSWORD)


def _browser(app, username: str) -> TestClient:
    """A separate cookie jar signed in as ``username`` through a server-side session."""
    browser = TestClient(app)
    assert browser.get(LOGIN, params={"username": username}).status_code == 200
    assert browser.get(PROTECTED).json()["username"] == username
    return browser


def _sessions(client, admin, username):
    response = client.get(f"{USERS_API}/{username}/sessions", headers=admin)
    assert response.status_code == 200, response.text
    return response.json()["sessions"]


class TestList:
    def test_lists_live_sessions_without_the_session_id(self, app, client, admin, bob, bound_store):
        _browser(app, BOB)
        _browser(app, BOB)
        full_ids = bound_store.auth_session_repo.list_live_for_user(BOB)

        response = client.get(f"{USERS_API}/{BOB}/sessions", headers=admin)
        sessions = response.json()["sessions"]
        assert len(sessions) == 2
        assert response.headers["cache-control"] == "no-store"
        for session in sessions:
            assert set(session) == {"pk", "session_id_prefix", "provider_id", "created_at", "last_seen_at", "expires_at"}
            assert len(session["session_id_prefix"]) == 8
            assert session["expires_at"] is not None and session["created_at"] is not None
        for full_id in full_ids:
            assert full_id not in response.text, "a full session id is a credential and never leaves the server"

    def test_revoked_and_expired_sessions_are_not_listed(self, app, client, admin, bob, bound_store):
        from datetime import datetime, timedelta, timezone

        _browser(app, BOB)
        bound_store.create_auth_session(BOB, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
        revoked = bound_store.create_auth_session(BOB, expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        bound_store.revoke_auth_session(revoked)

        assert len(_sessions(client, admin, BOB)) == 1

    def test_unknown_user_is_404(self, client, admin):
        assert client.get(f"{USERS_API}/nobody@example.com/sessions", headers=admin).status_code == 404


class TestRevoke:
    def test_revoke_one_ends_that_session_only(self, app, client, admin, bob, audit_events):
        first = _browser(app, BOB)
        second = _browser(app, BOB)
        sessions = _sessions(client, admin, BOB)
        newest = sessions[0]

        response = client.delete(f"{USERS_API}/{BOB}/sessions/{newest['pk']}", headers=admin)
        assert response.status_code == 200
        assert response.json() == {"revoked": 1}

        assert second.get(PROTECTED).status_code == 401, "the revoked session dies on its next request"
        assert first.get(PROTECTED).status_code == 200, "the other session is untouched"
        assert [s["pk"] for s in _sessions(client, admin, BOB)] == [sessions[1]["pk"]]

        event = [e for e in audit_events if e["event"] == "session.revoked"][-1]
        assert event["actor"] == ADMIN
        assert event["resource_id"] == BOB
        assert event["detail"]["source"] == "admin"
        assert event["detail"]["sessions"] == 1

    def test_revoking_twice_is_404(self, app, client, admin, bob):
        _browser(app, BOB)
        pk = _sessions(client, admin, BOB)[0]["pk"]
        response = client.delete(f"{USERS_API}/{BOB}/sessions/{pk}", headers=admin)
        assert response.status_code == 200
        response = client.delete(f"{USERS_API}/{BOB}/sessions/{pk}", headers=admin)
        assert response.status_code == 404

    def test_another_users_pk_is_404_and_revokes_nothing(self, app, client, admin, bob, carol):
        carols = _browser(app, CAROL)
        _browser(app, BOB)
        carol_pk = _sessions(client, admin, CAROL)[0]["pk"]

        response = client.delete(f"{USERS_API}/{BOB}/sessions/{carol_pk}", headers=admin)
        assert response.status_code == 404
        assert carols.get(PROTECTED).status_code == 200
        assert len(_sessions(client, admin, CAROL)) == 1

    def test_revoke_all(self, app, client, admin, bob, carol, audit_events):
        browsers = [_browser(app, BOB), _browser(app, BOB)]
        carols = _browser(app, CAROL)

        response = client.delete(f"{USERS_API}/{BOB}/sessions", headers=admin)
        assert response.json() == {"revoked": 2}
        assert all(browser.get(PROTECTED).status_code == 401 for browser in browsers)
        assert carols.get(PROTECTED).status_code == 200
        assert _sessions(client, admin, BOB) == []

        event = [e for e in audit_events if e["event"] == "session.revoked"][-1]
        assert (event["actor"], event["resource_id"], event["detail"]["source"], event["detail"]["sessions"]) == (ADMIN, BOB, "admin", 2)

    def test_revoke_all_keeps_the_account_and_its_token(self, app, client, admin, bob):
        _browser(app, BOB)
        client.delete(f"{USERS_API}/{BOB}/sessions", headers=admin)
        assert client.get(PROTECTED, headers=bob).status_code == 200, "basic auth with the user's token still works"

    def test_unknown_user_is_404(self, client, admin):
        response = client.delete(f"{USERS_API}/nobody@example.com/sessions", headers=admin)
        assert response.status_code == 404
        response = client.delete(f"{USERS_API}/nobody@example.com/sessions/1", headers=admin)
        assert response.status_code == 404


class TestNonAdmin:
    """Every endpoint is admin-only — including a user asking about their own sessions."""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", f"{USERS_API}/{CAROL}/sessions"),
            ("DELETE", f"{USERS_API}/{CAROL}/sessions"),
            ("DELETE", f"{USERS_API}/{CAROL}/sessions/1"),
            ("GET", f"{USERS_API}/{BOB}/sessions"),
            ("DELETE", f"{USERS_API}/{BOB}/sessions"),
        ],
    )
    def test_forbidden(self, app, client, admin, bob, carol, method, path):
        carols = _browser(app, CAROL)
        assert client.request(method, path, headers=bob).status_code == 403
        assert carols.get(PROTECTED).status_code == 200, "a refused request revokes nothing"

    def test_unauthenticated_is_refused(self, client, bob):
        assert client.get(f"{USERS_API}/{BOB}/sessions").status_code == 401
        response = client.delete(f"{USERS_API}/{BOB}/sessions")
        assert response.status_code == 401

    def test_a_scim_token_cannot_revoke_sessions(self, app, client, bob, scim):
        bobs = _browser(app, BOB)
        response = client.delete(f"{USERS_API}/{BOB}/sessions", headers={"Authorization": scim["Authorization"]})
        assert response.status_code == 401
        assert bobs.get(PROTECTED).status_code == 200
