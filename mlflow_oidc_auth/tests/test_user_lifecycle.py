"""User lifecycle: inactive denial, the last-admin invariant, and break-glass recovery (#311).

Directories deprovision by setting ``active=false`` rather than deleting — Entra sends
``PATCH active:false`` — so a deprovisioned user keeps a valid cookie or an unexpired token.
Credentials alone still check out, which is why the denial has to happen in the auth path
rather than being left to downstream permission checks.

Enforcement creates a lockout risk, the invariant prevents it and the CLI recovers from it;
the three are tested together because they are one safety story.
"""

import base64
import time

import pytest
from authlib.jose import JsonWebKey, jwt
from click.testing import CliRunner
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from mlflow.exceptions import MlflowException
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

import mlflow_oidc_auth.auth as auth_module
import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth.db.cli import commands
from mlflow_oidc_auth.middleware import AuthMiddleware

PASSWORD = "lifecycle-password"  # not a credential: only ever seeded into a tmp_path database
PROTECTED = "/lifecycle/protected"
LOGIN = "/login/lifecycle"


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    yield s
    s.engine.dispose()


@pytest.fixture
def bound_store(store):
    """Point the lazy singleton at the test store; AuthMiddleware imports it directly."""
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", store)
    yield store
    object.__setattr__(store_module.store, "_instance", previous)


@pytest.fixture
def bearer_token(monkeypatch):
    """Prime the JWKS cache with a local key and return a token minter."""
    key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    private, public = key.as_dict(is_private=True), key.as_dict(is_private=False)
    kid = public.get("kid") or key.thumbprint()
    public["kid"] = private["kid"] = kid
    monkeypatch.setattr(auth_module.config, "OIDC_DISCOVERY_URL", "https://test.invalid/.well-known/openid-configuration")
    monkeypatch.setitem(auth_module._jwks_cache, auth_module._JWKS_CACHE_KEY, {"keys": [public]})

    def mint(username: str) -> str:
        now = int(time.time())
        return jwt.encode({"alg": "RS256", "kid": kid}, {"email": username, "name": username, "iat": now, "exp": now + 3600}, private).decode("utf-8")

    return mint


@pytest.fixture
def client(bound_store):
    app = FastAPI()

    @app.get(PROTECTED)
    async def protected(request: Request):
        return {"username": getattr(request.state, "username", None)}

    @app.get(LOGIN)
    async def login(request: Request, username: str):
        request.session["username"] = username
        return {"ok": True}

    app.add_middleware(AuthMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential")
    with TestClient(app) as c:
        yield c


def deactivate(store, username: str) -> None:
    """Deactivate out-of-band.

    The store refuses to deactivate the last active admin — correctly — so tests that need an
    inactive user either use a non-admin or go around the guard, the way a restored backup or a
    sync predating the guard would.
    """
    with store.engine.begin() as conn:
        conn.execute(text("UPDATE users SET active = 0 WHERE username = :u"), {"u": username})


class TestInactiveUserIsDeniedOnEveryAuthPath:
    """One test per path, because each presents credentials differently and each must deny."""

    def test_session_path_denies_an_inactive_user(self, store, client):
        store.create_user("s@example.com", PASSWORD, "S")
        client.get(LOGIN, params={"username": "s@example.com"})
        assert client.get(PROTECTED).status_code == 200, "precondition: an active user is allowed"

        deactivate(store, "s@example.com")

        assert client.get(PROTECTED).status_code == 401

    def test_bearer_path_denies_an_inactive_user(self, store, client, bearer_token):
        store.create_user("b@example.com", PASSWORD, "B")
        token = bearer_token("b@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get(PROTECTED, headers=headers).status_code == 200

        deactivate(store, "b@example.com")

        assert client.get(PROTECTED, headers=headers).status_code == 401

    def test_basic_path_denies_an_inactive_user(self, store, client):
        store.create_user("a@example.com", PASSWORD, "A")
        credentials = base64.b64encode(f"a@example.com:{PASSWORD}".encode()).decode()
        headers = {"Authorization": f"Basic {credentials}"}
        assert client.get(PROTECTED, headers=headers).status_code == 200

        deactivate(store, "a@example.com")

        assert client.get(PROTECTED, headers=headers).status_code == 401

    def test_a_still_valid_session_cookie_does_not_help(self, store, client):
        """The point of enforcing here: the cookie is signed, unexpired and genuine. Only the
        account state changed."""
        store.create_user("c@example.com", PASSWORD, "C")
        client.get(LOGIN, params={"username": "c@example.com"})
        deactivate(store, "c@example.com")

        response = client.get(PROTECTED)

        assert response.status_code == 401
        assert response.json().get("username") is None

    def test_reactivating_restores_access(self, store, client):
        store.create_user("r@example.com", PASSWORD, "R")
        client.get(LOGIN, params={"username": "r@example.com"})
        deactivate(store, "r@example.com")
        assert client.get(PROTECTED).status_code == 401

        store.update_user(username="r@example.com", active=True)

        assert client.get(PROTECTED).status_code == 200

    def test_an_active_user_is_unaffected(self, store, client):
        """Back-compat: every existing row is active=true after the #333 backfill, so no
        deployment changes behaviour."""
        store.create_user("ok@example.com", PASSWORD, "OK")
        client.get(LOGIN, params={"username": "ok@example.com"})

        assert client.get(PROTECTED).status_code == 200


class TestInactiveDenialCostsNoExtraQuery:
    def test_the_statement_count_is_unchanged(self, store, client):
        """``active`` rides along in the ``load_only`` list #333 added, so the #305 budget of 2
        statements per authenticated request still holds."""
        from sqlalchemy import event

        store.create_user("q@example.com", PASSWORD, "Q")
        client.get(LOGIN, params={"username": "q@example.com"})
        client.get(PROTECTED)

        statements = []

        def listener(conn, cursor, statement, parameters, context, executemany):
            if not statement.lstrip().upper().startswith(("PRAGMA", "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE")):
                statements.append(statement)

        event.listen(store.engine, "before_cursor_execute", listener)
        try:
            client.get(PROTECTED)
        finally:
            event.remove(store.engine, "before_cursor_execute", listener)

        assert len(statements) == 2, statements


class TestLastActiveAdminInvariant:
    """Refusing is cheap; recovering from a full lockout needs database access."""

    def test_deleting_the_last_active_admin_is_refused(self, store):
        store.create_user("admin@example.com", PASSWORD, "Admin", is_admin=True)
        store.create_user("plain@example.com", PASSWORD, "Plain")

        with pytest.raises(MlflowException, match="only active administrator"):
            store.delete_user("admin@example.com")

        assert store.get_user_profile("admin@example.com").is_admin is True

    def test_deactivating_the_last_active_admin_is_refused(self, store):
        store.create_user("admin@example.com", PASSWORD, "Admin", is_admin=True)

        with pytest.raises(MlflowException, match="only active administrator"):
            store.update_user(username="admin@example.com", active=False)

        assert store.get_user_profile("admin@example.com").active is True

    def test_demoting_the_last_active_admin_is_refused(self, store):
        """Demotion locks everyone out exactly as thoroughly as deletion."""
        store.create_user("admin@example.com", PASSWORD, "Admin", is_admin=True)

        with pytest.raises(MlflowException, match="only active administrator"):
            store.update_user(username="admin@example.com", is_admin=False)

        assert store.get_user_profile("admin@example.com").is_admin is True

    @pytest.mark.parametrize("operation", ["delete", "deactivate", "demote"])
    def test_any_of_them_is_allowed_while_another_active_admin_remains(self, store, operation):
        store.create_user("admin@example.com", PASSWORD, "Admin", is_admin=True)
        store.create_user("admin2@example.com", PASSWORD, "Admin2", is_admin=True)

        if operation == "delete":
            store.delete_user("admin@example.com")
            assert store.has_user("admin@example.com") is False
        elif operation == "deactivate":
            store.update_user(username="admin@example.com", active=False)
            assert store.get_user_profile("admin@example.com").active is False
        else:
            store.update_user(username="admin@example.com", is_admin=False)
            assert store.get_user_profile("admin@example.com").is_admin is False

    def test_an_inactive_admin_does_not_count_towards_the_invariant(self, store):
        """Two admins on paper, one of them deactivated, is still one active admin."""
        store.create_user("admin@example.com", PASSWORD, "Admin", is_admin=True)
        store.create_user("admin2@example.com", PASSWORD, "Admin2", is_admin=True)
        deactivate(store, "admin2@example.com")

        with pytest.raises(MlflowException, match="only active administrator"):
            store.delete_user("admin@example.com")

    def test_removing_a_non_admin_is_never_blocked(self, store):
        store.create_user("admin@example.com", PASSWORD, "Admin", is_admin=True)
        store.create_user("plain@example.com", PASSWORD, "Plain")

        store.delete_user("plain@example.com")

        assert store.has_user("plain@example.com") is False

    def test_removing_an_already_inactive_admin_is_allowed(self, store):
        """They cannot log in, so they are not the administrator anyone is relying on."""
        store.create_user("admin@example.com", PASSWORD, "Admin", is_admin=True)
        store.create_user("old@example.com", PASSWORD, "Old", is_admin=True)
        deactivate(store, "old@example.com")

        store.delete_user("old@example.com")

        assert store.has_user("old@example.com") is False


class TestBreakGlassCli:
    """The way back when the invariant was bypassed — a restored backup, or a sync that ran
    before the guard existed. Nothing inside the system can fix it: every route that grants
    admin requires an admin."""

    def _url(self, store) -> str:
        return store.engine.url.render_as_string(hide_password=False)

    def test_it_restores_an_admin_who_cannot_log_in(self, store):
        store.create_user("admin@example.com", PASSWORD, "Admin", is_admin=True)
        with store.engine.begin() as conn:
            conn.execute(text("UPDATE users SET active = 0, managed_by = 'scim' WHERE username = 'admin@example.com'"))

        result = CliRunner().invoke(commands, ["restore-admin", "--url", self._url(store), "--username", "admin@example.com"])

        assert result.exit_code == 0, result.output
        profile = store.get_user_profile("admin@example.com")
        assert (profile.is_admin, profile.active) == (True, True)

    def test_it_resets_managed_by(self, store):
        """Leaving the row owned by ``scim`` invites the next sync to undo the repair, and the
        #319 guard to refuse an admin's later edits to it."""
        store.create_user("admin@example.com", PASSWORD, "Admin", is_admin=True)
        with store.engine.begin() as conn:
            conn.execute(text("UPDATE users SET active = 0, managed_by = 'oidc:entra' WHERE username = 'admin@example.com'"))

        CliRunner().invoke(commands, ["restore-admin", "--url", self._url(store), "--username", "admin@example.com"])

        assert store.get_user_profile("admin@example.com").managed_by == "manual"

    def test_it_promotes_a_non_admin(self, store):
        """The realistic lockout is that nobody is left with admin at all."""
        store.create_user("plain@example.com", PASSWORD, "Plain")

        result = CliRunner().invoke(commands, ["restore-admin", "--url", self._url(store), "--username", "plain@example.com"])

        assert result.exit_code == 0
        assert store.get_user_profile("plain@example.com").is_admin is True

    def test_the_restored_admin_can_authenticate_again(self, store, client):
        """End to end: the recovery is only real if it restores access."""
        store.create_user("admin@example.com", PASSWORD, "Admin", is_admin=True)
        client.get(LOGIN, params={"username": "admin@example.com"})
        deactivate(store, "admin@example.com")
        assert client.get(PROTECTED).status_code == 401

        CliRunner().invoke(commands, ["restore-admin", "--url", self._url(store), "--username", "admin@example.com"])

        assert client.get(PROTECTED).status_code == 200

    def test_an_unknown_user_is_an_error_not_a_silent_no_op(self, store):
        result = CliRunner().invoke(commands, ["restore-admin", "--url", self._url(store), "--username", "ghost@example.com"])

        assert result.exit_code != 0
        assert "does not exist" in result.output

    def test_it_reports_what_it_changed(self, store):
        """An out-of-band privilege grant has to be visible afterwards."""
        store.create_user("admin@example.com", PASSWORD, "Admin", is_admin=True)
        deactivate(store, "admin@example.com")

        result = CliRunner().invoke(commands, ["restore-admin", "--url", self._url(store), "--username", "admin@example.com"])

        assert "admin@example.com" in result.output
        assert "active False -> True" in result.output
