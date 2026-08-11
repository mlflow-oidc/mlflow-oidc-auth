"""Server-side sessions, end to end through the real middleware (issue #310).

The repository tests prove the rows behave; these prove the *request* does. Two properties are
worth holding at this level because both are invisible from the repository:

1. **Revoking a session ends the next request**, with no TTL and no cache in between.
2. **A cookie minted before this change no longer authenticates.** The old cookie carried the
   username itself; honouring one would mean honouring a credential the server has no record of
   and cannot revoke — which is the whole defect. Everyone logs in again once, deliberately.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth.middleware import AuthMiddleware

PASSWORD = "session-e2e-password"  # not a credential: only ever seeded into a tmp_path database
PROTECTED = "/e2e/protected"
LOGIN = "/login/e2e"
LEGACY_LOGIN = "/login/e2e-legacy"
USERNAME = "session-e2e@example.com"


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)
    s.create_user(USERNAME, PASSWORD, "Session E2E")
    yield s
    s.engine.dispose()


@pytest.fixture
def client(store):
    """A TestClient over the real ``AuthMiddleware``, with the store singleton pointed at ``store``.

    Middleware order mirrors ``app.py`` — Auth then Session, which makes Session the outer one,
    so ``request.session`` exists by the time ``AuthMiddleware`` reads it.
    """
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", store)

    app = FastAPI()

    @app.get(PROTECTED)
    async def protected(request: Request):
        return {"username": getattr(request.state, "username", None)}

    @app.get(LOGIN)
    async def login(request: Request):
        # "/login" is an unprotected prefix. Mints the same cookie the OIDC callback does.
        request.session["session_id"] = store_module.store.create_auth_session(USERNAME, expires_at=datetime.now(timezone.utc) + timedelta(hours=8))
        return {"ok": True}

    @app.get(LEGACY_LOGIN)
    async def legacy_login(request: Request):
        # The pre-#310 cookie: the username, signed, and nothing on the server.
        request.session["username"] = USERNAME
        return {"ok": True}

    app.add_middleware(AuthMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential")

    try:
        with TestClient(app) as c:
            yield c
    finally:
        object.__setattr__(store_module.store, "_instance", previous)


class TestSessionAuthentication:
    def test_a_session_cookie_authenticates(self, client):
        client.get(LOGIN)

        response = client.get(PROTECTED)

        assert response.status_code == 200
        assert response.json()["username"] == USERNAME

    def test_no_cookie_is_rejected(self, client):
        assert client.get(PROTECTED).status_code == 401

    def test_an_unknown_session_id_is_rejected(self, client):
        client.get(LOGIN)
        client.cookies.clear()

        assert client.get(PROTECTED).status_code == 401


class TestRevocationEndsTheNextRequest:
    """No TTL, no cache: the request after the revocation fails."""

    def test_revoking_the_session_ends_it(self, client, store):
        client.get(LOGIN)
        assert client.get(PROTECTED).status_code == 200
        session_id = store.auth_session_repo.list_live_for_user(USERNAME)[0]

        store.revoke_auth_session(session_id)

        assert client.get(PROTECTED).status_code == 401

    def test_revoking_every_session_ends_it(self, client, store):
        client.get(LOGIN)
        assert client.get(PROTECTED).status_code == 200

        store.revoke_all_auth_sessions(USERNAME)

        assert client.get(PROTECTED).status_code == 401

    def test_deactivating_the_user_ends_it(self, client, store):
        client.get(LOGIN)
        assert client.get(PROTECTED).status_code == 200

        store.update_user(USERNAME, active=False)

        assert client.get(PROTECTED).status_code == 401

    def test_deleting_the_user_ends_it(self, client, store):
        client.get(LOGIN)
        assert client.get(PROTECTED).status_code == 200

        store.delete_user(USERNAME)

        assert client.get(PROTECTED).status_code == 401


class TestForcedReLogin:
    """The deliberate upgrade cost: existing cookies stop working when this ships."""

    def test_a_pre_310_cookie_does_not_authenticate(self, client):
        client.get(LEGACY_LOGIN)

        response = client.get(PROTECTED)

        assert response.status_code == 401

    def test_a_pre_310_cookie_cannot_be_upgraded_by_naming_a_real_user(self, client, store):
        """The username in the old cookie is not evidence of anything — it never was signed by us
        in a way tied to a server record. It must not be trusted to mint a new session."""
        client.get(LEGACY_LOGIN)
        client.get(PROTECTED)

        assert store.auth_session_repo.list_live_for_user(USERNAME) == []

    def test_logging_in_again_works(self, client):
        client.get(LEGACY_LOGIN)
        assert client.get(PROTECTED).status_code == 401

        client.get(LOGIN)

        assert client.get(PROTECTED).status_code == 200
