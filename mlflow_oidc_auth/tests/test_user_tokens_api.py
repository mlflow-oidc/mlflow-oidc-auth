"""The access token API end to end (issue #189): real ``AuthMiddleware``, real store, real router.

The authorization rules these pin:

* only a signed-in session (or an IdP bearer token) may issue a token — a request authenticated
  with an access token may not, so a leaked token cannot mint replacements for itself;
* a user sees and deletes only their own tokens, and another user's token id reads as not found;
* the ``/users/{username}/tokens`` endpoints are admin-only;
* every issue, delete and revoke is audited, and no secret ever reaches the audit log.
"""

import base64
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth.middleware import AuthMiddleware
from mlflow_oidc_auth.routers.users import users_router
from mlflow_oidc_auth.tests.token_helpers import issue_token

ADMIN = "admin@example.com"
ALICE = "alice@example.com"
BOB = "bob@example.com"
SERVICE = "svc-pipeline"
LOGIN = "/login/tokens-api"
TOKENS = "/api/2.0/mlflow/users/current/tokens"
ACCESS_TOKEN = "/api/2.0/mlflow/users/access-token"


def _of(username: str) -> str:
    return f"/api/2.0/mlflow/users/{username}/tokens"


def _basic(username: str, token: str) -> dict:
    return {"Authorization": "Basic " + base64.b64encode(f"{username}:{token}".encode()).decode()}


def _expiry(days: int = 30) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(ADMIN, "Admin", is_admin=True)
    s.create_user(ALICE, "Alice")
    s.create_user(BOB, "Bob")
    s.create_user(SERVICE, "Pipeline", is_service_account=True)
    yield s
    s.engine.dispose()


@pytest.fixture
def audit():
    with patch("mlflow_oidc_auth.routers.users.emit_audit_event") as emitted:
        yield emitted


@pytest.fixture
def app(store):
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", store)

    application = FastAPI()

    @application.get(LOGIN)
    async def login(request: Request, username: str):
        # "/login" is an unprotected prefix. Mints the same cookie the OIDC callback does.
        request.session["session_id"] = store_module.store.create_auth_session(username, expires_at=datetime.now(timezone.utc) + timedelta(hours=8))
        return {"ok": True}

    application.include_router(users_router)
    application.add_middleware(AuthMiddleware)
    application.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential")
    try:
        yield application
    finally:
        object.__setattr__(store_module.store, "_instance", previous)


def _session(app, username: str) -> TestClient:
    client = TestClient(app)
    assert client.get(LOGIN, params={"username": username}).status_code == 200
    return client


@pytest.fixture
def alice(app):
    return _session(app, ALICE)


@pytest.fixture
def admin(app):
    return _session(app, ADMIN)


@pytest.fixture
def anonymous(app):
    return TestClient(app)


class TestSelfService:
    def test_create_list_use_delete(self, alice, anonymous, audit):
        created = alice.post(TOKENS, json={"name": "laptop", "expiration": _expiry()})
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["name"] == "laptop" and body["token"].startswith(f"mlf_{body['token_prefix']}_")
        assert created.headers["cache-control"] == "no-store"

        listed = alice.get(TOKENS).json()["tokens"]
        assert [t["name"] for t in listed] == ["laptop"]
        assert "token" not in listed[0] and not any("hash" in key for key in listed[0])

        assert anonymous.get(TOKENS, headers=_basic(ALICE, body["token"])).status_code == 200

        response = alice.delete(f"{TOKENS}/{body['id']}")
        assert response.status_code == 200
        assert anonymous.get(TOKENS, headers=_basic(ALICE, body["token"])).status_code == 401

        events = [c.args[0] for c in audit.call_args_list]
        assert events == ["user.token_create", "user.token_delete"]
        assert body["token"] not in repr(audit.call_args_list)

    def test_a_duplicate_name_is_409(self, alice):
        response = alice.post(TOKENS, json={"name": "ci", "expiration": _expiry()})
        assert response.status_code == 201

        response = alice.post(TOKENS, json={"name": "ci", "expiration": _expiry()})
        assert response.status_code == 409

    @pytest.mark.parametrize(
        "payload",
        [
            {"name": "ci", "expiration": _expiry(-1)},
            {"name": "ci", "expiration": _expiry(400)},
            {"name": "ci", "expiration": "tomorrow"},
            {"name": "", "expiration": _expiry()},
        ],
    )
    def test_bad_input_is_400(self, alice, payload):
        response = alice.post(TOKENS, json=payload)
        assert response.status_code == 400

    @pytest.mark.parametrize("payload", [{"name": "ci"}, {"expiration": _expiry()}])
    def test_name_and_expiration_are_both_required(self, alice, payload):
        response = alice.post(TOKENS, json=payload)
        assert response.status_code == 422

    def test_the_cap_is_409(self, alice, store):
        from mlflow_oidc_auth.repository.user_token import MAX_LIVE_TOKENS_PER_USER

        for i in range(MAX_LIVE_TOKENS_PER_USER):
            issue_token(store, ALICE, name=f"t{i}")

        response = alice.post(TOKENS, json={"name": "one-more", "expiration": _expiry()})
        assert response.status_code == 409

    def test_the_default_token_can_be_rotated_from_a_session(self, alice, anonymous, audit):
        first = alice.patch(ACCESS_TOKEN).json()["token"]
        second = alice.patch(ACCESS_TOKEN).json()["token"]

        assert anonymous.get(TOKENS, headers=_basic(ALICE, first)).status_code == 401
        assert anonymous.get(TOKENS, headers=_basic(ALICE, second)).status_code == 200
        assert [c.args[0] for c in audit.call_args_list] == ["user.token_rotate", "user.token_rotate"]


class TestATokenCannotMintAnother:
    """The rule the maintainer chose: issuing a token needs an interactive sign-in."""

    def test_a_token_cannot_create_a_token(self, anonymous, store):
        headers = _basic(ALICE, issue_token(store, ALICE, name="ci"))

        response = anonymous.post(TOKENS, headers=headers, json={"name": "hidden", "expiration": _expiry()})

        assert response.status_code == 403
        assert [t.name for t in store.list_user_tokens(ALICE)] == ["ci"]

    def test_a_token_cannot_rotate_the_default_token(self, anonymous, store):
        headers = _basic(ALICE, issue_token(store, ALICE, name="ci"))

        response = anonymous.patch(ACCESS_TOKEN, headers=headers)
        assert response.status_code == 403
        assert [t.name for t in store.list_user_tokens(ALICE)] == ["ci"]

    def test_an_admin_token_cannot_issue_one_for_someone_else(self, anonymous, store):
        headers = _basic(ADMIN, issue_token(store, ADMIN, name="ci"))

        response = anonymous.post(_of(SERVICE), headers=headers, json={"name": "x", "expiration": _expiry()})
        assert response.status_code == 403
        response = anonymous.patch(ACCESS_TOKEN, headers=headers, json={"username": SERVICE})
        assert response.status_code == 403
        assert store.list_user_tokens(SERVICE) == []

    def test_a_token_may_still_list_and_delete_its_owners_tokens(self, anonymous, store):
        """Reading and removing only reduce access; they stay available to automation."""
        leaked = issue_token(store, ALICE, name="leaked")
        headers = _basic(ALICE, issue_token(store, ALICE, name="ci"))
        leaked_id = next(t.id for t in store.list_user_tokens(ALICE) if t.name == "leaked")

        assert anonymous.get(TOKENS, headers=headers).status_code == 200
        response = anonymous.delete(f"{TOKENS}/{leaked_id}", headers=headers)
        assert response.status_code == 200
        assert store.authenticate_user(ALICE, leaked) is False

    def test_the_request_state_marker_is_deny_by_default(self):
        """A request whose authentication method is unknown is refused, not waved through."""
        import asyncio

        from fastapi import HTTPException

        from mlflow_oidc_auth.dependencies import require_interactive_login

        class _State:
            pass

        class _Request:
            state = _State()

        with pytest.raises(HTTPException) as exc:
            asyncio.run(require_interactive_login(_Request()))
        assert exc.value.status_code == 403


class TestIssuingRules:
    def test_a_deactivated_user_cannot_be_issued_a_token_by_an_admin(self, admin, store):
        store.update_user(BOB, active=False)

        response = admin.post(_of(BOB), json={"name": "ci", "expiration": _expiry()})
        assert response.status_code == 409
        response = admin.patch(ACCESS_TOKEN, json={"username": BOB})
        assert response.status_code == 409
        assert store.list_user_tokens(BOB) == []

    def test_issuing_clears_expired_tokens_and_frees_their_names(self, alice, store):
        from mlflow_oidc_auth.db.models import SqlUserToken

        first = alice.post(TOKENS, json={"name": "ci", "expiration": _expiry()}).json()
        table = SqlUserToken.__table__
        with store.engine.begin() as conn:
            conn.execute(
                table.update().where(table.c.id == first["id"]).values(expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1))
            )
        assert [t["active"] for t in alice.get(TOKENS).json()["tokens"]] == [False]

        again = alice.post(TOKENS, json={"name": "ci", "expiration": _expiry()})

        assert again.status_code == 201
        assert [t["id"] for t in alice.get(TOKENS).json()["tokens"]] == [again.json()["id"]]


class TestWorkloadBearerThroughTheMiddleware:
    """The wiring, not just the pieces: dispatch labels a workload bearer and issuance refuses it."""

    @pytest.fixture
    def bearer(self, app, store):
        from unittest.mock import MagicMock

        from mlflow_oidc_auth.middleware import auth_middleware as middleware_module

        def install(interactive: bool, provider_type: str):
            provider = MagicMock(type=provider_type, interactive=interactive)
            patches = [
                patch.object(middleware_module, "validate_token", return_value={"email": ALICE}),
                patch.object(middleware_module.AuthMiddleware, "_provider_for", return_value=provider),
                patch.object(middleware_module.AuthMiddleware, "_authenticate_service_account", return_value=(True, ALICE, "")),
                patch.object(middleware_module, "extract_username", return_value=(ALICE, None)),
            ]
            for p in patches:
                p.start()
            return patches

        started = []
        yield lambda interactive, provider_type="oidc": started.extend(install(interactive, provider_type))
        for p in started:
            p.stop()

    @pytest.mark.parametrize("provider_type", ["k8s", "oidc"])
    def test_a_workload_bearer_cannot_issue(self, anonymous, bearer, store, provider_type):
        bearer(interactive=False, provider_type=provider_type)
        headers = {"Authorization": "Bearer workload-token"}

        assert anonymous.get(TOKENS, headers=headers).status_code == 200, "precondition: it authenticates"
        response = anonymous.post(TOKENS, headers=headers, json={"name": "x", "expiration": _expiry()})
        assert response.status_code == 403
        response = anonymous.patch(ACCESS_TOKEN, headers=headers)
        assert response.status_code == 403
        assert store.list_user_tokens(ALICE) == []

    def test_an_interactive_idp_user_token_can_issue(self, anonymous, bearer, store):
        bearer(interactive=True)

        response = anonymous.post(TOKENS, headers={"Authorization": "Bearer user-token"}, json={"name": "x", "expiration": _expiry()})

        assert response.status_code == 201


class TestIsolationBetweenUsers:
    def test_a_user_lists_only_their_own_tokens(self, alice, store):
        issue_token(store, BOB, name="bobs")

        assert alice.get(TOKENS).json()["tokens"] == []

    def test_another_users_token_id_reads_as_not_found(self, alice, anonymous, store):
        bobs = issue_token(store, BOB, name="bobs")
        (record,) = store.list_user_tokens(BOB)

        response = alice.delete(f"{TOKENS}/{record.id}")
        assert response.status_code == 404
        assert anonymous.get(TOKENS, headers=_basic(BOB, bobs)).status_code == 200

    @pytest.mark.parametrize(
        "method, path, body",
        [
            ("get", _of(BOB), None),
            ("post", _of(BOB), {"name": "x", "expiration": _expiry()}),
            ("delete", f"{_of(BOB)}/1", None),
            ("delete", _of(BOB), None),
        ],
    )
    def test_the_per_user_endpoints_are_admin_only(self, alice, store, method, path, body):
        issue_token(store, BOB, name="bobs")
        kwargs = {"json": body} if body is not None else {}

        response = getattr(alice, method)(path, **kwargs)

        assert response.status_code == 403
        assert [t.name for t in store.list_user_tokens(BOB)] == ["bobs"]

    def test_a_non_admin_cannot_rotate_someone_elses_default_token(self, alice, store):
        response = alice.patch(ACCESS_TOKEN, json={"username": BOB})
        assert response.status_code == 403
        assert store.list_user_tokens(BOB) == []


class TestAdministration:
    def test_an_admin_issues_a_token_for_a_service_account(self, admin, anonymous, audit):
        response = admin.post(_of(SERVICE), json={"name": "ci", "expiration": _expiry()})

        assert response.status_code == 201
        token = response.json()["token"]
        assert anonymous.get(TOKENS, headers=_basic(SERVICE, token)).status_code == 200
        (call,) = audit.call_args_list
        assert call.args[0] == "user.token_create"
        assert call.kwargs["actor"] == ADMIN and call.kwargs["resource_id"] == SERVICE
        assert token not in repr(call)

    def test_an_admin_lists_and_deletes_a_users_token(self, admin, store, audit):
        issue_token(store, ALICE, name="ci")
        (record,) = store.list_user_tokens(ALICE)

        assert [t["name"] for t in admin.get(_of(ALICE)).json()["tokens"]] == ["ci"]
        response = admin.delete(f"{_of(ALICE)}/{record.id}")
        assert response.status_code == 200
        assert store.list_user_tokens(ALICE) == []
        assert audit.call_args.args[0] == "user.token_delete"

    def test_a_token_id_of_another_user_is_404_even_for_an_admin(self, admin, store):
        """The path names the owner; the id must belong to them."""
        issue_token(store, BOB, name="bobs")
        (record,) = store.list_user_tokens(BOB)

        response = admin.delete(f"{_of(ALICE)}/{record.id}")
        assert response.status_code == 404
        assert [t.name for t in store.list_user_tokens(BOB)] == ["bobs"]

    def test_revoke_all_ends_every_token_and_is_audited(self, admin, anonymous, store, audit):
        tokens = [issue_token(store, ALICE, name=f"t{i}") for i in range(3)]

        response = admin.delete(_of(ALICE))

        assert response.json() == {"revoked": 3}
        assert all(anonymous.get(TOKENS, headers=_basic(ALICE, t)).status_code == 401 for t in tokens)
        assert audit.call_args.args[0] == "user.tokens_revoked"
        assert audit.call_args.kwargs["detail"] == {"tokens": 3, "reason": "admin_revoke_all"}

    def test_an_unknown_user_is_404(self, admin):
        assert admin.get(_of("ghost@example.com")).status_code == 404
        response = admin.post(_of("ghost@example.com"), json={"name": "x", "expiration": _expiry()})
        assert response.status_code == 404
        response = admin.delete(_of("ghost@example.com"))
        assert response.status_code == 404

    def test_deactivating_a_user_deletes_their_tokens(self, admin, store):
        issue_token(store, ALICE, name="ci")

        response = admin.patch(f"/api/2.0/mlflow/users/{ALICE}/active", json={"active": False})
        assert response.status_code == 200

        assert store.list_user_tokens(ALICE) == []


class TestAuthMethodMarker:
    """``AuthMiddleware`` records which credential it tried, in the order it tries them."""

    @pytest.mark.parametrize(
        "header, expected",
        [
            ("Basic dXNlcjp0b2tlbg==", "basic"),
            ("Bearer eyJhbGciOi", "bearer"),
            (None, "session"),
            ("Negotiate abc", "session"),
        ],
    )
    def test_the_marker_follows_the_authorization_header(self, header, expected):
        from starlette.requests import Request as StarletteRequest

        from mlflow_oidc_auth.middleware.auth_middleware import _auth_method

        headers = [(b"authorization", header.encode())] if header else []
        request = StarletteRequest({"type": "http", "method": "GET", "path": "/", "headers": headers})

        assert _auth_method(request) == expected


class TestWorkloadTokensCannotMint:
    """A short-lived workload credential (Kubernetes, CI identity) must not mint a year-long access token."""

    def test_the_marker_distinguishes_a_workload_bearer(self):
        from starlette.requests import Request as StarletteRequest

        from mlflow_oidc_auth.middleware.auth_middleware import _auth_method

        request = StarletteRequest({"type": "http", "method": "GET", "path": "/", "headers": [(b"authorization", b"Bearer eyJ")]})

        assert _auth_method(request, workload_bearer=True) == "workload"
        assert _auth_method(request, workload_bearer=False) == "bearer"

    @pytest.mark.parametrize("method, allowed", [("session", True), ("bearer", True), ("workload", False), ("basic", False)])
    def test_only_an_interactive_sign_in_may_issue(self, method, allowed):
        import asyncio

        from fastapi import HTTPException

        from mlflow_oidc_auth.dependencies import require_interactive_login

        class _State:
            auth_method = method

        class _Request:
            state = _State()

        if allowed:
            asyncio.run(require_interactive_login(_Request()))
        else:
            with pytest.raises(HTTPException):
                asyncio.run(require_interactive_login(_Request()))

    def test_the_bearer_path_flags_a_workload_token(self):
        """``_authenticate_bearer_token`` marks a token from a non-interactive provider."""
        import asyncio
        from unittest.mock import MagicMock

        from mlflow_oidc_auth.middleware import auth_middleware as middleware_module

        middleware = middleware_module.AuthMiddleware(app=MagicMock())
        provider = MagicMock(type="k8s")

        async def run(provider_type, interactive=True):
            provider.type = provider_type
            provider.interactive = interactive
            with (
                patch.object(middleware_module, "validate_token", return_value={"sub": "x"}),
                patch.object(middleware, "_provider_for", return_value=provider),
                patch.object(middleware, "_authenticate_service_account", return_value=(True, "svc", "")),
                patch.object(middleware_module, "extract_username", return_value=("person@example.com", None)),
            ):
                marker = middleware_module._WORKLOAD_BEARER.set(False)
                try:
                    await middleware._authenticate_bearer_token("Bearer tok")
                    return middleware_module._WORKLOAD_BEARER.get()
                finally:
                    middleware_module._WORKLOAD_BEARER.reset(marker)

        assert asyncio.run(run("k8s", interactive=False)) is True
        assert asyncio.run(run("oidc", interactive=False)) is True, "a token-only OIDC issuer is a workload too"
        assert asyncio.run(run("oidc")) is False


class TestRoutesDoNotShadowUsernames:
    """The caller's own tokens live under ``/users/current/``, a path already reserved, so a user
    literally named ``tokens`` is still reachable through the per-user routes (#415 review)."""

    def test_a_user_named_tokens_is_still_addressable(self, admin, store):
        store.create_user("tokens", "A user called tokens")

        profile = admin.get("/api/2.0/mlflow/users/tokens")
        assert profile.status_code == 200
        assert profile.json()["username"] == "tokens"

        response = admin.delete("/api/2.0/mlflow/users/tokens/sessions")
        assert response.status_code == 200

        issued = admin.post(_of("tokens"), json={"name": "ci", "expiration": _expiry()})
        assert issued.status_code == 201
        assert [t.name for t in store.list_user_tokens("tokens")] == ["ci"]
