"""Two issuers, validated independently (issue #313).

Every case here is meaningless with one provider: choosing a validator is only a question when
there is more than one, and it is the choosing that is dangerous. The provider is selected by
the token's own **unverified** ``iss``, which is safe for exactly one reason — the choice can
only ever narrow what follows. An unrecognised issuer selects nothing and the token is refused;
a recognised one selects a provider whose keys, algorithms, issuer and audience are then all
enforced against the token that named it.

The suite in ``suite.py`` runs twice here, once per provider, which is the acceptance criterion
that a new provider inherits the cases rather than restating them.
"""

import pytest

import mlflow_oidc_auth.auth as auth_module

from .suite import Issuer, TokenAdversarySuite, b64
from .test_oidc_bearer_tokens import provider_for, registry_of


@pytest.fixture
def entra():
    """The human-login provider."""
    return Issuer(name="entra", iss="https://login.entra.invalid/tenant", audience="mlflow-tracking")


@pytest.fixture
def kubernetes():
    """The automation provider: a cluster's service-account issuer, minting tokens for a
    different audience and signed with a different key."""
    return Issuer(name="k8s", iss="https://kubernetes.default.svc.invalid", audience="mlflow-api")


@pytest.fixture
def stranger():
    """An issuer this deployment has never heard of.

    The suite's ``foreign`` must be *unconfigured*: with two providers registered, a token from
    the other one is legitimately accepted, so using it as the foreign issuer would assert the
    opposite of what the deployment intends.
    """
    return Issuer(name="stranger", iss="https://stranger.idp.invalid", audience="mlflow-tracking")


@pytest.fixture
def both(entra, kubernetes, monkeypatch):
    """A registry with both providers, each with its own keys."""
    registry = registry_of(
        provider_for(entra, provider_id="entra"),
        provider_for(kubernetes, provider_id="k8s", type="k8s", interactive=False),
    )
    monkeypatch.setattr(auth_module.config, "AUTH_PROVIDERS", registry)

    keys = {"entra": entra.jwks, "k8s": kubernetes.jwks}
    monkeypatch.setattr(auth_module, "_get_provider_jwks", lambda provider, force_refresh=False: keys[provider.id])
    return auth_module.validate_token


class TestBothIssuersWorkAtOnce:
    def test_a_token_from_the_first_issuer_validates(self, both, entra):
        assert both(entra.mint())["iss"] == entra.iss

    def test_a_token_from_the_second_issuer_validates(self, both, kubernetes):
        assert both(kubernetes.mint())["iss"] == kubernetes.iss

    def test_neither_provider_can_verify_the_other_s_tokens(self, both, entra, kubernetes):
        """Each provider's keys are offered to the decoder alone — never a union.

        A union would mean the ``kid`` in an attacker's header selects from every configured
        provider's keys at once, so compromising the weakest issuer would forge tokens for all
        of them.
        """
        assert both(entra.mint(aud=entra.audience)) is not None

        with pytest.raises(Exception):
            # Entra's issuer, signed with the cluster's key: the header names the right issuer,
            # so the right validator is chosen, and its keys refuse the signature.
            both(kubernetes.mint(iss=entra.iss, aud=entra.audience))


class TestAudienceIsPerProvider:
    """The acceptance criterion: a token from issuer A presented with issuer B's audience."""

    def test_the_first_issuer_s_token_is_refused_at_the_second_s_audience(self, both, entra, kubernetes):
        with pytest.raises(Exception):
            both(entra.mint(aud=kubernetes.audience))

    def test_the_second_issuer_s_token_is_refused_at_the_first_s_audience(self, both, entra, kubernetes):
        with pytest.raises(Exception):
            both(kubernetes.mint(aud=entra.audience))

    def test_each_is_accepted_at_its_own(self, both, entra, kubernetes):
        assert both(entra.mint(aud=entra.audience)) is not None
        assert both(kubernetes.mint(aud=kubernetes.audience)) is not None


class TestAnUnknownIssuerHasNoValidator:
    """No fallback, ever. A default validator is the one an attacker aims at, because reaching
    it costs nothing more than an ``iss`` that matches nothing."""

    def test_a_third_issuer_is_refused(self, both):
        stranger = Issuer(name="stranger", iss="https://stranger.invalid", audience="mlflow-tracking")

        with pytest.raises(ValueError, match="does not match any configured provider"):
            both(stranger.mint())

    def test_it_is_refused_even_when_signed_by_a_configured_provider_s_key(self, both, entra):
        """The signature is genuine and the audience is right; only the issuer is unrecognised.
        Falling back to "some provider verified it" would accept this."""
        with pytest.raises(ValueError, match="does not match any configured provider"):
            both(entra.mint(iss="https://stranger.invalid"))

    def test_a_token_with_no_issuer_is_refused(self, both, entra):
        claims = entra.claims()
        claims.pop("iss")

        with pytest.raises(ValueError, match="no issuer"):
            both(entra.mint(claims))

    def test_a_lookalike_issuer_is_refused(self, both, entra):
        """Selection is exact string equality. Anything looser — prefix, suffix, case-insensitive
        — lets an attacker register a host that resolves to someone else's validator."""
        for lookalike in (entra.iss + ".attacker.invalid", entra.iss + "/", entra.iss.upper(), entra.iss.rstrip("/") + "/."):
            with pytest.raises(ValueError):
                both(entra.mint(iss=lookalike))


class TestKeyRotationIsPerIssuer:
    """A shared cache would mean every failed signature refetched whichever provider's keys
    happened to be cached, and two issuers rotating on different schedules would evict each
    other indefinitely."""

    def test_only_the_failing_provider_is_refetched(self, entra, kubernetes, monkeypatch):
        registry = registry_of(
            provider_for(entra, provider_id="entra"),
            provider_for(kubernetes, provider_id="k8s", type="k8s", interactive=False),
        )
        monkeypatch.setattr(auth_module.config, "AUTH_PROVIDERS", registry)

        refreshed = []
        keys = {"entra": entra.jwks, "k8s": kubernetes.jwks}

        def fetch(provider, force_refresh=False):
            if force_refresh:
                refreshed.append(provider.id)
            return keys[provider.id]

        monkeypatch.setattr(auth_module, "_get_provider_jwks", fetch)

        # A token for Entra whose signature does not verify — the rotation-shaped failure, and
        # the one authlib reports as BadSignatureError, which is what the retry is keyed on.
        header, payload, _ = entra.mint().split(".")
        unverifiable = f"{header}.{payload}.{b64(b'not-the-signature').decode()}"

        with pytest.raises(Exception):
            auth_module.validate_token(unverifiable)

        assert refreshed == ["entra"], f"expected only the failing provider to be refetched, got {refreshed}"

    def test_each_provider_caches_separately(self, entra, kubernetes, monkeypatch):
        """The cache is keyed by provider id, so one entry cannot evict another's keys."""
        auth_module._provider_jwks_cache.clear()
        fetched = []

        def fake_get(url, timeout=None, verify=None):
            fetched.append(url)

            class Response:
                @staticmethod
                def json():
                    if url.endswith("/.well-known/openid-configuration"):
                        return {"jwks_uri": url.replace("/.well-known/openid-configuration", "/keys")}
                    return entra.jwks if "entra" in url else kubernetes.jwks

            return Response()

        monkeypatch.setattr(auth_module.requests, "get", fake_get)

        entra_provider = provider_for(entra, provider_id="entra", discovery_url="https://entra.invalid/.well-known/openid-configuration")
        k8s_provider = provider_for(kubernetes, provider_id="k8s", discovery_url="https://k8s.invalid/.well-known/openid-configuration")

        assert auth_module._get_provider_jwks(entra_provider) == entra.jwks
        assert auth_module._get_provider_jwks(k8s_provider) == kubernetes.jwks
        # Both cached: neither displaced the other.
        assert auth_module._get_provider_jwks(entra_provider) == entra.jwks
        assert auth_module._get_provider_jwks(k8s_provider) == kubernetes.jwks

        assert len(fetched) == 4, f"expected one discovery + one keys fetch per provider, got {fetched}"

    def test_a_forced_refresh_evicts_only_its_own_entry(self, entra, kubernetes, monkeypatch):
        auth_module._provider_jwks_cache.clear()
        auth_module._provider_jwks_cache["entra"] = entra.jwks
        auth_module._provider_jwks_cache["k8s"] = kubernetes.jwks

        monkeypatch.setattr(auth_module.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("k8s keys were refetched")))
        entra_provider = provider_for(entra, provider_id="entra", discovery_url="https://entra.invalid/.well-known/openid-configuration")

        with pytest.raises(Exception):
            auth_module._get_provider_jwks(entra_provider, force_refresh=True)

        assert auth_module._provider_jwks_cache.get("k8s") == kubernetes.jwks, "the other provider's keys were evicted"


class TestTheSuiteAppliesToEveryProvider:
    """``TokenAdversarySuite`` run once per configured provider — the acceptance criterion that a
    new provider inherits the cases rather than re-implementing them."""

    class TestTheHumanLoginProvider(TokenAdversarySuite):
        @pytest.fixture
        def trusted(self, entra):
            return entra

        @pytest.fixture
        def foreign(self, stranger):
            return stranger

        @pytest.fixture
        def verify(self, both):
            return both

    class TestTheAutomationProvider(TokenAdversarySuite):
        @pytest.fixture
        def trusted(self, kubernetes):
            return kubernetes

        @pytest.fixture
        def foreign(self, stranger):
            return stranger

        @pytest.fixture
        def verify(self, both):
            return both


class TestTheSingleProviderDeploymentFetchesKeysTheSameWay:
    """The path a real single-provider deployment takes, which the fixtures elsewhere skip.

    Those fixtures build a provider with no ``discovery_url``, so they exercise the inherited
    ``_get_oidc_jwks`` branch. A deployment that sets ``OIDC_DISCOVERY_URL`` — every real one —
    gets a synthesised provider that *carries* it, and so takes the per-provider branch instead.
    Both now run one implementation; these cases hold that, so a fix to key fetching cannot
    apply to the branch under test and miss the branch in production.
    """

    def test_the_synthesised_provider_carries_the_configured_discovery_url(self):
        """The fact the coverage gap turned on."""
        from types import SimpleNamespace

        from mlflow_oidc_auth.provider_registry import build_provider_registry

        class Manager:
            @staticmethod
            def get(key, default=None):
                return default

        app_config = SimpleNamespace(
            OIDC_PROVIDER_DISPLAY_NAME="Login with OIDC",
            OIDC_AUDIENCE=None,
            OIDC_ISSUER=None,
            OIDC_DISCOVERY_URL="https://idp.example.com/.well-known/openid-configuration",
            OIDC_CLIENT_ID="client",
        )

        provider = build_provider_registry(Manager(), app_config).providers[0]

        assert provider.discovery_url == "https://idp.example.com/.well-known/openid-configuration"

    def test_both_branches_run_the_same_fetch(self, entra, monkeypatch):
        """Whichever cache the result lands in, the work is done by ``_load_jwks``."""
        calls = []
        monkeypatch.setattr(auth_module, "_load_jwks", lambda url, **kwargs: calls.append((url, kwargs["cache_key"])) or entra.jwks)
        monkeypatch.setattr(auth_module.config, "OIDC_DISCOVERY_URL", "https://flat.example.com/.well-known/openid-configuration")

        inherited = provider_for(entra, provider_id="default")
        own_source = provider_for(entra, provider_id="default", discovery_url="https://own.example.com/.well-known/openid-configuration")

        assert auth_module._get_provider_jwks(inherited) == entra.jwks
        assert auth_module._get_provider_jwks(own_source) == entra.jwks

        assert [url for url, _ in calls] == [
            "https://flat.example.com/.well-known/openid-configuration",
            "https://own.example.com/.well-known/openid-configuration",
        ]
        assert calls[0][1] == auth_module._JWKS_CACHE_KEY
        assert calls[1][1] == ("default", "https://own.example.com/.well-known/openid-configuration")

    def test_a_provider_with_its_own_source_still_refreshes_only_itself(self, entra, kubernetes, monkeypatch):
        auth_module._provider_jwks_cache.clear()
        auth_module._provider_jwks_cache[("k8s", "https://k8s.invalid/.well-known/openid-configuration")] = kubernetes.jwks

        fetched = []

        def fake_get(url, timeout=None, verify=None):
            fetched.append(url)

            class Response:
                @staticmethod
                def json():
                    return {"jwks_uri": "https://entra.invalid/keys"} if "openid-configuration" in url else entra.jwks

            return Response()

        monkeypatch.setattr(auth_module.requests, "get", fake_get)
        entra_provider = provider_for(entra, provider_id="entra", discovery_url="https://entra.invalid/.well-known/openid-configuration")

        auth_module._get_provider_jwks(entra_provider, force_refresh=True)

        assert auth_module._provider_jwks_cache.get(("k8s", "https://k8s.invalid/.well-known/openid-configuration")) == kubernetes.jwks
