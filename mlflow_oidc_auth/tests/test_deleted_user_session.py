"""A deleted user's session must not authenticate, on any surface (issue #306).

`_authenticate_session` authenticates purely from ``session["username"]`` in the signed cookie —
nothing there verifies the user still exists. The suspicion was that a user deleted mid-session
still passed the authentication middleware, merely downgraded to non-admin, leaving only
downstream permission checks between them and the application.

**Result: the gap was real and is now closed.** The `active` check added by #311 reads the user's
profile on every authenticated request, and a deleted user cannot be read — so the request is
denied before it reaches any surface, rather than proceeding as a non-admin.

These tests pin that for each surface the issue names, because the fix lives in one place and a
future refactor could easily restore the old behaviour for some of them:

* a FastAPI route (the permission-management API),
* a Flask route reached through ``AuthAwareWSGIMiddleware`` (MLflow's own API),
* ``/graphql``, which is a Flask route on the same mount.

All three sit behind ``AuthMiddleware``, which `app.py` adds before mounting Flask at ``/``, so
one denial covers them — but that is a structural claim, and this file is the evidence.
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from flask import Flask
from starlette.middleware.sessions import SessionMiddleware

import mlflow_oidc_auth.middleware.auth_middleware as auth_middleware_module
import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth.middleware import AuthAwareWSGIMiddleware, AuthMiddleware

PASSWORD = "session-password"  # not a credential: only ever seeded into a tmp_path database
LOGIN = "/login/probe"

# The three surfaces. Paths are chosen to reach each one: /oidc/* is FastAPI, /api/* and
# /graphql fall through to the mounted Flask app.
FASTAPI_ROUTE = "/oidc/api/probe"
FLASK_ROUTE = "/api/2.0/mlflow/experiments/probe"
GRAPHQL_ROUTE = "/graphql"


@pytest.fixture(autouse=True)
def clear_denial_audit_throttle():
    """Reset the module-level denial-audit window between tests.

    It is deliberately process-wide state, so without this a denial recorded by one test
    suppresses the audit event another test asserts on — and the failure looks like a missing
    event rather than leftover state.
    """
    auth_middleware_module._denial_audit_seen.clear()
    yield
    auth_middleware_module._denial_audit_seen.clear()


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", s)
    yield s
    object.__setattr__(store_module.store, "_instance", previous)
    s.engine.dispose()


@pytest.fixture
def client(store):
    """The real stack: AuthMiddleware in front, Flask mounted underneath at ``/``.

    Mirrors ``app.py`` — FastAPI routes registered first so they take precedence over the
    catch-all Flask mount — with a stand-in Flask app rather than MLflow's, since what is under
    test is whether the request reaches Flask at all.
    """
    flask_app = Flask(__name__)

    @flask_app.route(FLASK_ROUTE)
    def flask_probe():
        return {"reached": "flask"}

    @flask_app.route(GRAPHQL_ROUTE, methods=["GET", "POST"])
    def graphql_probe():
        return {"reached": "graphql"}

    api = FastAPI()

    @api.get(FASTAPI_ROUTE)
    async def fastapi_probe(request: Request):
        return {"reached": "fastapi", "username": getattr(request.state, "username", None)}

    @api.get(LOGIN)
    async def login(request: Request, username: str):
        request.session["username"] = username
        return {"ok": True}

    api.add_middleware(AuthMiddleware)
    api.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential")
    api.mount("/", AuthAwareWSGIMiddleware(flask_app))

    with TestClient(api) as c:
        yield c


ALL_SURFACES = [FASTAPI_ROUTE, FLASK_ROUTE, GRAPHQL_ROUTE]


class TestSurfacesAreReachableWhileTheUserExists:
    """Preconditions. Without these, the denial tests below could pass for the wrong reason —
    a route that never worked is not evidence of a closed gap."""

    @pytest.mark.parametrize("path", ALL_SURFACES)
    def test_a_live_user_reaches_every_surface(self, store, client, path):
        store.create_user("live@example.com", PASSWORD, "Live")
        client.get(LOGIN, params={"username": "live@example.com"})

        response = client.get(path)

        assert response.status_code == 200, response.text


class TestDeletedUserIsDeniedOnEverySurface:
    """The gap #306 suspected: a signed, unexpired cookie for an account that no longer exists."""

    @pytest.mark.parametrize("path", ALL_SURFACES)
    def test_a_deleted_user_is_denied(self, store, client, path):
        store.create_user("gone@example.com", PASSWORD, "Gone")
        store.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)
        client.get(LOGIN, params={"username": "gone@example.com"})
        assert client.get(path).status_code == 200, "precondition: the surface is reachable first"

        store.delete_user("gone@example.com")

        assert client.get(path).status_code == 401

    def test_the_request_never_reaches_flask(self, store, client):
        """Denied *before* the mount, not by a downstream permission check.

        The distinction matters: if the request reached Flask, every route without a validator
        would be exposed to a deleted user, and the fix would be one forgotten validator away
        from failing.
        """
        store.create_user("gone@example.com", PASSWORD, "Gone")
        store.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)
        client.get(LOGIN, params={"username": "gone@example.com"})
        store.delete_user("gone@example.com")

        response = client.get(FLASK_ROUTE)

        assert response.status_code == 401
        assert "reached" not in response.text

    def test_the_deleted_user_is_not_merely_downgraded(self, store, client):
        """The behaviour the issue described: authenticated, but non-admin. That would let a
        deleted account keep whatever access a non-admin has."""
        store.create_user("gone@example.com", PASSWORD, "Gone", is_admin=True)
        store.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)
        client.get(LOGIN, params={"username": "gone@example.com"})
        store.delete_user("gone@example.com")

        response = client.get(FASTAPI_ROUTE)

        assert response.status_code == 401
        assert response.json().get("username") is None

    def test_recreating_the_user_restores_access(self, store, client):
        """The cookie was never invalidated — only the account state changed — so a same-named
        account restores access. Worth pinning: it is the behaviour a server-side session store
        (#310) would change, and #310 should know it is changing it deliberately.
        """
        store.create_user("gone@example.com", PASSWORD, "Gone")
        store.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)
        client.get(LOGIN, params={"username": "gone@example.com"})
        store.delete_user("gone@example.com")
        assert client.get(FASTAPI_ROUTE).status_code == 401

        store.create_user("gone@example.com", PASSWORD, "Gone Again")

        assert client.get(FASTAPI_ROUTE).status_code == 200


class TestDenialAuditIsThrottled:
    """A revoked cookie keeps arriving, and one audit event per request would let a single stale
    session bury the forensic record — or let someone holding such a cookie dilute it on purpose.
    Raised in review of #348.
    """

    def _deny_repeatedly(self, store, client, monkeypatch, username, times):
        events = []
        monkeypatch.setattr(
            "mlflow_oidc_auth.middleware.auth_middleware.emit_audit_event",
            lambda event, **kwargs: events.append((event, kwargs)),
        )
        client.get(LOGIN, params={"username": username})
        store.delete_user(username)
        for _ in range(times):
            assert client.get(FASTAPI_ROUTE).status_code == 401
        return events

    def test_repeated_denials_audit_once(self, store, client, monkeypatch):
        store.create_user("gone@example.com", PASSWORD, "Gone")
        store.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)

        events = self._deny_repeatedly(store, client, monkeypatch, "gone@example.com", times=25)

        assert len(events) == 1, f"expected one audit event for 25 denials, got {len(events)}"

    def test_every_request_is_still_denied(self, store, client, monkeypatch):
        """Throttling the record must never throttle the decision."""
        store.create_user("gone@example.com", PASSWORD, "Gone")
        store.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)
        self._deny_repeatedly(store, client, monkeypatch, "gone@example.com", times=5)

        assert client.get(FASTAPI_ROUTE).status_code == 401

    def test_a_different_user_is_audited_separately(self, store, client, monkeypatch):
        """Suppression is per (username, reason); one noisy session must not hide another."""
        events = []
        monkeypatch.setattr(
            "mlflow_oidc_auth.middleware.auth_middleware.emit_audit_event",
            lambda event, **kwargs: events.append((event, kwargs)),
        )
        for name in ("a@example.com", "b@example.com"):
            store.create_user(name, PASSWORD, name)
        store.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)

        for name in ("a@example.com", "b@example.com"):
            client.get(LOGIN, params={"username": name})
            store.delete_user(name)
            client.get(FASTAPI_ROUTE)
            client.get(FASTAPI_ROUTE)

        assert sorted(kwargs["actor"] for _, kwargs in events) == ["a@example.com", "b@example.com"]

    def test_a_different_reason_for_the_same_user_is_audited_separately(self, store, client, monkeypatch):
        """Deactivated then deleted is two distinct events about one account."""
        from sqlalchemy import text

        events = []
        monkeypatch.setattr(
            "mlflow_oidc_auth.middleware.auth_middleware.emit_audit_event",
            lambda event, **kwargs: events.append(event),
        )
        store.create_user("x@example.com", PASSWORD, "X")
        store.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)
        client.get(LOGIN, params={"username": "x@example.com"})

        with store.engine.begin() as conn:
            conn.execute(text("UPDATE users SET active = 0 WHERE username = 'x@example.com'"))
        client.get(FASTAPI_ROUTE)
        store.delete_user("x@example.com")
        client.get(FASTAPI_ROUTE)

        assert events == ["auth.denied_inactive", "auth.denied_unknown_user"]

    def test_the_throttle_cache_is_bounded(self):
        """An attacker rotating usernames must not grow this without limit; evicting only ever
        costs a duplicate audit entry, never a missed denial."""
        assert auth_middleware_module._denial_audit_seen.maxsize <= 4096


class TestAdminStatusShim:
    def test_an_inactive_admin_is_not_reported_as_admin(self, store):
        """A method named "is this an admin" must not answer True for an account being turned
        away — these are exactly the deprovisioned admins #311 exists to shut out."""
        from sqlalchemy import text

        middleware = AuthMiddleware.__new__(AuthMiddleware)
        store.create_user("adm@example.com", PASSWORD, "Adm", is_admin=True)
        store.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)
        assert middleware._get_user_admin_status("adm@example.com") is True

        with store.engine.begin() as conn:
            conn.execute(text("UPDATE users SET active = 0 WHERE username = 'adm@example.com'"))

        assert middleware._get_user_admin_status("adm@example.com") is False

    def test_a_deleted_admin_is_not_reported_as_admin(self, store):
        middleware = AuthMiddleware.__new__(AuthMiddleware)
        store.create_user("adm@example.com", PASSWORD, "Adm", is_admin=True)
        store.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)

        store.delete_user("adm@example.com")

        assert middleware._get_user_admin_status("adm@example.com") is False


class TestDenialIsReportedAsDeletion:
    """A deleted user is not an inactive one, and an operator reading the log should not have to
    guess which happened."""

    def test_the_audit_event_names_deletion(self, store, client, monkeypatch):
        events = []
        monkeypatch.setattr(
            "mlflow_oidc_auth.middleware.auth_middleware.emit_audit_event",
            lambda event, **kwargs: events.append((event, kwargs)),
        )
        store.create_user("gone@example.com", PASSWORD, "Gone")
        store.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)
        client.get(LOGIN, params={"username": "gone@example.com"})
        store.delete_user("gone@example.com")

        client.get(FASTAPI_ROUTE)

        assert events, "a denial must be audited"
        event, kwargs = events[0]
        assert event == "auth.denied_unknown_user"
        assert kwargs["status"] == "denied"

    def test_an_inactive_user_is_still_reported_as_inactive(self, store, client, monkeypatch):
        """The two reasons must stay distinguishable in both directions."""
        from sqlalchemy import text

        events = []
        monkeypatch.setattr(
            "mlflow_oidc_auth.middleware.auth_middleware.emit_audit_event",
            lambda event, **kwargs: events.append((event, kwargs)),
        )
        store.create_user("off@example.com", PASSWORD, "Off")
        client.get(LOGIN, params={"username": "off@example.com"})
        with store.engine.begin() as conn:
            conn.execute(text("UPDATE users SET active = 0 WHERE username = 'off@example.com'"))

        client.get(FASTAPI_ROUTE)

        assert events[0][0] == "auth.denied_inactive"

    def test_a_missing_user_is_not_logged_as_an_error(self, store, client, caplog):
        """A user deleted mid-session is an ordinary condition, and their browser will keep
        retrying with the same cookie. Logging it at ERROR would fill the log with something
        the operator can do nothing about.
        """
        import logging

        store.create_user("gone@example.com", PASSWORD, "Gone")
        store.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)
        client.get(LOGIN, params={"username": "gone@example.com"})
        store.delete_user("gone@example.com")

        with caplog.at_level(logging.DEBUG):
            client.get(FASTAPI_ROUTE)

        errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert not errors, [r.message for r in errors]
