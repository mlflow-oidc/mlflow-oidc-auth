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
    def __init__(self, **query):
        self.session = {}
        self.base_url = "http://testserver"
        self.query_params = _Query(query)


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

    async def _callback(self, request, provider_id=None):
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


class TestASecondInteractiveProviderIsRefusedForNow:
    """#316 gives every provider a login route and defends the mix-up attack. What it does not
    give is per-provider identity: the username field, the groups attribute and the admin group
    are still read from deployment-wide configuration, and the user row is not namespaced by
    provider.

    A second interactive provider on top of that is account takeover, not a feature — a
    contractor tenant asserting ``email: alice@corp.com`` would land on Alice's account. #318 is
    what makes provisioning and identity binding per-provider; until then this is refused at
    load rather than shipped.
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

    def test_a_second_provider_gets_no_login_button(self, caplog):
        """Coerced off rather than rejected: the entry is still a usable *token* provider, and
        only the browser flow is unsafe."""
        with caplog.at_level("WARNING"):
            result = self._build([self._entry(interactive=True)])

        assert [provider.id for provider in result.providers] == ["okta"]
        assert result.providers[0].interactive is False
        assert result.interactive_providers() == []
        assert any("#318" in record.getMessage() for record in caplog.records)

    def test_the_same_provider_is_fine_for_bearer_tokens(self):
        """Only the browser flow is gated: a token from this issuer is validated per-provider
        already (#313), and none of the identity questions arise."""
        result = self._build([self._entry(interactive=False)])

        assert [provider.id for provider in result.providers] == ["okta"]

    def test_the_default_provider_is_unaffected(self):
        assert build_default().providers[0].interactive is True


def build_default():
    from types import SimpleNamespace as NS

    from mlflow_oidc_auth.provider_registry import build_provider_registry

    class Manager:
        @staticmethod
        def get(key, default=None):
            return default

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
