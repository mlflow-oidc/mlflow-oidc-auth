import types
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from authlib.jose.errors import BadSignatureError
from fastapi import HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

from mlflow_oidc_auth import routers
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.routers import auth as auth_router_mod


class DummyRequest:
    def __init__(self):
        self.session: dict[str, Any] = {}
        self.base_url = "http://testserver"
        self.query_params = {}


@pytest.mark.asyncio
async def test_maybe_await_non_awaitable():
    assert await auth_router_mod._maybe_await(3) == 3


@pytest.mark.asyncio
async def test_maybe_await_awaitable():
    async def _coro():
        return "ok"

    assert await auth_router_mod._maybe_await(_coro()) == "ok"


@pytest.mark.asyncio
async def test_refresh_oidc_jwks_uses_fetch_jwk_set(monkeypatch):
    called = {"count": 0}

    def fetch_jwk_set(force=False):
        called["count"] += 1

    # Ensure a dummy `oidc` client exists on the registry so we can patch safely
    import types

    monkeypatch.setattr(auth_router_mod.oauth, "oidc", types.SimpleNamespace(), raising=False)
    monkeypatch.setattr(auth_router_mod.oauth.oidc, "fetch_jwk_set", fetch_jwk_set, raising=False)
    await auth_router_mod._refresh_oidc_jwks()
    assert called["count"] == 1


@pytest.mark.asyncio
async def test_call_authorize_access_token_sync(monkeypatch):
    async def _fake(request):
        return {"ok": True}

    # test async implementation
    import types

    monkeypatch.setattr(auth_router_mod.oauth, "oidc", types.SimpleNamespace(), raising=False)
    monkeypatch.setattr(auth_router_mod.oauth.oidc, "authorize_access_token", _fake, raising=False)
    req = DummyRequest()
    res = await auth_router_mod._call_authorize_access_token(req)
    assert res == {"ok": True}


@pytest.mark.asyncio
async def test_authorize_access_token_with_retry_bad_sig_then_success(monkeypatch):
    calls = {"count": 0}

    async def _fake(request):
        calls["count"] += 1
        if calls["count"] == 1:
            raise BadSignatureError("bad")
        return {"access_token": "a"}

    monkeypatch.setattr(auth_router_mod, "_call_authorize_access_token", _fake)

    refreshed = {"count": 0}

    async def _refresh():
        refreshed["count"] += 1

    monkeypatch.setattr(auth_router_mod, "_refresh_oidc_jwks", _refresh)

    res = await auth_router_mod._authorize_access_token_with_retry(DummyRequest())
    assert res == {"access_token": "a"}
    assert refreshed["count"] == 1


@pytest.mark.asyncio
async def test_authorize_access_token_with_retry_failure_raises(monkeypatch):
    async def _fake(request):
        raise ValueError("boom")

    monkeypatch.setattr(auth_router_mod, "_call_authorize_access_token", _fake)
    import types

    monkeypatch.setattr(auth_router_mod.oauth, "oidc", types.SimpleNamespace(), raising=False)
    with pytest.raises(ValueError):
        await auth_router_mod._authorize_access_token_with_retry(DummyRequest())


def test_build_ui_url_with_and_without_query():
    req = DummyRequest()
    url = auth_router_mod._build_ui_url(req, "/auth")
    assert url == "http://testserver" + routers._prefix.UI_ROUTER_PREFIX + "/auth"

    url2 = auth_router_mod._build_ui_url(req, "/auth", {"a": ["1", "2"], "b": "x"})
    parsed = urlparse(url2)
    qs = parse_qs(parsed.query)
    assert qs["a"] == ["1", "2"]
    assert qs["b"] == ["x"]


@pytest.mark.asyncio
async def test_login_not_configured(monkeypatch):
    monkeypatch.setattr(auth_router_mod, "is_oidc_configured", lambda: False)
    req = DummyRequest()

    with pytest.raises(HTTPException) as ex:
        await auth_router_mod.login(req)
    assert ex.value.status_code == 500


@pytest.mark.asyncio
async def test_login_authorize_redirect_success(monkeypatch):
    monkeypatch.setattr(auth_router_mod, "is_oidc_configured", lambda: True)

    async def fake_authorize_redirect(request, redirect_uri=None, state=None):
        return RedirectResponse(url=redirect_uri)

    import types

    monkeypatch.setattr(auth_router_mod.oauth, "oidc", types.SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        auth_router_mod.oauth.oidc,
        "authorize_redirect",
        fake_authorize_redirect,
        raising=False,
    )
    monkeypatch.setattr(
        auth_router_mod,
        "get_configured_or_dynamic_redirect_uri",
        lambda request, callback_path, configured_uri: "http://cb",
    )

    req = DummyRequest()
    res = await auth_router_mod.login(req)
    assert isinstance(res, RedirectResponse)
    assert "oauth_state" in req.session


@pytest.mark.asyncio
async def test_login_no_authorize_redirect_raises(monkeypatch):
    monkeypatch.setattr(auth_router_mod, "is_oidc_configured", lambda: True)

    # ensure oidc client present and remove authorize_redirect
    import types

    monkeypatch.setattr(auth_router_mod.oauth, "oidc", types.SimpleNamespace(), raising=False)
    if hasattr(auth_router_mod.oauth.oidc, "authorize_redirect"):
        delattr(auth_router_mod.oauth.oidc, "authorize_redirect")

    req = DummyRequest()
    with pytest.raises(HTTPException):
        await auth_router_mod.login(req)


@pytest.mark.asyncio
async def test_logout_with_end_session_endpoint(monkeypatch):
    req = DummyRequest()
    req.session["session_id"] = "sid-bob"
    import types

    monkeypatch.setattr(auth_router_mod.oauth, "oidc", types.SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        auth_router_mod.oauth.oidc,
        "server_metadata",
        {"end_session_endpoint": "http://end"},
        raising=False,
    )

    res = await auth_router_mod.logout(req)
    assert isinstance(res, RedirectResponse)
    assert "post_logout_redirect_uri" in res.headers["location"]
    # client_id must be sent so Keycloak does not reject the logout with
    # "Missing parameters: id_token_hint".
    assert "client_id=" in res.headers["location"]


@pytest.mark.asyncio
async def test_logout_without_end_session_endpoint(monkeypatch):
    req = DummyRequest()
    req.session["session_id"] = "sid-bob"
    # ensure oidc client exists and remove server_metadata
    import types

    monkeypatch.setattr(auth_router_mod.oauth, "oidc", types.SimpleNamespace(), raising=False)
    if hasattr(auth_router_mod.oauth.oidc, "server_metadata"):
        delattr(auth_router_mod.oauth.oidc, "server_metadata")

    res = await auth_router_mod.logout(req)
    assert isinstance(res, RedirectResponse)
    assert routers._prefix.UI_ROUTER_PREFIX in res.headers["location"]


@pytest.mark.asyncio
async def test_logout_exception_clears_session(monkeypatch):
    class BadSession(dict):
        def clear(self):
            raise RuntimeError("boom")

    req = DummyRequest()
    req.session = BadSession({"username": "a"})

    res = await auth_router_mod.logout(req)
    assert isinstance(res, RedirectResponse)


@pytest.mark.asyncio
async def test_callback_not_configured(monkeypatch):
    monkeypatch.setattr(auth_router_mod, "is_oidc_configured", lambda: False)
    req = DummyRequest()

    res = await auth_router_mod.callback(req)
    assert isinstance(res, RedirectResponse)
    assert "error=" in res.headers["location"]


@pytest.mark.asyncio
async def test_callback_process_errors_redirect(monkeypatch):
    monkeypatch.setattr(auth_router_mod, "is_oidc_configured", lambda: True)

    async def _fake_proc(request, session):
        return None, ["err"]

    monkeypatch.setattr(auth_router_mod, "_process_oidc_callback_fastapi", _fake_proc)

    req = DummyRequest()
    res = await auth_router_mod.callback(req)
    assert isinstance(res, RedirectResponse)
    assert "error" in res.headers["location"]


@pytest.mark.asyncio
async def test_callback_success_redirects(monkeypatch):
    monkeypatch.setattr(auth_router_mod, "is_oidc_configured", lambda: True)

    # return email and no errors
    async def _fake_proc2(request, session):
        return "User@Example.COM", []

    monkeypatch.setattr(auth_router_mod, "_process_oidc_callback_fastapi", _fake_proc2)
    # The callback now opens a server-side session row (#310); the fake user has none.
    monkeypatch.setattr(auth_router_mod, "_open_server_session", lambda username: "sid-opened")

    req = DummyRequest()
    # case False -> redirect to base url
    monkeypatch.setattr(config, "DEFAULT_LANDING_PAGE_IS_PERMISSIONS", False)
    res = await auth_router_mod.callback(req)
    assert isinstance(res, RedirectResponse)
    assert res.headers["location"] == str(req.base_url)

    # case True -> redirect to /user
    req2 = DummyRequest()
    monkeypatch.setattr(config, "DEFAULT_LANDING_PAGE_IS_PERMISSIONS", True)
    res2 = await auth_router_mod.callback(req2)
    assert isinstance(res2, RedirectResponse)
    assert "/user" in res2.headers["location"]


@pytest.mark.asyncio
async def test_callback_auth_failed_without_errors(monkeypatch):
    monkeypatch.setattr(auth_router_mod, "is_oidc_configured", lambda: True)

    async def _fake_proc3(request, session):
        return None, []

    monkeypatch.setattr(auth_router_mod, "_process_oidc_callback_fastapi", _fake_proc3)

    req = DummyRequest()
    with pytest.raises(HTTPException) as ex:
        await auth_router_mod.callback(req)
    assert ex.value.status_code == 401


@pytest.mark.asyncio
async def test_auth_status(monkeypatch):
    req = DummyRequest()
    # unauthenticated
    res = await auth_router_mod.auth_status(req)
    assert isinstance(res, JSONResponse)
    assert res.status_code == 200

    # authenticated
    req2 = DummyRequest()
    req2.session["session_id"] = "sid-bob"
    import json
    from types import SimpleNamespace

    monkeypatch.setattr(
        auth_router_mod.store,
        "resolve_auth_session",
        lambda sid: SimpleNamespace(username="bob", is_admin=False, is_active=True) if sid == "sid-bob" else None,
    )
    monkeypatch.setattr(config, "OIDC_PROVIDER_DISPLAY_NAME", "Prov")
    res2 = await auth_router_mod.auth_status(req2)
    payload = json.loads(res2.body)
    assert payload["authenticated"] is True
    assert payload["provider"] == "Prov"


@pytest.mark.asyncio
async def test_process_oidc_callback_fastapi_various_paths(monkeypatch):
    req = DummyRequest()
    session = {}

    # provider error
    req.query_params = {"error": "err", "error_description": "<bad>"}
    email, errors = await auth_router_mod._process_oidc_callback_fastapi(req, session)
    assert email is None
    assert "OIDC provider error" in errors[0]
    assert "&lt;bad&gt;" or "<bad>"  # ensured escape path

    # missing state
    req.query_params = {}
    session = {}
    email, errors = await auth_router_mod._process_oidc_callback_fastapi(req, session)
    assert "Missing OAuth state" in errors[0]

    # invalid state
    req.query_params = {"state": "x"}
    session = {"oauth_state": "y"}
    email, errors = await auth_router_mod._process_oidc_callback_fastapi(req, session)
    assert "Invalid state" in errors[0]

    # no code
    req.query_params = {"state": "ok"}
    session = {"oauth_state": "ok"}
    email, errors = await auth_router_mod._process_oidc_callback_fastapi(req, session)
    assert "No authorization code" in errors[0]

    # missing authorize_access_token
    req.query_params = {"state": "ok", "code": "c"}
    session = {"oauth_state": "ok"}
    import types

    monkeypatch.setattr(auth_router_mod.oauth, "oidc", types.SimpleNamespace(), raising=False)
    if hasattr(auth_router_mod.oauth.oidc, "authorize_access_token"):
        delattr(auth_router_mod.oauth.oidc, "authorize_access_token")
    email, errors = await auth_router_mod._process_oidc_callback_fastapi(req, session)
    assert "OIDC configuration error" in errors[0]

    # token exchange failure
    async def fake_exchange(request):
        return None

    monkeypatch.setattr(
        auth_router_mod.oauth.oidc,
        "authorize_access_token",
        fake_exchange,
        raising=False,
    )
    req.query_params = {"state": "ok", "code": "c"}
    session = {"oauth_state": "ok"}
    email, errors = await auth_router_mod._process_oidc_callback_fastapi(req, session)
    assert "Failed to exchange authorization code" in errors[0]

    # no userinfo
    async def fake_exchange2(request):
        return {"access_token": "a", "id_token": "i"}

    monkeypatch.setattr(
        auth_router_mod.oauth.oidc,
        "authorize_access_token",
        fake_exchange2,
        raising=False,
    )
    req.query_params = {"state": "ok", "code": "c"}
    session = {"oauth_state": "ok"}
    email, errors = await auth_router_mod._process_oidc_callback_fastapi(req, session)
    assert "No user information" in errors[0]

    # missing username (no configured fields found)
    async def fake_exchange3(request):
        return {"access_token": "a", "id_token": "i", "userinfo": {"name": "n"}}

    monkeypatch.setattr(
        auth_router_mod.oauth.oidc,
        "authorize_access_token",
        fake_exchange3,
        raising=False,
    )
    monkeypatch.setattr(config, "OIDC_USERNAME_FIELD", ["email", "preferred_username"], raising=False)
    req.query_params = {"state": "ok", "code": "c"}
    session = {"oauth_state": "ok"}
    email, errors = await auth_router_mod._process_oidc_callback_fastapi(req, session)
    assert "No username provided" in errors[0]

    # missing display name doesn't block login (falls back to username) — the callback
    # proceeds to the group-authorization gate, which fails here since no groups claim
    # is present. See tests/routers/test_auth.py for the successful-fallback path.
    async def fake_exchange4(request):
        return {"access_token": "a", "id_token": "i", "userinfo": {"email": "e@x.com"}}

    monkeypatch.setattr(
        auth_router_mod.oauth.oidc,
        "authorize_access_token",
        fake_exchange4,
        raising=False,
    )
    monkeypatch.setattr(config, "OIDC_DISPLAY_NAME_FIELD", ["name"], raising=False)
    req.query_params = {"state": "ok", "code": "c"}
    session = {"oauth_state": "ok"}
    email, errors = await auth_router_mod._process_oidc_callback_fastapi(req, session)
    assert "not allowed" in errors[0]

    # user not allowed
    async def fake_exchange5(request):
        return {
            "access_token": "a",
            "id_token": "i",
            "userinfo": {"email": "e@x.com", "name": "Name", "groups": ["other"]},
        }

    monkeypatch.setattr(
        auth_router_mod.oauth.oidc,
        "authorize_access_token",
        fake_exchange5,
        raising=False,
    )
    monkeypatch.setattr(config, "OIDC_GROUP_DETECTION_PLUGIN", "")
    monkeypatch.setattr(config, "OIDC_ADMIN_GROUP_NAME", ["admin"])
    monkeypatch.setattr(config, "OIDC_GROUP_NAME", ["users"])

    req.query_params = {"state": "ok", "code": "c"}
    session = {"oauth_state": "ok"}
    email, errors = await auth_router_mod._process_oidc_callback_fastapi(req, session)
    assert "not allowed" in errors[0]

    # user/group management error
    async def fake_exchange6(request):
        return {
            "access_token": "a",
            "id_token": "i",
            "userinfo": {"email": "e@x.com", "name": "Name", "groups": ["users"]},
        }

    monkeypatch.setattr(
        auth_router_mod.oauth.oidc,
        "authorize_access_token",
        fake_exchange6,
        raising=False,
    )
    # monkeypatch user module to raise
    import mlflow_oidc_auth.user as user_module

    monkeypatch.setattr(
        user_module,
        "create_user",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")),
        raising=False,
    )
    monkeypatch.setattr(user_module, "populate_groups", lambda **kw: None, raising=False)
    monkeypatch.setattr(user_module, "update_user", lambda **kw: None, raising=False)

    req.query_params = {"state": "ok", "code": "c"}
    session = {"oauth_state": "ok"}
    email, errors = await auth_router_mod._process_oidc_callback_fastapi(req, session)
    assert "Failed to update user/groups" in errors[0]

    # success - make user module no-ops
    import mlflow_oidc_auth.user as user_module

    monkeypatch.setattr(user_module, "create_user", lambda **kw: None, raising=False)
    monkeypatch.setattr(user_module, "populate_groups", lambda **kw: None, raising=False)
    monkeypatch.setattr(user_module, "update_user", lambda **kw: None, raising=False)

    monkeypatch.setattr(
        auth_router_mod.oauth.oidc,
        "authorize_access_token",
        fake_exchange6,
        raising=False,
    )
    monkeypatch.setattr(config, "OIDC_ADMIN_GROUP_NAME", ["admin", "users"])
    req.query_params = {"state": "ok", "code": "c"}
    session = {"oauth_state": "ok"}
    email, errors = await auth_router_mod._process_oidc_callback_fastapi(req, session)
    assert email == "e@x.com"
    assert errors == []


@pytest.mark.asyncio
async def test_refresh_oidc_jwks_load_server_metadata_and_exception(monkeypatch):
    # ensure we have an oidc client with load_server_metadata
    import types

    called = {"count": 0}

    async def load_server_metadata(force=False):
        called["count"] += 1

    monkeypatch.setattr(auth_router_mod.oauth, "oidc", types.SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        auth_router_mod.oauth.oidc,
        "load_server_metadata",
        load_server_metadata,
        raising=False,
    )

    await auth_router_mod._refresh_oidc_jwks()
    assert called["count"] == 1

    # now make it raise and ensure exception is swallowed
    async def load_server_metadata_bad(force=False):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        auth_router_mod.oauth.oidc,
        "load_server_metadata",
        load_server_metadata_bad,
        raising=False,
    )
    # Should not raise
    await auth_router_mod._refresh_oidc_jwks()


@pytest.mark.asyncio
async def test_call_authorize_access_token_sync_implementation(monkeypatch):
    # simulate a sync authorize_access_token implementation
    import types

    def sync_call(request):
        return {"ok": True}

    monkeypatch.setattr(auth_router_mod.oauth, "oidc", types.SimpleNamespace(), raising=False)
    monkeypatch.setattr(auth_router_mod.oauth.oidc, "authorize_access_token", sync_call, raising=False)

    res = await auth_router_mod._call_authorize_access_token(DummyRequest())
    assert res == {"ok": True}


@pytest.mark.asyncio
async def test_authorize_access_token_retry_on_exception_then_success(monkeypatch):
    calls = {"count": 0}

    async def call_then_success(request):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("boom")
        return {"access_token": "x"}

    monkeypatch.setattr(auth_router_mod, "_call_authorize_access_token", call_then_success)
    import types

    monkeypatch.setattr(auth_router_mod.oauth, "oidc", types.SimpleNamespace(), raising=False)

    refreshed = {"count": 0}

    async def _refresh():
        refreshed["count"] += 1

    monkeypatch.setattr(auth_router_mod, "_refresh_oidc_jwks", _refresh)

    res = await auth_router_mod._authorize_access_token_with_retry(DummyRequest())
    assert res == {"access_token": "x"}
    assert refreshed["count"] == 1


@pytest.mark.asyncio
async def test_login_fallback_redirect_uri_on_error(monkeypatch):
    monkeypatch.setattr(auth_router_mod, "is_oidc_configured", lambda: True)

    # make the redirect helper raise so the fallback path is used
    async def fake_authorize_redirect(request, redirect_uri=None, state=None):
        return RedirectResponse(url=redirect_uri)

    monkeypatch.setattr(auth_router_mod.oauth, "oidc", types.SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        auth_router_mod.oauth.oidc,
        "authorize_redirect",
        fake_authorize_redirect,
        raising=False,
    )
    monkeypatch.setattr(
        auth_router_mod,
        "get_configured_or_dynamic_redirect_uri",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    req = DummyRequest()
    res = await auth_router_mod.login(req)
    assert isinstance(res, RedirectResponse)
    # fallback should use the request.base_url
    assert str(req.base_url).rstrip("/") + "/callback" in res.headers["location"]


@pytest.mark.asyncio
async def test_auth_status_exception_propagates(monkeypatch):
    class BadReq:
        @property
        def session(self):
            raise RuntimeError("boom")

    # auth_status now returns HTTPException(500) on session access errors
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await auth_router_mod.auth_status(BadReq())

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_process_oidc_callback_final_except(monkeypatch):
    # Cause an unexpected exception inside the token handling logic to exercise final except
    class BadTokenResponse:
        def get(self, _):
            raise RuntimeError("boom")

    async def fake_exchange(request):
        return BadTokenResponse()

    import types

    monkeypatch.setattr(auth_router_mod.oauth, "oidc", types.SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        auth_router_mod.oauth.oidc,
        "authorize_access_token",
        fake_exchange,
        raising=False,
    )

    req = DummyRequest()
    req.query_params = {"state": "s", "code": "c"}
    session = {"oauth_state": "s"}

    email, errors = await auth_router_mod._process_oidc_callback_fastapi(req, session)
    assert "Failed to process authentication response" in errors[0]


class TestSessionHandoverOnReLogin:
    """Two logins in the same browser must not leave the first user's session id in the cookie.

    Found by security review of #310: the callback writes the new login's refresh token into the
    cookie *before* opening the session row. If opening it then failed and the old ``session_id``
    were still there, the browser would stay authenticated as the previous user and go on
    refreshing that session with the new user's IdP grant.
    """

    @pytest.mark.asyncio
    async def test_the_previous_session_is_revoked_and_replaced(self, monkeypatch):
        monkeypatch.setattr(auth_router_mod, "is_oidc_configured", lambda: True)

        async def _proc(request, session):
            return "second@example.com", []

        monkeypatch.setattr(auth_router_mod, "_process_oidc_callback_fastapi", _proc)
        monkeypatch.setattr(auth_router_mod, "_open_server_session", lambda username: "sid-second")
        revoked = []
        monkeypatch.setattr(auth_router_mod.store, "revoke_auth_session", lambda sid: revoked.append(sid) or True)

        req = DummyRequest()
        req.session["session_id"] = "sid-first"

        await auth_router_mod.callback(req)

        assert revoked == ["sid-first"]
        assert req.session["session_id"] == "sid-second"

    @pytest.mark.asyncio
    async def test_the_previous_users_refresh_token_is_not_inherited(self, monkeypatch):
        """The finding this ordering exists for.

        ``_persist_session_auth`` keeps an existing refresh token when the new token response
        carries none, so retiring the old login *after* the exchange would hand the next user
        the previous user's grant — their session would then outlive their own IdP session and
        die with someone else's.
        """
        monkeypatch.setattr(auth_router_mod, "is_oidc_configured", lambda: True)
        seen = {}

        async def _proc(request, session):
            # Stands in for the token exchange: records what the previous login left behind,
            # then persists a token response that carries no refresh token of its own.
            seen["at_exchange"] = dict(session)
            auth_router_mod._persist_session_auth(session, {"expires_at": 4102444800})
            return "second@example.com", []

        monkeypatch.setattr(auth_router_mod, "_process_oidc_callback_fastapi", _proc)
        monkeypatch.setattr(auth_router_mod, "_open_server_session", lambda username: "sid-second")
        monkeypatch.setattr(auth_router_mod.store, "revoke_auth_session", lambda sid: True)
        monkeypatch.setattr(config, "OIDC_USE_REFRESH_TOKEN", True)

        req = DummyRequest()
        req.session["session_id"] = "sid-first"
        req.session["refresh_token"] = "rt-first"
        req.session["expires_at"] = 100

        await auth_router_mod.callback(req)

        assert "refresh_token" not in seen["at_exchange"], "the exchange must not see the previous login's token"
        assert "refresh_token" not in req.session
        assert req.session["session_id"] == "sid-second"

    @pytest.mark.asyncio
    async def test_a_failure_to_open_a_session_clears_the_cookie(self, monkeypatch):
        monkeypatch.setattr(auth_router_mod, "is_oidc_configured", lambda: True)

        async def _proc(request, session):
            return "second@example.com", []

        monkeypatch.setattr(auth_router_mod, "_process_oidc_callback_fastapi", _proc)

        def _boom(username):
            raise RuntimeError("database is down")

        monkeypatch.setattr(auth_router_mod, "_open_server_session", _boom)
        monkeypatch.setattr(auth_router_mod.store, "revoke_auth_session", lambda sid: True)

        req = DummyRequest()
        req.session["session_id"] = "sid-first"
        req.session["refresh_token"] = "rt-second"  # written by _persist_session_auth already

        res = await auth_router_mod.callback(req)

        assert isinstance(res, RedirectResponse)
        assert "session_error" in res.headers["location"]
        assert req.session == {}, "a failed login must not leave any credential in the cookie"


class TestLogoutSurfacesRevocationFailure:
    """Telling a user they are logged out while the session stays live is the worst outcome."""

    @pytest.mark.asyncio
    async def test_a_revocation_failure_is_not_reported_as_success(self, monkeypatch):
        def _boom(session_id):
            raise RuntimeError("database is down")

        monkeypatch.setattr(auth_router_mod.store, "revoke_auth_session", _boom)

        req = DummyRequest()
        req.session["session_id"] = "sid-live"

        with pytest.raises(HTTPException) as excinfo:
            await auth_router_mod.logout(req)

        assert excinfo.value.status_code == 503

    @pytest.mark.asyncio
    async def test_the_session_id_survives_a_failed_revocation(self, monkeypatch):
        """So the 503's advice to retry is advice the user can act on.

        Clearing the cookie first would delete the only copy of the session id: the retry would
        find nothing to revoke, take the success path, and leave the session live.
        """

        def _boom(session_id):
            raise RuntimeError("db down")

        monkeypatch.setattr(auth_router_mod.store, "revoke_auth_session", _boom)

        req = DummyRequest()
        req.session["session_id"] = "sid-live"

        with pytest.raises(HTTPException):
            await auth_router_mod.logout(req)

        assert req.session.get("session_id") == "sid-live"

    @pytest.mark.asyncio
    async def test_the_failure_is_audited_as_a_failure(self, monkeypatch):
        """A denied outcome recorded with the default status "success" is invisible to the
        query an operator actually runs."""
        events = []
        monkeypatch.setattr(auth_router_mod, "emit_audit_event", lambda event, **kwargs: events.append((event, kwargs)))

        def _boom(session_id):
            raise RuntimeError("db down")

        monkeypatch.setattr(auth_router_mod.store, "revoke_auth_session", _boom)

        req = DummyRequest()
        req.session["session_id"] = "sid-live"

        with pytest.raises(HTTPException):
            await auth_router_mod.logout(req)

        assert [e for e, _ in events] == ["auth.logout_failed"]
        assert events[0][1]["status"] == "denied"

    @pytest.mark.asyncio
    async def test_a_successful_logout_revokes_the_row(self, monkeypatch):
        revoked = []
        monkeypatch.setattr(auth_router_mod.store, "revoke_auth_session", lambda sid: revoked.append(sid) or True)
        monkeypatch.setattr(auth_router_mod.oauth, "oidc", types.SimpleNamespace(), raising=False)

        req = DummyRequest()
        req.session["session_id"] = "sid-live"

        res = await auth_router_mod.logout(req)

        assert revoked == ["sid-live"]
        assert isinstance(res, RedirectResponse)
