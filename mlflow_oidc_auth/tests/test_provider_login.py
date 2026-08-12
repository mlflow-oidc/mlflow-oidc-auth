"""Per-provider login and the RFC 9207 mix-up defence (issue #316).

Three things become possible once a deployment has more than one authorization server, and all
three are decided here:

* **A response can arrive from the wrong one.** An authorization response carries ``code`` and
  ``state`` and nothing that says who sent it, so with two providers the client cannot tell them
  apart by looking. RFC 9207 adds ``iss``; the decision function landed with the adversarial
  suite in #307, and this is where it is wired in.
* **Two logins can be in flight at once.** The state used to be one cookie key, so a second tab
  overwrote the first. It is a row per attempt now.
* **A response can be replayed.** Consuming the row *is* the CSRF check, so the second use of a
  captured callback finds nothing.
"""

from types import SimpleNamespace

import pytest

import mlflow_oidc_auth.routers.auth as auth_router_mod
from mlflow_oidc_auth.provider_registry import ProviderConfig, RegistryLoadResult
from mlflow_oidc_auth.repository.auth_state import AuthAttempt

ENTRA = "https://login.entra.invalid/tenant"
OKTA = "https://okta.invalid"


class DummyRequest:
    def __init__(self, root_path="", **query):
        self.session = {}
        self.base_url = "http://testserver"
        self.query_params = _Query(query)
        self.scope = {"root_path": root_path}


class _Query(dict):
    """A query-params mapping with ``getlist``, as Starlette's has."""

    def getlist(self, key):
        value = self.get(key)
        if value is None:
            return []
        return value if isinstance(value, list) else [value]


@pytest.fixture
def two_providers(monkeypatch):
    registry = RegistryLoadResult(
        providers=[
            ProviderConfig(id="entra", type="oidc", display_name="Entra ID", audience="mlflow", issuer=ENTRA),
            ProviderConfig(id="okta", type="oidc", display_name="Okta", audience="mlflow", issuer=OKTA),
            ProviderConfig(id="cluster", type="k8s", display_name="Kubernetes", audience="mlflow-api", issuer="https://k8s.invalid", interactive=False),
        ],
        errors=[],
        source="env",
    )
    monkeypatch.setattr(auth_router_mod.config, "AUTH_PROVIDERS", registry, raising=False)
    return registry


@pytest.fixture
def attempt_at(monkeypatch):
    """Make the callback see an in-flight attempt at a chosen provider."""

    def _install(provider_id, state="state-1", redirect_after_login=None):
        monkeypatch.setattr(
            auth_router_mod.store,
            "consume_auth_state",
            lambda s: AuthAttempt(state=s, provider_id=provider_id, redirect_after_login=redirect_after_login) if s == state else None,
            raising=False,
        )

    return _install


@pytest.fixture
def advertises_iss(monkeypatch):
    """Control whether the provider claims to send ``iss``."""

    def _install(supported):
        async def _check(provider):
            return supported

        monkeypatch.setattr(auth_router_mod, "_iss_parameter_supported", _check)

    return _install


class TestTheProviderList:
    """What #317's login picker renders."""

    @pytest.mark.asyncio
    async def test_only_interactive_providers_are_listed(self, two_providers):
        response = await auth_router_mod.providers(DummyRequest())

        import json

        listed = json.loads(response.body)["providers"]
        assert [entry["id"] for entry in listed] == ["entra", "okta"], "a cluster issuer has no browser flow to start"

    @pytest.mark.asyncio
    async def test_each_entry_carries_a_login_url(self, two_providers):
        import json

        listed = json.loads((await auth_router_mod.providers(DummyRequest())).body)["providers"]

        assert listed[0]["login_url"].endswith("/login/entra")
        assert listed[0]["display_name"] == "Entra ID"

    @pytest.mark.asyncio
    async def test_nothing_about_the_configuration_leaks(self, two_providers):
        """It is reachable before anyone has logged in, so it carries what a login page needs
        and nothing else — no issuer, no audience, no client id, no key source."""
        import json

        body = json.loads((await auth_router_mod.providers(DummyRequest())).body)

        assert set(body["providers"][0]) == {"id", "display_name", "type", "login_url"}
        assert ENTRA not in json.dumps(body)


class TestAnUnknownProviderIs404:
    @pytest.mark.asyncio
    async def test_login_at_an_unknown_provider(self, two_providers):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            await auth_router_mod.login_with_provider(DummyRequest(), "nope")

        assert excinfo.value.status_code == 404

    @pytest.mark.asyncio
    async def test_login_at_a_non_interactive_provider(self, two_providers):
        """A Kubernetes issuer verifies tokens but has no authorization endpoint to redirect to,
        so naming it in a login URL is a 404 rather than a broken redirect."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            await auth_router_mod.login_with_provider(DummyRequest(), "cluster")

        assert excinfo.value.status_code == 404

    @pytest.mark.asyncio
    async def test_callback_for_an_unknown_provider(self, two_providers):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            await auth_router_mod.callback_for_provider(DummyRequest(), "nope")

        assert excinfo.value.status_code == 404


class TestTheMixUpDefence:
    """The attack: an authorization response from one server delivered to a client that is
    waiting for another."""

    async def _callback(self, request, provider_id="entra"):
        """Arrives at the callback of the provider the attempt started at, unless a case says
        otherwise — the path check comes first, and these cases are about ``iss``."""
        return await auth_router_mod._process_oidc_callback_fastapi(request, {}, provider_id=provider_id)

    @pytest.mark.asyncio
    async def test_a_response_from_another_issuer_is_refused(self, two_providers, attempt_at, advertises_iss):
        attempt_at("entra")
        advertises_iss(True)

        _, errors = await self._callback(DummyRequest(state="state-1", code="c", iss=OKTA))

        assert errors and "unexpected issuer" in errors[0]

    @pytest.mark.asyncio
    async def test_a_stripped_iss_is_refused_when_the_provider_sends_one(self, two_providers, attempt_at, advertises_iss):
        """Otherwise the defence is one deleted query parameter away from being switched off."""
        attempt_at("entra")
        advertises_iss(True)

        _, errors = await self._callback(DummyRequest(state="state-1", code="c"))

        assert errors and "unexpected issuer" in errors[0]

    @pytest.mark.asyncio
    async def test_a_missing_iss_is_allowed_when_the_provider_advertises_nothing(self, two_providers, attempt_at, advertises_iss):
        """RFC 9207 is recent; refusing here would break logins that work today."""
        attempt_at("entra")
        advertises_iss(False)

        _, errors = await self._callback(DummyRequest(state="state-1", code="c"))

        assert not any("issuer" in error for error in errors), errors

    @pytest.mark.asyncio
    async def test_a_matching_iss_passes(self, two_providers, attempt_at, advertises_iss):
        attempt_at("entra")
        advertises_iss(True)

        _, errors = await self._callback(DummyRequest(state="state-1", code="c", iss=ENTRA))

        assert not any("issuer" in error for error in errors), errors

    @pytest.mark.asyncio
    async def test_a_repeated_iss_is_refused(self, two_providers, attempt_at, advertises_iss):
        """``?iss=honest&iss=attacker`` names two issuers, so it can be attributed to neither."""
        attempt_at("entra")
        advertises_iss(True)

        _, errors = await self._callback(DummyRequest(state="state-1", code="c", iss=[ENTRA, OKTA]))

        assert errors and "unexpected issuer" in errors[0]

    @pytest.mark.asyncio
    async def test_a_response_cannot_be_completed_at_another_providers_callback(self, two_providers, attempt_at, advertises_iss):
        """The first thing a mix-up tries: deliver the response to the wrong callback path."""
        attempt_at("entra")
        advertises_iss(False)

        _, errors = await self._callback(DummyRequest(state="state-1", code="c"), provider_id="okta")

        assert errors and "Invalid state parameter" in errors[0]


class TestTheAttemptIsSingleUse:
    @pytest.mark.asyncio
    async def test_an_unknown_state_is_refused(self, two_providers, attempt_at):
        attempt_at("entra", state="state-1")

        _, errors = await auth_router_mod._process_oidc_callback_fastapi(DummyRequest(state="other", code="c"), {})

        assert errors == ["Invalid state parameter"]

    @pytest.mark.asyncio
    async def test_a_missing_state_is_refused(self, two_providers, attempt_at):
        attempt_at("entra")

        _, errors = await auth_router_mod._process_oidc_callback_fastapi(DummyRequest(code="c"), {})

        assert errors == ["Invalid state parameter"]

    @pytest.mark.asyncio
    async def test_a_provider_removed_mid_flight_is_refused(self, two_providers, attempt_at):
        """There is no policy left to apply to the response, so there is nothing safe to do with
        it."""
        attempt_at("retired-provider")

        _, errors = await auth_router_mod._process_oidc_callback_fastapi(DummyRequest(state="state-1", code="c"), {})

        assert errors and "no longer configured" in errors[0]


class TestLoginStartsAnAttempt:
    @pytest.mark.asyncio
    async def test_the_attempt_names_the_provider(self, two_providers, monkeypatch):
        recorded = {}

        def create(provider_id, **kwargs):
            recorded.update({"provider_id": provider_id, **kwargs})
            return "state-1"

        monkeypatch.setattr(auth_router_mod.store, "create_auth_state", create, raising=False)
        monkeypatch.setattr(auth_router_mod, "is_oidc_configured", lambda provider_id=None: True)
        monkeypatch.setattr(auth_router_mod, "assert_pkce_supported", _noop)
        monkeypatch.setattr(auth_router_mod, "get_client", lambda provider_id=None: SimpleNamespace(authorize_redirect=_redirect), raising=False)
        monkeypatch.setattr(auth_router_mod, "get_configured_or_dynamic_redirect_uri", lambda request, callback_path, configured_uri=None: "http://cb")

        await auth_router_mod._begin_login(DummyRequest(), "okta")

        assert recorded["provider_id"] == "okta"

    @pytest.mark.asyncio
    async def test_each_provider_gets_its_own_callback_path(self, two_providers, monkeypatch):
        """A shared callback path would mean a response could be delivered to a provider it did
        not come from, which is the ambiguity the whole defence exists to remove."""
        paths = []

        monkeypatch.setattr(auth_router_mod.store, "create_auth_state", lambda provider_id, **kwargs: "state-1", raising=False)
        monkeypatch.setattr(auth_router_mod, "is_oidc_configured", lambda provider_id=None: True)
        monkeypatch.setattr(auth_router_mod, "assert_pkce_supported", _noop)
        monkeypatch.setattr(auth_router_mod, "get_client", lambda provider_id=None: SimpleNamespace(authorize_redirect=_redirect), raising=False)
        monkeypatch.setattr(
            auth_router_mod,
            "get_configured_or_dynamic_redirect_uri",
            lambda request, callback_path, configured_uri=None: paths.append(callback_path) or "http://cb",
        )

        await auth_router_mod._begin_login(DummyRequest(), "okta")
        await auth_router_mod._begin_login(DummyRequest(), "default")

        assert paths == ["/callback/okta", "/callback"], "the default keeps the legacy path, so registered redirect URIs still work"


async def _noop(*args, **kwargs):
    return None


async def _redirect(request, redirect_uri=None, state=None):
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url=redirect_uri)


class TestTheProviderCannotComeFromTheQueryString:
    """``/login?provider_id=x`` must not reach the flow: the 404 gate lives on the path-scoped
    route, and a query parameter would step around it."""

    @pytest.mark.asyncio
    async def test_login_takes_no_provider_query_parameter(self):
        import inspect

        assert "provider_id" not in inspect.signature(auth_router_mod.login).parameters

    @pytest.mark.asyncio
    async def test_callback_takes_no_provider_query_parameter(self):
        import inspect

        assert "provider_id" not in inspect.signature(auth_router_mod.callback).parameters


class TestASecondProviderCanNowLogIn:
    """#318 landed with this branch, so the hold-back is gone.

    What makes it safe is not the login route — it is that an unbound identity from a second
    provider is a *new* principal (#309) and cannot take a username someone else already answers
    to (#318). Those are asserted in ``test_provisioning_policy.py``; this is the plumbing.
    """

    @staticmethod
    def _build(entries):
        from types import SimpleNamespace as NS
        import json

        from mlflow_oidc_auth.provider_registry import build_provider_registry

        class Manager:
            @staticmethod
            def get(key, default=None):
                return json.dumps(entries) if key == "AUTH_PROVIDERS" else default

        return build_provider_registry(
            Manager(),
            NS(
                OIDC_PROVIDER_DISPLAY_NAME="Login with OIDC",
                OIDC_AUDIENCE=None,
                OIDC_ISSUER=None,
                OIDC_DISCOVERY_URL="https://idp.example.com/.well-known/openid-configuration",
                OIDC_CLIENT_ID="client",
            ),
        )

    @staticmethod
    def _entry(**overrides):
        entry = {
            "id": "okta",
            "type": "oidc",
            "audience": "mlflow",
            "issuer": "https://okta.example.com",
            "discovery_url": "https://okta.example.com/.well-known/openid-configuration",
        }
        entry.update(overrides)
        return entry

    def test_a_second_provider_is_interactive(self):
        result = self._build([self._entry(interactive=True)])

        assert [provider.id for provider in result.providers] == ["okta"]
        assert result.providers[0].interactive is True
        assert [provider.id for provider in result.interactive_providers()] == ["okta"]

    def test_a_provider_can_still_be_bearer_only(self):
        result = self._build([self._entry(interactive=False)])

        assert result.interactive_providers() == []


class TestTheReturnTargetCannotLeaveTheOrigin:
    """``?next=`` is stored in the attempt row and redirected to after a successful login — the
    ideal moment to land a victim on a lookalike page."""

    @pytest.mark.parametrize(
        "target",
        ["//evil.com", "https://evil.com", "javascript:alert(1)", "/\\evil.com", "/\tevil.com", "/\r\n/evil.com", "\\\\evil.com"],
    )
    def test_anything_a_browser_would_resolve_off_origin_is_dropped(self, target):
        assert auth_router_mod._sanitize_next(target) is None

    @pytest.mark.parametrize("target", ["/users", "/oidc/ui/groups", "/#/experiments/0", "/a?b=c"])
    def test_real_paths_survive(self, target):
        assert auth_router_mod._sanitize_next(target) == target


class TestAnExistingUserCanStillLogIn:
    """The path every user of every upgraded deployment takes, driven through the callback
    itself rather than the policy function.

    The unit tests for adoption live in ``test_provisioning_policy.py``; this is here because the
    callback fixtures elsewhere patch ``has_user`` to False, so the existing-user branch was
    never exercised end to end — which is exactly how a change that locked out every existing
    user passed a green suite.
    """

    @pytest.fixture
    def existing_user_callback(self, monkeypatch):
        registry = RegistryLoadResult(
            providers=[ProviderConfig(id="default", type="oidc", audience="mlflow", issuer=ENTRA)],
            errors=[],
            source="legacy",
        )
        monkeypatch.setattr(auth_router_mod.config, "AUTH_PROVIDERS", registry, raising=False)
        monkeypatch.setattr(auth_router_mod.config, "OIDC_GROUP_DETECTION_PLUGIN", None, raising=False)
        monkeypatch.setattr(auth_router_mod.config, "OIDC_GROUPS_ATTRIBUTE", "groups", raising=False)
        monkeypatch.setattr(auth_router_mod.config, "OIDC_GROUP_NAME", ["mlflow"], raising=False)
        monkeypatch.setattr(auth_router_mod.config, "OIDC_ADMIN_GROUP_NAME", ["mlflow-admin"], raising=False)
        monkeypatch.setattr(auth_router_mod.config, "MLFLOW_ENABLE_WORKSPACES", False, raising=False)
        monkeypatch.setattr(
            auth_router_mod.store,
            "consume_auth_state",
            lambda state: AuthAttempt(state=state, provider_id="default"),
            raising=False,
        )

        class _Identities:
            """The state the Phase 0 backfill leaves: a legacy row keyed on the username."""

            def __init__(self):
                self.bound = {("default", "alice@corp.com"): "alice@corp.com"}
                self.links = []

            def get_username_by_identity(self, provider_id, subject):
                return self.bound.get((provider_id, subject))

            def list_providers_for_username(self, username):
                return [provider for (provider, _), name in self.bound.items() if name == username]

            def link(self, provider_id, subject, username, **kwargs):
                self.links.append((provider_id, subject, username))
                self.bound[(provider_id, subject)] = username
                return True

        identities = _Identities()
        monkeypatch.setattr(auth_router_mod.store, "user_identity_repo", identities, raising=False)
        monkeypatch.setattr(auth_router_mod.store, "has_user", lambda username: username == "alice@corp.com", raising=False)
        monkeypatch.setattr(auth_router_mod.store, "get_groups_for_user", lambda username: ["mlflow"], raising=False)

        created = []
        monkeypatch.setattr("mlflow_oidc_auth.user.create_user", lambda **kwargs: created.append(kwargs))
        monkeypatch.setattr("mlflow_oidc_auth.user.populate_groups", lambda **kwargs: None)
        monkeypatch.setattr("mlflow_oidc_auth.user.update_user", lambda **kwargs: None)

        async def _exchange(request, provider_id=None):
            return {
                "access_token": "at",
                "userinfo": {"sub": "auth0|6f3a", "email": "alice@corp.com", "name": "Alice", "groups": ["mlflow"]},
            }

        monkeypatch.setattr(auth_router_mod, "_authorize_access_token_with_key_refresh", _exchange)
        monkeypatch.setattr(auth_router_mod, "get_client", lambda provider_id=None: SimpleNamespace(authorize_access_token=_exchange), raising=False)
        monkeypatch.setattr(auth_router_mod, "_iss_parameter_supported", _no_iss)
        return identities, created

    @pytest.mark.asyncio
    async def test_a_pre_existing_user_signs_in_and_is_adopted(self, existing_user_callback):
        """A real ``sub`` is not a username, so the backfilled row does not match it. The account
        is adopted rather than refused, and the real subject is bound for next time."""
        identities, _ = existing_user_callback
        request = DummyRequest(state="state-1", code="c")

        username, errors = await auth_router_mod._process_oidc_callback_fastapi(request, request.session)

        assert errors == []
        assert username == "alice@corp.com"
        assert ("default", "auth0|6f3a", "alice@corp.com") in identities.links

    @pytest.mark.asyncio
    async def test_the_second_login_matches_on_the_bound_identity(self, existing_user_callback):
        identities, _ = existing_user_callback
        first = DummyRequest(state="state-1", code="c")
        await auth_router_mod._process_oidc_callback_fastapi(first, first.session)

        second = DummyRequest(state="state-1", code="c")
        username, errors = await auth_router_mod._process_oidc_callback_fastapi(second, second.session)

        assert errors == []
        assert username == "alice@corp.com"


async def _no_iss(provider):
    return False


class TestTheLegacyCallbackBelongsToTheDefaultProvider:
    """``/callback`` is not "whoever asks" — it is the ``default`` provider's URL.

    Treating an unscoped path as having no opinion about the provider would let anyone able to
    deliver an authorization response there opt out of the path check entirely, which is one of
    the three mix-up defences.
    """

    @pytest.mark.asyncio
    async def test_a_second_providers_response_is_refused_at_the_legacy_callback(self, two_providers, attempt_at, advertises_iss):
        attempt_at("entra")
        advertises_iss(False)

        _, errors = await auth_router_mod._process_oidc_callback_fastapi(DummyRequest(state="state-1", code="c"), {}, provider_id=None)

        assert errors == ["Invalid state parameter"]

    @pytest.mark.asyncio
    async def test_the_default_providers_response_is_accepted_there(self, monkeypatch, attempt_at, advertises_iss):
        monkeypatch.setattr(
            auth_router_mod.config,
            "AUTH_PROVIDERS",
            RegistryLoadResult(providers=[ProviderConfig(id="default", type="oidc", audience="mlflow", issuer=ENTRA)], errors=[], source="legacy"),
            raising=False,
        )
        attempt_at("default")
        advertises_iss(False)

        _, errors = await auth_router_mod._process_oidc_callback_fastapi(DummyRequest(state="state-1", code="c"), {}, provider_id=None)

        assert "Invalid state parameter" not in errors

    @pytest.mark.asyncio
    async def test_login_at_the_default_provider_uses_the_legacy_callback_path(self, monkeypatch):
        """Its redirect URI is the one already registered at the operator's IdP, whichever route
        started the login."""
        monkeypatch.setattr(
            auth_router_mod.config,
            "AUTH_PROVIDERS",
            RegistryLoadResult(providers=[ProviderConfig(id="default", type="oidc", audience="mlflow", issuer=ENTRA)], errors=[], source="legacy"),
            raising=False,
        )
        paths = []
        monkeypatch.setattr(auth_router_mod, "is_oidc_configured", lambda provider_id=None: True)
        monkeypatch.setattr(auth_router_mod.store, "create_auth_state", lambda provider_id, **kwargs: "state-1", raising=False)
        monkeypatch.setattr(auth_router_mod, "assert_pkce_supported", _noop)
        monkeypatch.setattr(auth_router_mod, "get_client", lambda provider_id=None: SimpleNamespace(authorize_redirect=_redirect), raising=False)
        monkeypatch.setattr(
            auth_router_mod,
            "get_configured_or_dynamic_redirect_uri",
            lambda request, callback_path, configured_uri=None: paths.append(callback_path) or "http://cb",
        )

        await auth_router_mod.login_with_provider(DummyRequest(), "default")

        assert paths == ["/callback"]


class TestTheExchangeNeverBorrowsAnotherProvidersClient:
    """An authorization code minted by one issuer must never be posted to another's token
    endpoint — that hands one IdP a credential belonging to a different one."""

    @pytest.mark.asyncio
    async def test_a_named_provider_with_no_client_fails(self, monkeypatch):
        monkeypatch.setattr(auth_router_mod, "get_client", lambda provider_id=None: None, raising=False)

        with pytest.raises(RuntimeError, match="partner"):
            auth_router_mod._client_for_exchange("partner")

    @pytest.mark.asyncio
    async def test_the_default_provider_still_resolves_to_the_legacy_client(self, monkeypatch):
        legacy = SimpleNamespace(authorize_access_token=_redirect)
        monkeypatch.setattr(auth_router_mod, "get_client", lambda provider_id=None: None, raising=False)
        monkeypatch.setattr(auth_router_mod.oauth, "oidc", legacy, raising=False)

        assert auth_router_mod._client_for_exchange("default") is legacy


class TestTheLoginUrlsDoNotComeFromTheHostHeader:
    """They are the buttons a login page offers, on an unauthenticated endpoint.

    They carry no origin at all. An absolute URL would have to take its origin from the request,
    and the request's origin is the ``Host`` header — which the client sets.
    """

    @pytest.mark.asyncio
    async def test_the_login_url_is_a_path_with_no_origin(self, two_providers, monkeypatch):
        import json

        monkeypatch.setattr(auth_router_mod.config, "OIDC_REDIRECT_URI", "https://mlflow.corp.example/callback", raising=False)
        request = DummyRequest()
        request.base_url = "http://evil.example"

        listed = json.loads((await auth_router_mod.providers(request)).body)["providers"]

        assert listed[0]["login_url"] == "/login/entra"

    @pytest.mark.asyncio
    async def test_a_hostile_host_header_cannot_reach_the_button(self, two_providers, monkeypatch):
        import json

        monkeypatch.setattr(auth_router_mod.config, "OIDC_REDIRECT_URI", None, raising=False)
        request = DummyRequest()
        request.base_url = "http://evil.example"

        listed = json.loads((await auth_router_mod.providers(request)).body)["providers"]

        assert all("evil.example" not in entry["login_url"] for entry in listed)
        assert all(entry["login_url"].startswith("/") for entry in listed)

    @pytest.mark.asyncio
    async def test_a_mounted_deployment_keeps_its_prefix(self, two_providers):
        """``root_path`` comes from the mount, not from a header, so it is safe to include."""
        import json

        listed = json.loads((await auth_router_mod.providers(DummyRequest(root_path="/mlflow"))).body)["providers"]

        assert listed[0]["login_url"] == "/mlflow/login/entra"

    @pytest.mark.asyncio
    async def test_a_protocol_relative_prefix_is_discarded(self, two_providers):
        """``root_path`` is not always the mount — ``X-Forwarded-Prefix`` also sets it.

        ``//evil.example`` starts with a slash, so it survives the proxy middleware's
        normalisation, and concatenating it would produce a protocol-relative URL that a browser
        resolves off-origin. A discarded prefix is a broken link; an honoured one is a login
        somewhere else.
        """
        import json

        listed = json.loads((await auth_router_mod.providers(DummyRequest(root_path="//evil.example"))).body)["providers"]

        assert all(entry["login_url"] == f"/login/{entry['id']}" for entry in listed)

    @pytest.mark.asyncio
    async def test_a_prefix_that_is_not_a_path_is_discarded(self, two_providers):
        import json

        listed = json.loads((await auth_router_mod.providers(DummyRequest(root_path="evil.example"))).body)["providers"]

        assert all(entry["login_url"].startswith("/login/") for entry in listed)

    @pytest.mark.asyncio
    async def test_the_response_is_not_cacheable(self, two_providers):
        response = await auth_router_mod.providers(DummyRequest())

        assert response.headers["cache-control"] == "no-store"
