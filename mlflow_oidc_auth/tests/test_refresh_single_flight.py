"""Concurrent silent refresh exchanges the refresh token exactly once (issue #367).

The defect: a page load fires several API calls at once. When the session's IdP expiry had
passed, every one of them refreshed — each exchanging the *same* refresh token. Under refresh
token rotation with reuse detection (Keycloak, Okta, Auth0, Entra with rotation on), the IdP
answers the second exchange by revoking the whole token family, and the user is logged out
mid-page. The refresh token also rode in the cookie, so even a lucky winner could be undone by a
loser's response overwriting it.

These tests run the real ``AuthMiddleware`` against a real SQLite store, with a fake IdP that
implements rotation *and* reuse detection, so a second exchange is not merely counted — it is
fatal, as it is in production.
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth.middleware import AuthMiddleware
from mlflow_oidc_auth.session.token_vault import SessionTokens, get_token_vault

PASSWORD = "single-flight-password"  # not a credential: only ever seeded into a tmp_path database
USERNAME = "single-flight@example.com"
PROTECTED = "/sf/protected"
LOGIN = "/login/sf"
ISSUED = "rt-issued"  # test-only token strings
ROTATED = "rt-rotated"
CONCURRENCY = 8


class RotatingIdP:
    """A token endpoint with rotation and reuse detection.

    Exchanging the current refresh token returns a new one and retires the old. Presenting a
    retired token revokes the family — every later exchange fails — exactly as a real IdP with
    reuse detection does.
    """

    def __init__(self, delay: float = 0.2, fail: bool = False):
        self.delay = delay
        self.fail = fail
        self.valid = ISSUED
        self.family_revoked = False
        self.calls = 0
        self._lock = threading.Lock()

    async def fetch_access_token(self, grant_type, refresh_token):
        with self._lock:
            self.calls += 1
        # Long enough that every concurrent request reaches the refresh while this one is in flight.
        await asyncio.sleep(self.delay)
        with self._lock:
            if self.fail or self.family_revoked:
                raise RuntimeError("invalid_grant")
            if refresh_token != self.valid:
                self.family_revoked = True
                raise RuntimeError("invalid_grant: refresh token reuse detected")
            self.valid = ROTATED
        return {"access_token": "at", "expires_at": int(time.time()) + 3600, "refresh_token": ROTATED}


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
    s.create_user(USERNAME, PASSWORD, "Single Flight")
    yield s
    s.engine.dispose()


@pytest.fixture
def idp():
    return RotatingIdP()


@pytest.fixture
def app(store, idp, monkeypatch):
    from mlflow_oidc_auth.routers import auth as auth_module

    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", store)
    _patch_live_configs(monkeypatch, OIDC_USE_REFRESH_TOKEN=True, OIDC_SESSION_EXPIRY_LEEWAY_SECONDS=0)
    monkeypatch.setattr(auth_module, "oauth", type("FakeOAuth", (), {"oidc": idp})())

    application = FastAPI()

    @application.get(PROTECTED)
    async def protected(request: Request):
        return {"username": getattr(request.state, "username", None)}

    @application.get(LOGIN)
    async def login(request: Request):
        # A session whose IdP expiry has already passed, holding a refresh token — the state a
        # tab is in when it wakes up and fires its burst of API calls.
        tokens = SessionTokens(provider_id="default", expires_at=100, refresh_token=ISSUED)
        request.session["session_id"] = store_module.store.create_auth_session(
            USERNAME,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
            provider_id="default",
            encrypted_tokens=get_token_vault().encrypt(tokens),
        )
        return {"ok": True}

    application.add_middleware(AuthMiddleware)
    application.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential")
    try:
        yield application
    finally:
        object.__setattr__(store_module.store, "_instance", previous)


def _stored_tokens(store) -> SessionTokens:
    sid = store.auth_session_repo.list_live_for_user(USERNAME)[0]
    return get_token_vault().decrypt(store.resolve_auth_session(sid).encrypted_tokens)


async def _burst(app, n: int):
    """Log in, then fire ``n`` concurrent requests on one event loop with the same cookie."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        assert (await client.get(LOGIN)).status_code == 200
        responses = await asyncio.gather(*(client.get(PROTECTED) for _ in range(n)))
        return responses, client


class TestSingleFlightOnOneEventLoop:
    def test_n_concurrent_requests_exchange_once_and_all_succeed(self, app, idp, store):
        responses, _ = asyncio.run(_burst(app, CONCURRENCY))

        assert [r.status_code for r in responses] == [200] * CONCURRENCY
        assert idp.calls == 1, f"the refresh token was exchanged {idp.calls} times"
        assert idp.family_revoked is False
        assert _stored_tokens(store).refresh_token == ROTATED

    def test_no_response_writes_token_material_to_the_cookie(self, app, idp):
        responses, _ = asyncio.run(_burst(app, CONCURRENCY))

        for response in responses:
            set_cookie = response.headers.get("set-cookie", "")
            assert ROTATED not in set_cookie and ISSUED not in set_cookie

    def test_a_later_request_adopts_the_result(self, app, idp, store):
        async def scenario():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                await client.get(LOGIN)
                await asyncio.gather(*(client.get(PROTECTED) for _ in range(CONCURRENCY)))
                return await client.get(PROTECTED)

        assert asyncio.run(scenario()).status_code == 200
        assert idp.calls == 1

    def test_definitive_failure_ends_the_session_for_every_request(self, app, idp, store):
        idp.fail = True

        responses, _ = asyncio.run(_burst(app, CONCURRENCY))

        assert [r.status_code for r in responses] == [401] * CONCURRENCY
        # The losers re-read and retried once each at most: none may succeed on a failed IdP.
        assert idp.calls >= 1
        assert _stored_tokens(store).refresh_token == ISSUED, "nothing is written on failure"


class TestWaitersHoldNoThreads:
    """Waiters queue on the event loop; only the refresher uses a worker thread (security review).

    Blocking waiters in executor threads could fill the default executor that the refresher
    itself needs, so the one request able to release them would stall behind them.
    """

    def test_slow_idp_many_waiters_one_thread_one_exchange(self, app, idp, store, monkeypatch):
        from mlflow_oidc_auth.routers import auth as auth_module
        from mlflow_oidc_auth.session.refresh_lock import pending_turns

        idp.delay = 0.5
        in_flight = {"now": 0, "max": 0, "calls": 0}
        real = auth_module._run_blocking

        async def counting(fn, *args, **kwargs):
            in_flight["calls"] += 1
            in_flight["now"] += 1
            in_flight["max"] = max(in_flight["max"], in_flight["now"])
            try:
                return await real(fn, *args, **kwargs)
            finally:
                in_flight["now"] -= 1

        monkeypatch.setattr(auth_module, "_run_blocking", counting)

        responses, _ = asyncio.run(_burst(app, CONCURRENCY * 2))

        assert [r.status_code for r in responses] == [200] * (CONCURRENCY * 2)
        assert idp.calls == 1
        assert in_flight["calls"] == 1, "only the refresher may take a worker thread"
        assert in_flight["max"] == 1
        assert _stored_tokens(store).refresh_token == ROTATED
        assert pending_turns() == 0, "the per-session locks are released and dropped"

    def test_waiters_time_out_rather_than_hang(self, app, idp, store, monkeypatch):
        """A refresher stuck past the cap does not pin its waiters; they re-read and give up."""
        from mlflow_oidc_auth.routers import auth as auth_module

        idp.delay = 1.0
        monkeypatch.setattr(auth_module, "REFRESH_GUARD_TIMEOUT_SECONDS", 0.2)

        started = time.monotonic()
        responses, _ = asyncio.run(_burst(app, 4))
        elapsed = time.monotonic() - started

        statuses = sorted(r.status_code for r in responses)
        # The refresher still succeeds; the waiters stopped waiting after the cap.
        assert statuses.count(200) >= 1
        assert statuses.count(401) >= 1
        assert idp.calls == 1
        assert elapsed < 5


class TestSingleFlightAcrossThreads:
    """Worker threads with their own event loops — the shape of a threaded ASGI server."""

    def test_n_threads_exchange_once_and_all_succeed(self, app, idp, store):
        with TestClient(app) as client:
            assert client.get(LOGIN).status_code == 200
            cookie = client.cookies.get("session")

        barrier = threading.Barrier(CONCURRENCY)

        def one_request(_):
            # Separate clients, so each runs its own event loop, sharing only the cookie.
            with TestClient(app, cookies={"session": cookie}) as c:
                barrier.wait(5)
                return c.get(PROTECTED).status_code

        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            statuses = list(pool.map(one_request, range(CONCURRENCY)))

        assert statuses == [200] * CONCURRENCY
        assert idp.calls == 1, f"the refresh token was exchanged {idp.calls} times"
        assert idp.family_revoked is False
        assert _stored_tokens(store).refresh_token == ROTATED


class TestWithoutTheGuardTheDefectReproduces:
    """Proves the fake IdP would catch a regression: bypass both locks and the family is revoked."""

    def test_unguarded_concurrent_refresh_replays_the_token(self, app, idp, store, monkeypatch):
        from contextlib import asynccontextmanager, contextmanager

        from mlflow_oidc_auth.repository.auth_session import RefreshGuard

        real_store = object.__getattribute__(store_module.store, "_instance")

        def no_guard(session_id):
            @contextmanager
            def _cm():
                yield RefreshGuard(
                    real_store.auth_session_repo._read_tokens(session_id)[1],
                    True,
                    reread=lambda: real_store.auth_session_repo._read_tokens(session_id)[1],
                    write=lambda blob: real_store.store_auth_session_tokens(session_id, blob),
                )

            return _cm()

        @asynccontextmanager
        async def no_turn(session_id, timeout):
            yield

        from mlflow_oidc_auth.routers import auth as auth_module

        monkeypatch.setattr(real_store, "auth_session_refresh_guard", no_guard)
        monkeypatch.setattr(auth_module, "local_refresh_turn", no_turn)

        asyncio.run(_burst(app, CONCURRENCY))

        # The losers' post-failure re-read may even let this burst through, but the IdP has
        # revoked the token family: the rotated token stored on the row is already dead, and the
        # next refresh logs the user out. That is the #367 failure.
        assert idp.calls > 1
        assert idp.family_revoked is True
