"""Claims the ID token lacks are completed from the provider's UserInfo endpoint.

authlib puts the validated ID token's claims under ``token["userinfo"]``; it never calls the
UserInfo endpoint. Providers that release email, name or groups only from that endpoint therefore
could not complete a login. These tests drive the real callback with a fake authlib client and pin
the rules: the ID token stays the base and always wins, the endpoint is called only when a needed
claim is missing, its ``sub`` must match the ID token's (OpenID Connect Core 5.3.2), and it never
supplies a claim describing the authentication itself.
"""

import time
from types import SimpleNamespace

import httpx2
import pytest
from authlib.integrations.starlette_client import OAuth

import mlflow_oidc_auth.routers.auth as auth_router_mod
from mlflow_oidc_auth.provider_registry import ProviderConfig, RegistryLoadResult
from mlflow_oidc_auth.repository.auth_state import AuthAttempt

ISSUER = "https://idp.invalid"
OTHER_ISSUER = "https://other-idp.invalid"
SUB = "subject-123"


class DummyRequest:
    def __init__(self, **query):
        self.session = {}
        self.base_url = "http://testserver"
        self.query_params = _Query(query)
        self.scope = {"root_path": ""}
        self.state = SimpleNamespace()


class _Query(dict):
    def getlist(self, key):
        value = self.get(key)
        if value is None:
            return []
        return value if isinstance(value, list) else [value]


class FakeClient:
    """Stands in for a per-provider authlib client."""

    def __init__(self, id_claims, userinfo=None, *, metadata=None, userinfo_error=None):
        self.id_claims = id_claims
        self.userinfo_response = userinfo
        self.userinfo_error = userinfo_error
        self.server_metadata = {"issuer": ISSUER, "userinfo_endpoint": f"{ISSUER}/userinfo"} if metadata is None else metadata
        self.userinfo_calls = []

    async def authorize_access_token(self, request):
        return {"access_token": "at", "token_type": "Bearer", "id_token": "idt", "userinfo": dict(self.id_claims)}

    async def load_server_metadata(self):
        return self.server_metadata

    async def userinfo(self, **kwargs):
        self.userinfo_calls.append(kwargs)
        if self.userinfo_error is not None:
            raise self.userinfo_error
        return self.userinfo_response


class _Identities:
    def __init__(self):
        self.links = []

    def get_username_by_identity(self, provider_id, subject):
        return None

    def list_providers_for_username(self, username):
        return []

    def link(self, provider_id, subject, username, **kwargs):
        self.links.append((provider_id, subject, username))
        return True


async def _no_iss(provider):
    return False


@pytest.fixture
def login(monkeypatch):
    """Install providers and clients; returns a coroutine that runs one callback."""

    monkeypatch.setattr(auth_router_mod.config, "OIDC_GROUP_DETECTION_PLUGIN", None, raising=False)
    monkeypatch.setattr(auth_router_mod.config, "OIDC_GROUPS_ATTRIBUTE", "groups", raising=False)
    monkeypatch.setattr(auth_router_mod.config, "OIDC_GROUP_NAME", ["mlflow"], raising=False)
    monkeypatch.setattr(auth_router_mod.config, "OIDC_ADMIN_GROUP_NAME", ["mlflow-admin"], raising=False)
    monkeypatch.setattr(auth_router_mod.config, "OIDC_USERNAME_FIELD", ["email", "preferred_username"], raising=False)
    monkeypatch.setattr(auth_router_mod.config, "OIDC_DISPLAY_NAME_FIELD", ["name"], raising=False)
    monkeypatch.setattr(auth_router_mod.config, "MLFLOW_ENABLE_WORKSPACES", False, raising=False)
    monkeypatch.setattr(auth_router_mod, "_iss_parameter_supported", _no_iss)

    identities = _Identities()
    created = []
    monkeypatch.setattr(auth_router_mod.store, "user_identity_repo", identities, raising=False)
    monkeypatch.setattr(auth_router_mod.store, "has_user", lambda username: False, raising=False)
    monkeypatch.setattr(auth_router_mod.store, "get_groups_for_user", lambda username: [], raising=False)
    monkeypatch.setattr(auth_router_mod, "_account_is_inactive", lambda username: False)
    monkeypatch.setattr("mlflow_oidc_auth.user.create_user", lambda **kwargs: created.append(kwargs))
    monkeypatch.setattr("mlflow_oidc_auth.user.populate_groups", lambda **kwargs: None)
    monkeypatch.setattr("mlflow_oidc_auth.user.update_user", lambda **kwargs: None)

    clients: dict = {}

    def _install(client, provider_id="default", issuer=ISSUER, userinfo_groups=False):
        clients[provider_id] = (client, issuer, userinfo_groups)
        registry = RegistryLoadResult(
            providers=[ProviderConfig(id=pid, type="oidc", audience="mlflow", issuer=iss, userinfo_groups=ug) for pid, (_, iss, ug) in clients.items()],
            errors=[],
            source="env",
        )
        monkeypatch.setattr(auth_router_mod.config, "AUTH_PROVIDERS", registry, raising=False)
        monkeypatch.setattr(auth_router_mod, "get_client", lambda pid=None: clients[pid][0] if pid in clients else None, raising=False)
        return client

    async def _run(provider_id="default"):
        monkeypatch.setattr(
            auth_router_mod.store,
            "consume_auth_state",
            lambda state: AuthAttempt(state=state, provider_id=provider_id),
            raising=False,
        )
        request = DummyRequest(state="state-1", code="c")
        callback_provider = None if provider_id == "default" else provider_id
        return await auth_router_mod._process_oidc_callback_fastapi(request, request.session, provider_id=callback_provider)

    return SimpleNamespace(install=_install, run=_run, created=created, identities=identities)


def _complete_id_claims(**overrides):
    claims = {"sub": SUB, "iss": ISSUER, "aud": "mlflow", "email": "alice@corp.com", "name": "Alice", "groups": ["mlflow"]}
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


class TestTheIdTokenIsEnough:
    @pytest.mark.asyncio
    async def test_no_userinfo_call_when_the_id_token_has_every_needed_claim(self, login):
        client = login.install(FakeClient(_complete_id_claims(), userinfo={"sub": SUB}))

        username, errors = await login.run()

        assert errors == []
        assert username == "alice@corp.com"
        assert client.userinfo_calls == []

    @pytest.mark.asyncio
    async def test_no_call_when_the_provider_advertises_no_userinfo_endpoint(self, login):
        client = login.install(FakeClient(_complete_id_claims(email=None), userinfo={"sub": SUB, "email": "alice@corp.com"}, metadata={"issuer": ISSUER}))

        username, errors = await login.run()

        assert client.userinfo_calls == []
        assert username is None
        assert errors == ["No username provided in OIDC userinfo"]


class TestMissingClaimsAreFilled:
    @pytest.mark.asyncio
    async def test_email_missing_from_the_id_token_is_taken_from_userinfo(self, login):
        client = login.install(
            FakeClient(
                {"sub": SUB, "iss": ISSUER, "aud": "mlflow", "groups": ["mlflow"]},
                userinfo={"sub": SUB, "email": "alice@corp.com", "name": "Alice"},
            )
        )

        username, errors = await login.run()

        assert errors == []
        assert username == "alice@corp.com"
        assert len(client.userinfo_calls) == 1
        assert client.userinfo_calls[0]["token"] == {"access_token": "at", "token_type": "Bearer"}
        assert login.created[0]["display_name"] == "Alice"
        # The subject bound is the ID token's.
        assert login.identities.links == [("default", SUB, "alice@corp.com")]

    @pytest.mark.asyncio
    async def test_groups_missing_from_the_id_token_are_taken_from_userinfo_when_the_provider_opts_in(self, login):
        client = login.install(FakeClient(_complete_id_claims(groups=None), userinfo={"sub": SUB, "groups": ["mlflow"]}), userinfo_groups=True)

        username, errors = await login.run()

        assert errors == []
        assert username == "alice@corp.com"
        assert len(client.userinfo_calls) == 1

    @pytest.mark.asyncio
    async def test_the_username_field_the_id_token_yields_is_kept(self, login):
        """Completing groups must not switch the username from ``preferred_username`` to an
        ``email`` that only UserInfo carries — that would sign the user into another account."""
        login.install(
            FakeClient(
                {"sub": SUB, "preferred_username": "alice", "name": "Alice"},
                userinfo={"sub": SUB, "email": "alice@corp.com", "groups": ["mlflow"]},
            ),
            userinfo_groups=True,
        )

        username, errors = await login.run()

        assert errors == []
        assert username == "alice"


class TestTheSubjectMustMatch:
    @pytest.mark.asyncio
    async def test_a_different_sub_refuses_the_login(self, login):
        login.install(FakeClient(_complete_id_claims(email=None), userinfo={"sub": "someone-else", "email": "mallory@corp.com"}))

        username, errors = await login.run()

        assert username is None
        assert errors == ["User information from the identity provider does not match the signed-in user"]
        assert login.created == []
        assert login.identities.links == []

    @pytest.mark.asyncio
    async def test_a_missing_sub_refuses_the_login(self, login):
        login.install(FakeClient(_complete_id_claims(email=None), userinfo={"email": "alice@corp.com"}))

        username, errors = await login.run()

        assert username is None
        assert errors == ["User information from the identity provider does not match the signed-in user"]
        assert login.created == []

    @pytest.mark.asyncio
    async def test_a_mismatched_sub_refuses_even_when_the_id_token_would_have_sufficed_for_the_username(self, login):
        login.install(FakeClient(_complete_id_claims(groups=None), userinfo={"sub": "someone-else", "groups": ["mlflow-admin"]}), userinfo_groups=True)

        username, errors = await login.run()

        assert username is None
        assert login.created == []

    @pytest.mark.asyncio
    async def test_an_id_token_without_sub_is_not_completed_from_userinfo(self, login):
        """Nothing to bind the response to, so it is not requested at all."""
        client = login.install(FakeClient({"preferred_username": "alice", "name": "Alice"}, userinfo={"sub": "x", "groups": ["mlflow"]}), userinfo_groups=True)

        username, errors = await login.run()

        assert client.userinfo_calls == []
        assert username is None
        assert errors == ["User is not allowed to login"]


class TestTheIdTokenAlwaysWins:
    @pytest.mark.asyncio
    async def test_userinfo_never_overrides_an_id_token_claim(self, login):
        login.install(
            FakeClient(
                _complete_id_claims(name=None, groups=["mlflow"]),
                userinfo={"sub": SUB, "email": "mallory@corp.com", "groups": ["mlflow-admin"], "name": "Alice"},
            )
        )

        username, errors = await login.run()

        assert errors == []
        assert username == "alice@corp.com"
        assert login.created[0]["is_admin"] is False
        assert login.created[0]["display_name"] == "Alice"

    def test_security_claims_are_never_taken_from_userinfo(self):
        id_claims = {"sub": SUB}
        userinfo = {name: "from-userinfo" for name in ("iss", "aud", "exp", "iat", "nbf", "nonce", "azp", "at_hash", "sid", "auth_time", "acr", "amr")}
        userinfo.update({"sub": SUB, "email": "alice@corp.com"})

        merged = auth_router_mod._merge_userinfo_claims(id_claims, userinfo)

        assert merged == {"sub": SUB, "email": "alice@corp.com"}

    def test_email_verified_is_not_paired_with_an_id_token_email(self):
        merged = auth_router_mod._merge_userinfo_claims(
            {"sub": SUB, "email": "alice@corp.com"},
            {"sub": SUB, "email": "other@corp.com", "email_verified": True, "name": "Alice"},
        )

        assert "email_verified" not in merged
        assert merged["email"] == "alice@corp.com"
        assert merged["name"] == "Alice"

    def test_a_coupled_pair_is_taken_whole_when_the_id_token_has_neither_half(self):
        merged = auth_router_mod._merge_userinfo_claims({"sub": SUB}, {"sub": SUB, "email": "alice@corp.com", "email_verified": True})

        assert merged["email"] == "alice@corp.com"
        assert merged["email_verified"] is True


class TestGroupsFromUserinfoAreOptIn:
    """The groups and workspace claims decide access, so UserInfo supplies them only when the
    provider opts in with ``userinfo_groups`` (``OIDC_USERINFO_GROUPS``)."""

    @pytest.mark.asyncio
    async def test_without_the_flag_missing_groups_trigger_no_call_and_stay_empty(self, login):
        client = login.install(FakeClient(_complete_id_claims(groups=None), userinfo={"sub": SUB, "groups": ["mlflow", "mlflow-admin"]}))

        username, errors = await login.run()

        assert client.userinfo_calls == []
        assert username is None
        assert errors == ["User is not allowed to login"]
        assert login.created == []

    @pytest.mark.asyncio
    async def test_without_the_flag_identity_claims_are_filled_but_groups_are_not(self, login, monkeypatch):
        seen = {}
        real_provision = auth_router_mod._provision_login

        def _spy(provider, **kwargs):
            seen.update(kwargs)
            return real_provision(provider, **kwargs)

        monkeypatch.setattr(auth_router_mod, "_provision_login", _spy)
        client = login.install(
            FakeClient(
                {"sub": SUB, "iss": ISSUER, "aud": "mlflow"},
                userinfo={"sub": SUB, "email": "alice@corp.com", "email_verified": True, "name": "Alice", "groups": ["mlflow", "mlflow-admin"]},
            )
        )

        username, errors = await login.run()

        assert len(client.userinfo_calls) == 1
        # The identity came from UserInfo...
        assert seen["username"] == "alice@corp.com"
        assert seen["display_name"] == "Alice"
        assert seen["userinfo"]["email_verified"] is True
        # ...its groups did not, so the group gate refuses.
        assert "groups" not in seen["userinfo"] and seen["user_groups"] == []
        assert username is None
        assert errors == ["User is not allowed to login"]
        assert login.created == []

    def test_without_the_flag_the_merge_drops_groups_and_workspace(self, monkeypatch):
        monkeypatch.setattr(auth_router_mod.config, "OIDC_GROUPS_ATTRIBUTE", "roles", raising=False)
        monkeypatch.setattr(auth_router_mod.config, "OIDC_WORKSPACE_CLAIM_NAME", "tenant", raising=False)
        userinfo = {"sub": SUB, "email": "alice@corp.com", "email_verified": True, "name": "Alice", "roles": ["mlflow-admin"], "tenant": "acme"}

        merged = auth_router_mod._merge_userinfo_claims({"sub": SUB}, userinfo)
        opted_in = auth_router_mod._merge_userinfo_claims({"sub": SUB}, userinfo, userinfo_groups=True)

        assert merged == {"sub": SUB, "email": "alice@corp.com", "email_verified": True, "name": "Alice"}
        assert opted_in["roles"] == ["mlflow-admin"] and opted_in["tenant"] == "acme"

    @pytest.mark.asyncio
    async def test_with_the_flag_groups_are_taken(self, login):
        client = login.install(
            FakeClient({"sub": SUB, "iss": ISSUER, "aud": "mlflow"}, userinfo={"sub": SUB, "email": "alice@corp.com", "groups": ["mlflow"]}),
            userinfo_groups=True,
        )

        username, errors = await login.run()

        assert len(client.userinfo_calls) == 1
        assert errors == []
        assert username == "alice@corp.com"

    @pytest.mark.asyncio
    async def test_with_the_flag_userinfo_groups_never_override_the_id_tokens(self, login):
        login.install(
            FakeClient(_complete_id_claims(name=None), userinfo={"sub": SUB, "name": "Alice", "groups": ["mlflow-admin"]}),
            userinfo_groups=True,
        )

        username, errors = await login.run()

        assert errors == []
        assert login.created[0]["is_admin"] is False


class TestUserinfoFailure:
    @pytest.mark.parametrize(
        "client_kwargs",
        [
            {"userinfo_error": RuntimeError("connection refused")},
            {"userinfo_error": ValueError("Expecting value: line 1 column 1 (char 0)")},  # an application/jwt body
            {"userinfo": ["not", "an", "object"]},
            {"userinfo": None},
        ],
    )
    @pytest.mark.asyncio
    async def test_the_login_proceeds_when_the_id_token_suffices_for_it(self, login, client_kwargs):
        client = login.install(FakeClient(_complete_id_claims(name=None), **client_kwargs))

        username, errors = await login.run()

        assert len(client.userinfo_calls) == 1
        assert errors == []
        assert username == "alice@corp.com"
        assert login.created[0]["display_name"] == "alice@corp.com"

    @pytest.mark.asyncio
    async def test_the_login_fails_when_the_id_token_does_not_suffice(self, login):
        login.install(FakeClient(_complete_id_claims(email=None), userinfo_error=RuntimeError("503")))

        username, errors = await login.run()

        assert username is None
        assert errors == ["No username provided in OIDC userinfo"]


class TestEachProviderUsesItsOwnClient:
    @pytest.mark.asyncio
    async def test_userinfo_goes_to_the_provider_the_login_started_at(self, login):
        default_client = login.install(FakeClient(_complete_id_claims(), userinfo={"sub": SUB, "email": "wrong@corp.com"}))
        partner_client = login.install(
            FakeClient(
                {"sub": "partner-sub", "iss": OTHER_ISSUER, "aud": "mlflow", "name": "Bob", "groups": ["mlflow"]},
                userinfo={"sub": "partner-sub", "email": "bob@partner.com"},
                metadata={"issuer": OTHER_ISSUER, "userinfo_endpoint": f"{OTHER_ISSUER}/userinfo"},
            ),
            provider_id="partner",
            issuer=OTHER_ISSUER,
        )

        username, errors = await login.run("partner")

        assert errors == []
        assert username == "bob@partner.com"
        assert len(partner_client.userinfo_calls) == 1
        assert default_client.userinfo_calls == []
        assert login.identities.links == [("partner", "partner-sub", "bob@partner.com")]


class TestWhichClaimsAreNeeded:
    def test_groups_are_not_needed_with_a_detection_plugin(self, monkeypatch):
        monkeypatch.setattr(auth_router_mod.config, "OIDC_GROUP_DETECTION_PLUGIN", "some.plugin", raising=False)
        monkeypatch.setattr(auth_router_mod.config, "MLFLOW_ENABLE_WORKSPACES", False, raising=False)
        monkeypatch.setattr(auth_router_mod.config, "OIDC_USERNAME_FIELD", ["email"], raising=False)
        monkeypatch.setattr(auth_router_mod.config, "OIDC_DISPLAY_NAME_FIELD", ["name"], raising=False)

        assert auth_router_mod._claims_the_login_lacks({"email": "a@b.c", "name": "A"}) == []

    def test_the_workspace_claim_is_needed_only_when_workspaces_read_it(self, monkeypatch):
        monkeypatch.setattr(auth_router_mod.config, "OIDC_GROUP_DETECTION_PLUGIN", None, raising=False)
        monkeypatch.setattr(auth_router_mod.config, "OIDC_GROUPS_ATTRIBUTE", "groups", raising=False)
        monkeypatch.setattr(auth_router_mod.config, "OIDC_USERNAME_FIELD", ["email"], raising=False)
        monkeypatch.setattr(auth_router_mod.config, "OIDC_DISPLAY_NAME_FIELD", ["name"], raising=False)
        monkeypatch.setattr(auth_router_mod.config, "OIDC_WORKSPACE_CLAIM_NAME", "workspace", raising=False)
        claims = {"email": "a@b.c", "name": "A", "groups": []}

        monkeypatch.setattr(auth_router_mod.config, "MLFLOW_ENABLE_WORKSPACES", True, raising=False)
        monkeypatch.setattr(auth_router_mod.config, "OIDC_WORKSPACE_DETECTION_PLUGIN", None, raising=False)
        assert auth_router_mod._claims_the_login_lacks(claims, userinfo_groups=True) == ["workspace"]
        # Without the opt-in the workspace claim never comes from UserInfo, so it is never "missing".
        assert auth_router_mod._claims_the_login_lacks(claims) == []

        monkeypatch.setattr(auth_router_mod.config, "OIDC_WORKSPACE_DETECTION_PLUGIN", "ws.plugin", raising=False)
        assert auth_router_mod._claims_the_login_lacks(claims, userinfo_groups=True) == []

        monkeypatch.setattr(auth_router_mod.config, "MLFLOW_ENABLE_WORKSPACES", False, raising=False)
        monkeypatch.setattr(auth_router_mod.config, "OIDC_WORKSPACE_DETECTION_PLUGIN", None, raising=False)
        assert auth_router_mod._claims_the_login_lacks(claims, userinfo_groups=True) == []


class TestThroughARealAuthlibClient:
    """The same calls through authlib's own client and HTTP stack, with only the network faked."""

    @staticmethod
    def _client(userinfo_response):
        seen = []

        def handler(request):
            seen.append((request.method, request.url.path, request.headers.get("authorization")))
            if request.url.path.endswith("/openid-configuration"):
                return httpx2.Response(200, json={"issuer": ISSUER, "token_endpoint": f"{ISSUER}/token", "userinfo_endpoint": f"{ISSUER}/userinfo"})
            if request.url.path == "/userinfo":
                return userinfo_response
            return httpx2.Response(200, json={"access_token": "refreshed", "token_type": "Bearer", "refresh_token": "rotated"})

        oauth = OAuth()
        oauth.register(
            "userinfo_test",
            client_id="mlflow",
            client_secret="secret",
            server_metadata_url=f"{ISSUER}/.well-known/openid-configuration",
            client_kwargs={"transport": httpx2.MockTransport(handler)},
        )
        return oauth.userinfo_test, seen

    @staticmethod
    def _token_response():
        # A short-lived access token: authlib treats one expiring within 60 seconds as expired.
        return {"access_token": "at", "token_type": "Bearer", "refresh_token": "rt", "expires_in": 10, "expires_at": int(time.time()) + 10}

    @pytest.mark.asyncio
    async def test_the_access_token_is_sent_and_the_refresh_token_is_never_spent(self):
        client, seen = self._client(httpx2.Response(200, json={"sub": SUB, "email": "alice@corp.com"}))

        claims = await auth_router_mod._fetch_userinfo_claims(client, "default", self._token_response())

        assert claims == {"sub": SUB, "email": "alice@corp.com"}
        assert ("GET", "/userinfo", "Bearer at") in seen
        assert all(path != "/token" for _, path, _ in seen)

    @pytest.mark.parametrize(
        "response",
        [
            httpx2.Response(200, content=b"eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ4In0.sig", headers={"content-type": "application/jwt"}),
            httpx2.Response(401, json={"error": "invalid_token"}),
            httpx2.Response(500, text="oops"),
            httpx2.Response(200, json=["not", "an", "object"]),
        ],
    )
    @pytest.mark.asyncio
    async def test_an_unusable_response_is_a_failed_call(self, response):
        client, _ = self._client(response)

        assert await auth_router_mod._fetch_userinfo_claims(client, "default", self._token_response()) is None
