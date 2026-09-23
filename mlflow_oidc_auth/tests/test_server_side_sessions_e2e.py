"""Server-side sessions, end to end through the real middleware (issue #310).

The repository tests prove the rows behave; these prove the *request* does. Two properties are
worth holding at this level because both are invisible from the repository:

1. **Revoking a session ends the next request**, with no TTL and no cache in between.
2. **A cookie minted before this change no longer authenticates.** The old cookie carried the
   username itself; honouring one would mean honouring a credential the server has no record of
   and cannot revoke — which is the whole defect. Everyone logs in again once, deliberately.
3. **Provider tokens never transit the cookie** (#367). The refresh token and IdP expiry live
   encrypted on the session row; a cookie from before that change is cleaned, not trusted.
"""

import base64
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


def _basic(username: str, token: str) -> dict:
    """An Authorization header for the username/token pair MLflow clients use."""
    encoded = base64.b64encode(f"{username}:{token}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def _patch_live_configs(monkeypatch, **values):
    """Set ``values`` on every config object the code under test actually reads.

    Some suites delete ``mlflow_oidc_auth.config`` from ``sys.modules``, after which the
    middleware and router keep the object they imported while a fresh import yields another.
    """
    from mlflow_oidc_auth.config import config as current
    from mlflow_oidc_auth.middleware import auth_middleware as middleware_module
    from mlflow_oidc_auth.routers import auth as auth_module

    targets = {id(c): c for c in (current, middleware_module.config, auth_module.config)}
    for cfg in targets.values():
        for name, value in values.items():
            monkeypatch.setattr(cfg, name, value, raising=False)


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


class TestUserTokensAreIndependentOfSessions:
    """Sessions moved server-side; user tokens did not.

    Both credentials name the same account, so the two now have to be shown not to interfere:
    a browser session must not be needed to use a token, revoking sessions must not disable a
    token, and rotating a token must not log the browser out. Deprovisioning is the one place
    they *must* agree — a deactivated user is refused on either.
    """

    def test_a_token_authenticates_with_no_cookie_at_all(self, client, store):
        response = client.get(PROTECTED, headers=_basic(USERNAME, PASSWORD))

        assert response.status_code == 200
        assert response.json()["username"] == USERNAME

    def test_a_wrong_token_is_refused(self, client):
        assert client.get(PROTECTED, headers=_basic(USERNAME, "not-the-token")).status_code == 401

    def test_a_token_still_works_after_every_session_is_revoked(self, client, store):
        """Revocation ends browser sessions. It is not a way to disable API access."""
        client.get(LOGIN)
        store.revoke_all_auth_sessions(USERNAME)
        assert client.get(PROTECTED).status_code == 401, "precondition: the cookie is dead"

        assert client.get(PROTECTED, headers=_basic(USERNAME, PASSWORD)).status_code == 200

    def test_rotating_the_token_does_not_end_the_browser_session(self, store, client):
        """The session is a row of its own; it does not hang off the password hash."""
        client.get(LOGIN)
        store.update_user(USERNAME, password="rotated-token", password_expiration=None)

        assert client.get(PROTECTED).status_code == 200

    def test_rotating_the_token_invalidates_the_old_one(self, client, store):
        store.update_user(USERNAME, password="rotated-token", password_expiration=None)

        assert client.get(PROTECTED, headers=_basic(USERNAME, PASSWORD)).status_code == 401
        assert client.get(PROTECTED, headers=_basic(USERNAME, "rotated-token")).status_code == 200

    def test_a_cookie_is_ignored_when_a_token_is_presented(self, client, store):
        """The Authorization header wins outright, so a revoked session cannot leak its stale
        admin or active flags into a token-authenticated request."""
        client.get(LOGIN)
        store.revoke_all_auth_sessions(USERNAME)

        response = client.get(PROTECTED, headers=_basic(USERNAME, PASSWORD))

        assert response.status_code == 200
        assert response.json()["username"] == USERNAME

    def test_deactivating_the_user_refuses_both_credentials(self, client, store):
        """The one place the two must agree."""
        client.get(LOGIN)
        store.update_user(USERNAME, active=False)

        assert client.get(PROTECTED).status_code == 401
        assert client.get(PROTECTED, headers=_basic(USERNAME, PASSWORD)).status_code == 401

    def test_deleting_the_user_refuses_both_credentials(self, client, store):
        client.get(LOGIN)
        store.delete_user(USERNAME)

        assert client.get(PROTECTED).status_code == 401
        assert client.get(PROTECTED, headers=_basic(USERNAME, PASSWORD)).status_code == 401

    def test_an_expired_token_is_refused_while_the_session_still_works(self, client, store):
        """Token expiry and session expiry are separate clocks, and neither drives the other."""
        client.get(LOGIN)
        store.update_user(USERNAME, password=PASSWORD, password_expiration=datetime.now(timezone.utc) - timedelta(seconds=1))

        assert client.get(PROTECTED, headers=_basic(USERNAME, PASSWORD)).status_code == 401
        assert client.get(PROTECTED).status_code == 200


# --- Provider tokens live on the row, never in the cookie (#367) -----------------------------

REFRESH_TOKEN_ISSUED = "rt-issued-at-login"  # test-only strings, never real credentials
REFRESH_TOKEN_ROTATED = "rt-rotated-by-idp"
ID_TOKEN_ISSUED = "idt-issued-at-login"
EXPIRE_ROW = "/login/e2e-expire"
LEGACY_TOKENS_LOGIN = "/login/e2e-legacy-tokens"


def _cookie_payload(client) -> dict:
    """The decoded contents of Starlette's signed session cookie (base64 JSON, then signature)."""
    import json

    raw = client.cookies.get("session")
    if not raw:
        return {}
    data = raw.split(".")[0]
    return json.loads(base64.b64decode(data + "=" * (-len(data) % 4)))


class _RotatingIdP:
    """A token endpoint with refresh-token rotation and reuse detection."""

    def __init__(self, fail: bool = False):
        self.calls = []
        self.valid = REFRESH_TOKEN_ISSUED
        self.fail = fail

    async def fetch_access_token(self, grant_type, refresh_token):
        import time

        self.calls.append(refresh_token)
        if self.fail or refresh_token != self.valid:
            raise RuntimeError("invalid_grant")
        self.valid = REFRESH_TOKEN_ROTATED
        return {"access_token": "at", "expires_at": int(time.time()) + 3600, "refresh_token": REFRESH_TOKEN_ROTATED}


@pytest.fixture
def token_client(store, monkeypatch):
    """The real middleware plus the real OIDC callback tail, with a fake IdP behind it."""
    import time

    from mlflow_oidc_auth.routers import auth as auth_module
    from mlflow_oidc_auth.session.token_vault import SessionTokens, get_token_vault

    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", store)

    idp = _RotatingIdP()
    _patch_live_configs(monkeypatch, OIDC_USE_REFRESH_TOKEN=True, OIDC_SESSION_EXPIRY_LEEWAY_SECONDS=0)
    monkeypatch.setattr(auth_module, "oauth", type("FakeOAuth", (), {"oidc": idp})())
    monkeypatch.setattr(auth_module, "is_oidc_configured", lambda provider_id=None: True)

    async def fake_process(request, session, provider_id=None):
        # What the real ``_process_oidc_callback_fastapi`` does after its state check: retire the
        # login this browser carried, then leave this login's tokens for the session row.
        auth_module._retire_previous_login(session)
        request.state.pending_session_tokens = auth_module._session_tokens_from_response(
            {"expires_at": int(time.time()) + 3600, "refresh_token": REFRESH_TOKEN_ISSUED, "id_token": ID_TOKEN_ISSUED},
            provider_id="default",
        )
        return USERNAME, []

    monkeypatch.setattr(auth_module, "_process_oidc_callback_fastapi", fake_process)

    app = FastAPI()

    @app.get(PROTECTED)
    async def protected(request: Request):
        return {"username": getattr(request.state, "username", None)}

    @app.get(EXPIRE_ROW)
    async def expire_row(request: Request):
        # Age the IdP expiry on the row, as time passing would.
        sid = request.session["session_id"]
        vault = get_token_vault()
        tokens = vault.decrypt(store_module.store.resolve_auth_session(sid).encrypted_tokens)
        aged = SessionTokens(**{**tokens.to_dict(), "expires_at": 100})
        store_module.store.store_auth_session_tokens(sid, vault.encrypt(aged))
        return {"ok": True}

    @app.get(LEGACY_TOKENS_LOGIN)
    async def legacy_tokens(request: Request, expires_at: int = 9999999999):
        # A cookie from before #367: a real session id, plus token material in the cookie.
        request.session["session_id"] = store_module.store.create_auth_session(USERNAME, expires_at=datetime.now(timezone.utc) + timedelta(hours=8))
        request.session["expires_at"] = expires_at
        request.session["refresh_token"] = "rt-in-a-legacy-cookie"
        return {"ok": True}

    # After the test routes: the router's "/login/{provider_id}" would otherwise shadow them.
    app.include_router(auth_module.auth_router)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential")

    try:
        with TestClient(app, follow_redirects=False) as c:
            c.idp = idp
            yield c
    finally:
        object.__setattr__(store_module.store, "_instance", previous)


def _row_tokens(store):
    from mlflow_oidc_auth.session.token_vault import get_token_vault

    sid = store.auth_session_repo.list_live_for_user(USERNAME)[0]
    return get_token_vault().decrypt(store.resolve_auth_session(sid).encrypted_tokens)


class TestTokensNeverTransitTheCookie:
    def test_after_login_the_cookie_holds_only_the_session_id(self, token_client, store):
        response = token_client.get("/callback")

        assert response.status_code == 302
        payload = _cookie_payload(token_client)
        assert set(payload) <= {"session_id", "authenticated"}
        assert "refresh_token" not in payload and "expires_at" not in payload
        cookie = token_client.cookies.get("session")
        assert REFRESH_TOKEN_ISSUED not in cookie and ID_TOKEN_ISSUED not in cookie

        tokens = _row_tokens(store)
        assert tokens.refresh_token == REFRESH_TOKEN_ISSUED
        assert tokens.id_token == ID_TOKEN_ISSUED
        assert tokens.provider_id == "default"
        assert token_client.get(PROTECTED).status_code == 200

    def test_after_refresh_the_cookie_still_holds_only_the_session_id(self, token_client, store):
        token_client.get("/callback")
        token_client.get(EXPIRE_ROW)

        response = token_client.get(PROTECTED)

        assert response.status_code == 200
        assert token_client.idp.calls == [REFRESH_TOKEN_ISSUED]
        payload = _cookie_payload(token_client)
        assert "refresh_token" not in payload and "expires_at" not in payload
        assert REFRESH_TOKEN_ROTATED not in token_client.cookies.get("session")
        assert _row_tokens(store).refresh_token == REFRESH_TOKEN_ROTATED

    def test_a_request_after_the_refresh_does_not_exchange_again(self, token_client):
        token_client.get("/callback")
        token_client.get(EXPIRE_ROW)
        token_client.get(PROTECTED)

        assert token_client.get(PROTECTED).status_code == 200
        assert token_client.idp.calls == [REFRESH_TOKEN_ISSUED]

    def test_a_refused_refresh_ends_the_session(self, token_client, store):
        token_client.get("/callback")
        token_client.get(EXPIRE_ROW)
        token_client.idp.fail = True

        assert token_client.get(PROTECTED).status_code == 401
        assert "session_id" not in _cookie_payload(token_client), "the cookie is cleared"
        assert token_client.get(PROTECTED).status_code == 401

    def test_a_legacy_cookie_is_cleaned_and_not_trusted(self, token_client, store):
        token_client.get(LEGACY_TOKENS_LOGIN)
        assert "refresh_token" in _cookie_payload(token_client), "precondition: a legacy cookie"
        sid = _cookie_payload(token_client)["session_id"]
        # The row says expired and holds nothing to refresh with; the cookie's far-future
        # expiry and refresh token must not rescue it.
        from mlflow_oidc_auth.session.token_vault import SessionTokens, get_token_vault

        store.store_auth_session_tokens(sid, get_token_vault().encrypt(SessionTokens(expires_at=100)))

        assert token_client.get(PROTECTED).status_code == 401
        assert token_client.idp.calls == [], "the cookie's refresh token is never sent to the IdP"
        payload = _cookie_payload(token_client)
        assert "refresh_token" not in payload and "expires_at" not in payload

    def test_a_legacy_expiry_still_bounds_a_row_without_tokens(self, token_client, store):
        """A row from before #367 holds no tokens, so the signed cookie's ``expires_at`` is the only
        IdP bound it has. It is honoured, not dropped: past means re-login."""
        token_client.get(LEGACY_TOKENS_LOGIN, params={"expires_at": 100})

        assert token_client.get(PROTECTED).status_code == 401
        assert _cookie_payload(token_client) == {}, "the session is cleared"
        assert token_client.idp.calls == [], "nothing is refreshed: the row holds no token"
        assert token_client.get(PROTECTED).status_code == 401

    def test_a_future_legacy_expiry_keeps_working_and_keeps_its_bound(self, token_client):
        token_client.get(LEGACY_TOKENS_LOGIN)

        assert token_client.get(PROTECTED).status_code == 200
        payload = _cookie_payload(token_client)
        assert "refresh_token" not in payload, "the cookie's refresh token is dropped at once"
        assert payload.get("expires_at") == 9999999999, "the bound stays until it passes"
        assert "session_id" in payload
        assert token_client.get(PROTECTED).status_code == 200

    def test_a_new_login_replaces_the_legacy_bound(self, token_client, store):
        token_client.get(LEGACY_TOKENS_LOGIN)
        token_client.get("/callback")

        payload = _cookie_payload(token_client)
        assert "expires_at" not in payload and "refresh_token" not in payload
        assert token_client.get(PROTECTED).status_code == 200
