"""The per-request auth-path query budget (issue #305).

``AuthMiddleware.dispatch`` runs on every request that is not on an unprotected prefix.
Whatever it costs is paid by every API call and every UI navigation, so it is the one
number the enterprise-identity work (epic #304) is budgeted against.

These tests pin that budget. They are exact assertions, so a regression *and* a silent
improvement both fail and have to be acknowledged in a diff — same discipline as
``test_query_counts.py`` (issue #253).

The budget, measured by ``scripts/bench_auth_path.py`` and recorded in
``docs/performance-baseline.md``:

===============  ===================
scenario         SQL statements
===============  ===================
unprotected      0
session          1
bearer           2
basic            3
===============  ===================

The session path was 2 until #310 moved sessions server-side: resolving the cookie's opaque id
joins ``auth_sessions`` to ``users`` and returns the session's validity together with the admin
and active flags, so the request that used to cost a lookup *and* a profile read now costs one
statement. Lower is allowed; it simply has to be acknowledged here rather than drift.

**No task may raise these numbers.** A change that needs more per-request data must fit
it into the existing statements (widen the ``load_only``) or cache it — not add a query.

See ``conftest.py`` for why round-trips, not query cost, are the metric.
"""

import base64
import time
from datetime import datetime, timedelta, timezone
from typing import List

import pytest
from authlib.jose import JsonWebKey, jwt
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

import mlflow_oidc_auth.auth as auth_module
import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth.middleware import AuthMiddleware

from .conftest import QueryCounter

BENCH_PASSWORD = "bench-password"  # not a credential: only ever seeded into a tmp_path database
PROTECTED_PATH = "/bench/protected"
UNPROTECTED_PATH = "/health/bench"
LOGIN_PATH = "/login/bench"


@pytest.fixture
def auth_user(store):
    """A user with a real password hash and a handful of groups."""
    username = "baseline@example.com"
    store.create_user(username, BENCH_PASSWORD, "Baseline User")
    groups = [f"baseline-group-{i}" for i in range(4)]
    store.populate_groups(groups)
    store.set_user_groups(username, groups)
    return username


@pytest.fixture
def bound_store(store, monkeypatch):
    """Point the lazy ``store`` singleton at the test store for the duration of a test.

    ``AuthMiddleware`` imports the singleton directly, so it cannot be injected. This
    installs the store the fixture already built rather than constructing a second one,
    and ``monkeypatch`` restores the previous instance afterwards.
    """
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", store)
    yield store
    object.__setattr__(store_module.store, "_instance", previous)


@pytest.fixture
def bearer_token(monkeypatch):
    """Prime the JWKS cache with a local key and return a minted RS256 token.

    Signature verification is real; only the JWKS network fetch is bypassed — which is
    what a warm production process does too, since JWKS is cached for
    ``OIDC_JWKS_CACHE_TTL_SECONDS``.
    """
    key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    private = key.as_dict(is_private=True)
    public = key.as_dict(is_private=False)
    kid = public.get("kid") or key.thumbprint()
    public["kid"] = kid
    private["kid"] = kid

    monkeypatch.setattr(auth_module.config, "OIDC_DISCOVERY_URL", "https://test.invalid/.well-known/openid-configuration")
    monkeypatch.setitem(auth_module._jwks_cache, auth_module._JWKS_CACHE_KEY, {"keys": [public]})

    def mint(username: str) -> str:
        now = int(time.time())
        claims = {"email": username, "name": username, "iat": now, "exp": now + 3600}
        return jwt.encode({"alg": "RS256", "kid": kid}, claims, private).decode("utf-8")

    return mint


@pytest.fixture
def client(bound_store):
    """A TestClient over a minimal app wrapping the real ``AuthMiddleware``.

    Middleware is added in the same order as ``app.py`` — Auth, then Session — which in
    Starlette makes Session the outer one, so ``request.session`` exists by the time
    ``AuthMiddleware`` looks for it. MLflow's Flask app is not mounted: this measures the
    auth path, not MLflow.
    """
    app = FastAPI()

    @app.get(PROTECTED_PATH)
    async def protected(request: Request):
        return {"username": getattr(request.state, "username", None)}

    @app.get(UNPROTECTED_PATH)
    async def unprotected():
        return {"ok": True}

    @app.get(LOGIN_PATH)
    async def login(request: Request, username: str):
        # "/login" is an unprotected prefix, so this runs without authentication and
        # mints the same session the OIDC callback would.
        # Mirrors the OIDC callback since #310: the cookie carries only an opaque session id.
        request.session["session_id"] = store_module.store.create_auth_session(username, expires_at=datetime.now(timezone.utc) + timedelta(hours=8))
        return {"ok": True}

    app.add_middleware(AuthMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential")

    with TestClient(app) as c:
        yield c


def _count_requests(counter: QueryCounter, make_request, n: int = 3) -> List[int]:
    """Issue ``n`` identical requests and return the statement count of each.

    Repeating catches a first-request-only cost (a lazily built cache, a connection
    warm-up) that a single measurement would bake into the budget.
    """
    counts = []
    for _ in range(n):
        counter.reset()
        response = make_request()
        assert response.status_code == 200, response.text
        counts.append(counter.count)
    return counts


class TestAuthPathQueryBudget:
    """The per-request statement budget. These numbers are the contract."""

    def test_unprotected_path_issues_no_queries(self, client, counter, auth_user):
        """An unprotected prefix must short-circuit before any store access."""
        counts = _count_requests(counter, lambda: client.get(UNPROTECTED_PATH))

        assert counts == [0, 0, 0], counter.report()

    def test_session_authenticated_request_issues_one_query(self, client, counter, auth_user):
        """The browser path costs a single statement since #310.

        Resolving the opaque session id joins ``auth_sessions`` to ``users``, so the session's
        validity and the user's admin and active flags all come back together. The two-statement
        profile read this used to perform — the ``load_only`` select plus a ``selectinload`` for
        groups the auth path never used — is gone from this path.
        """
        client.get(LOGIN_PATH, params={"username": auth_user})

        counts = _count_requests(counter, lambda: client.get(PROTECTED_PATH))

        assert counts == [1, 1, 1], counter.report()

    def test_bearer_authenticated_request_issues_two_queries(self, client, counter, auth_user, bearer_token):
        """The API path: with provisioning off (the default), only the admin check runs."""
        token = bearer_token(auth_user)

        counts = _count_requests(counter, lambda: client.get(PROTECTED_PATH, headers={"Authorization": f"Bearer {token}"}))

        assert counts == [2, 2, 2], counter.report()

    def test_bearer_with_provisioning_enabled_costs_one_extra_query(self, client, counter, auth_user, bearer_token, monkeypatch):
        """``OIDC_PROVISION_ON_BEARER_AUTH`` adds a ``has_user`` check to *every* bearer
        request, not only the first — the guard runs before it can decide to do nothing.

        Recorded so the opt-in's cost is a known number rather than a surprise. The flag is
        off by default, which is why the budget above is 2.
        """
        from mlflow_oidc_auth.middleware import auth_middleware as middleware_module

        monkeypatch.setattr(middleware_module.config, "OIDC_PROVISION_ON_BEARER_AUTH", True)
        token = bearer_token(auth_user)

        counts = _count_requests(counter, lambda: client.get(PROTECTED_PATH, headers={"Authorization": f"Bearer {token}"}))

        assert counts == [3, 3, 3], counter.report()

    def test_basic_authenticated_request_issues_three_queries(self, client, counter, auth_user):
        """Basic auth pays one extra statement to load the password hash before the admin check."""
        credentials = base64.b64encode(f"{auth_user}:{BENCH_PASSWORD}".encode()).decode()

        counts = _count_requests(counter, lambda: client.get(PROTECTED_PATH, headers={"Authorization": f"Basic {credentials}"}))

        assert counts == [3, 3, 3], counter.report()


class TestAuthPathDenialCosts:
    """The denial paths. An unauthenticated caller must not be cheaper to serve than a
    real one in a way that leaks, nor more expensive in a way that invites a DoS."""

    def test_unauthenticated_request_is_denied_without_touching_the_store(self, client, counter, auth_user):
        """No credentials means no user to look up: 401 with zero statements.

        This is the negative case for the budget — an anonymous flood must not be able to
        drive database load through the auth path.
        """
        counter.reset()

        response = client.get(PROTECTED_PATH)

        assert response.status_code == 401
        assert counter.count == 0, counter.report()

    def test_invalid_bearer_token_is_denied_without_touching_the_store(self, client, counter, auth_user):
        """A forged/garbage token is rejected at signature validation, before any query."""
        counter.reset()

        response = client.get(PROTECTED_PATH, headers={"Authorization": "Bearer not-a-real-token"})

        assert response.status_code == 401
        assert counter.count == 0, counter.report()

    def test_wrong_basic_password_is_denied_after_one_query(self, client, counter, auth_user):
        """Basic auth must load the hash to compare it, but must not go on to the admin check."""
        credentials = base64.b64encode(f"{auth_user}:wrong-password".encode()).decode()
        counter.reset()

        response = client.get(PROTECTED_PATH, headers={"Authorization": f"Basic {credentials}"})

        assert response.status_code == 401
        assert counter.count == 1, counter.report()

    def test_unknown_user_basic_auth_is_denied_after_one_query(self, client, counter, auth_user):
        """A username that does not exist costs exactly the one lookup that proves it."""
        credentials = base64.b64encode(b"ghost@example.com:whatever").decode()
        counter.reset()

        response = client.get(PROTECTED_PATH, headers={"Authorization": f"Basic {credentials}"})

        assert response.status_code == 401
        assert counter.count == 1, counter.report()


class TestAdminStatusLookup:
    """``_get_user_admin_status`` itself — the specific claim issue #305 asked us to check."""

    def test_admin_check_is_two_statements(self, store, counter, auth_user):
        """Confirmed: one select on ``users``, one selectinload on ``groups``."""
        counter.reset()

        store.get_user_profile(auth_user)

        assert counter.count == 2, counter.report()
        assert counter.for_table("users") >= 1, counter.report()
        assert counter.for_table("groups") >= 1, counter.report()

    @pytest.mark.parametrize("n_groups", [0, 1, 20])
    def test_admin_check_is_constant_in_group_count(self, store, counter, n_groups):
        """The 2 statements must not become 2 + G. ``selectinload`` batches; a lazy load
        would not, and that is the regression this guards."""
        username = f"g{n_groups}@example.com"
        store.create_user(username, BENCH_PASSWORD, username)
        if n_groups:
            groups = [f"cg{n_groups}-{i}" for i in range(n_groups)]
            store.populate_groups(groups)
            store.set_user_groups(username, groups)
        counter.reset()

        profile = store.get_user_profile(username)

        assert len(profile.groups) == n_groups
        assert counter.count == 2, counter.report()

    def test_admin_check_is_uncached(self, store, counter, auth_user):
        """Two identical calls cost two full lookups.

        This is the *problem statement*, asserted: despite ``PERMISSION_CACHE_TTL_SECONDS``
        and a pluggable cache backend existing, nothing caches the profile. If a later
        change adds that cache, this test must fail and be replaced with one asserting
        the cached count — deliberately, in a diff.
        """
        counter.reset()

        store.get_user_profile(auth_user)
        store.get_user_profile(auth_user)

        assert counter.count == 4, counter.report()
