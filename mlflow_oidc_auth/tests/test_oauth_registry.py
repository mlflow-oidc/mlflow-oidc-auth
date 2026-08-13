"""One OAuth client per provider (issue #315).

There used to be a single global client hardcoded as ``"oidc"`` behind a one-shot registration
flag, which cannot express more than one identity provider — and, more subtly, cannot express
"provider A registered, provider B failed", which is the state that matters once there are two.

What these tests defend:

* the legacy deployment is untouched — ``oauth.oidc`` still resolves, because ``default`` keeps
  that authlib name;
* providers register independently, so one bad entry does not disable login for everyone;
* secrets come from the config chain, never from the registry JSON.
"""

from contextlib import ExitStack
from unittest.mock import patch

import pytest

import mlflow_oidc_auth.oauth as oauth_mod
from mlflow_oidc_auth.provider_registry import DEFAULT_PROVIDER_ID, ProviderConfig, RegistryLoadResult


@pytest.fixture(autouse=True)
def clean_registry():
    """Every test starts with an empty authlib registry and no registration state."""
    oauth_mod.reset_oauth()
    yield
    oauth_mod.reset_oauth()


def provider(provider_id: str, **kwargs) -> ProviderConfig:
    defaults = {
        "audience": "mlflow",
        "client_id": f"{provider_id}-client",
        "discovery_url": f"https://{provider_id}.example.com/.well-known/openid-configuration",
    }
    defaults.update(kwargs)
    return ProviderConfig(id=provider_id, **defaults)


def with_registry(*providers):
    """Patch the config registry with the given providers."""
    return patch.object(oauth_mod.config, "AUTH_PROVIDERS", RegistryLoadResult(providers=list(providers), source="env"))


def with_secrets(**secrets):
    """Patch the config chain so per-provider secrets resolve."""
    return patch.object(oauth_mod.config_manager, "get", lambda key, default=None: secrets.get(key, default))


class TestLegacyDeploymentIsUnchanged:
    def test_the_default_provider_registers_under_the_name_oidc(self):
        """Every existing call site reaches the client as ``oauth.oidc``; renaming it to
        ``default`` would be a breaking change for no benefit."""
        assert oauth_mod.client_name(DEFAULT_PROVIDER_ID) == "oidc"

    def test_another_provider_registers_under_its_own_id(self):
        assert oauth_mod.client_name("okta") == "okta"

    def test_flat_config_alone_still_registers(self):
        """No registry configured, just the flat OIDC_* variables — exactly today's deployment.

        ``source="legacy"`` is what "no registry configured" looks like; an *empty* registry with
        ``source="env"`` means the operator wrote one and left it empty, which is a different
        statement and is covered by TestAnExplicitRegistryIsNotOverridden.
        """
        with (
            patch.object(oauth_mod.config, "AUTH_PROVIDERS", RegistryLoadResult(providers=[], source="legacy")),
            patch.object(oauth_mod.config, "OIDC_CLIENT_ID", "id"),
            patch.object(oauth_mod.config, "OIDC_CLIENT_SECRET", "secret"),
            patch.object(oauth_mod.config, "OIDC_DISCOVERY_URL", "https://idp.example.com/.well-known/openid-configuration"),
        ):
            assert oauth_mod.ensure_oidc_client_registered() is True

        assert oauth_mod.get_client() is not None
        assert getattr(oauth_mod.oauth, "oidc", None) is not None

    def test_registration_is_idempotent(self):
        with (
            with_registry(provider(DEFAULT_PROVIDER_ID)),
            with_secrets(),
            patch.object(oauth_mod.config, "OIDC_CLIENT_SECRET", "secret"),
            patch.object(oauth_mod.oauth, "register") as register,
        ):
            assert oauth_mod.ensure_client_registered(DEFAULT_PROVIDER_ID) is True
            assert oauth_mod.ensure_client_registered(DEFAULT_PROVIDER_ID) is True

        assert register.call_count == 1, "a second call must not re-register"


class TestMultipleProviders:
    def test_each_provider_registers_independently(self):
        with (
            with_registry(provider("okta"), provider("entra")),
            with_secrets(OIDC_CLIENT_SECRET_OKTA="s1", OIDC_CLIENT_SECRET_ENTRA="s2"),
        ):
            results = oauth_mod.ensure_all_clients_registered()

        assert results == {"okta": True, "entra": True}
        assert oauth_mod.get_client("okta") is not None
        assert oauth_mod.get_client("entra") is not None

    def test_one_failing_provider_does_not_break_the_others(self):
        """The acceptance criterion. With several providers, one unreachable discovery document
        must not disable login for everyone."""
        real_register = oauth_mod.oauth.register

        def register(name, **kwargs):
            if name == "broken":
                raise RuntimeError("discovery document unreachable")
            return real_register(name, **kwargs)

        with (
            with_registry(provider("okta"), provider("broken"), provider("entra")),
            with_secrets(OIDC_CLIENT_SECRET_OKTA="s1", OIDC_CLIENT_SECRET_BROKEN="s2", OIDC_CLIENT_SECRET_ENTRA="s3"),
            patch.object(oauth_mod.oauth, "register", side_effect=register),
        ):
            results = oauth_mod.ensure_all_clients_registered()

        assert results == {"okta": True, "broken": False, "entra": True}

    def test_a_provider_with_no_secret_is_skipped_when_pkce_is_off(self):
        with (
            with_registry(provider("okta"), provider("nosecret")),
            with_secrets(OIDC_CLIENT_SECRET_OKTA="s1"),
            patch.object(oauth_mod.config, "OIDC_CODE_CHALLENGE", None),
        ):
            results = oauth_mod.ensure_all_clients_registered()

        assert results == {"okta": True, "nosecret": False}
        assert oauth_mod.get_client("nosecret") is None

    def test_a_provider_with_no_secret_registers_as_a_public_client(self):
        """A secretless provider is a public client, not a broken one, once PKCE is on (#300).

        PKCE is the default since #312, so this — not the skip above — is what an operator who
        omits a client secret actually gets.
        """
        with (
            with_registry(provider("okta"), provider("nosecret")),
            with_secrets(OIDC_CLIENT_SECRET_OKTA="s1"),
            patch.object(oauth_mod.config, "OIDC_CODE_CHALLENGE", "S256"),
        ):
            results = oauth_mod.ensure_all_clients_registered()

        assert results == {"okta": True, "nosecret": True}
        assert oauth_mod.get_client("nosecret") is not None

    def test_non_oidc_providers_are_not_registered(self):
        """SAML has no authlib OAuth client, and a Kubernetes issuer is verified from its JWKS
        rather than driven through an authorization flow."""
        with (
            with_registry(provider("okta"), provider("cluster", type="k8s", interactive=False)),
            with_secrets(OIDC_CLIENT_SECRET_OKTA="s1", OIDC_CLIENT_SECRET_CLUSTER="s2"),
        ):
            results = oauth_mod.ensure_all_clients_registered()

        assert results == {"okta": True}

    def test_an_unknown_provider_id_is_false_not_an_error(self):
        with with_registry(provider("okta")), with_secrets(OIDC_CLIENT_SECRET_OKTA="s1"):
            assert oauth_mod.ensure_client_registered("nope") is False

    def test_registration_state_is_per_provider(self):
        """A single global flag could not express "A registered, B failed" — which is the only
        state that matters once there is more than one provider."""
        with (
            with_registry(provider("okta"), provider("nosecret")),
            with_secrets(OIDC_CLIENT_SECRET_OKTA="s1"),
            # PKCE off, so "nosecret" is genuinely unregistrable rather than a public client.
            patch.object(oauth_mod.config, "OIDC_CODE_CHALLENGE", None),
        ):
            oauth_mod.ensure_all_clients_registered()

            assert oauth_mod.ensure_client_registered("okta") is True
            assert oauth_mod.ensure_client_registered("nosecret") is False


class TestSecretsComeFromTheConfigChain:
    """``ProviderConfig`` has no secret field on purpose: the registry is declarative config that
    may live in a JSON file or an env var, and secrets belong in the secrets manager."""

    @pytest.mark.parametrize(
        "provider_id,expected_key",
        [("okta", "OIDC_CLIENT_SECRET_OKTA"), ("okta-eu", "OIDC_CLIENT_SECRET_OKTA_EU"), ("entra.prod", "OIDC_CLIENT_SECRET_ENTRA_PROD")],
    )
    def test_the_secret_key_is_derived_from_the_provider_id(self, provider_id, expected_key):
        """A provider id that is legal in JSON has to become a legal environment variable name."""
        assert oauth_mod._secret_env_key(provider_id) == expected_key

    def test_the_default_provider_uses_the_flat_secret(self):
        with patch.object(oauth_mod.config, "OIDC_CLIENT_SECRET", "flat-secret"):
            assert oauth_mod._client_secret_for(DEFAULT_PROVIDER_ID) == "flat-secret"

    def test_the_secret_reaches_the_registered_client(self):
        with (
            with_registry(provider("okta")),
            with_secrets(OIDC_CLIENT_SECRET_OKTA="from-secrets-manager"),
            patch.object(oauth_mod.oauth, "register") as register,
        ):
            oauth_mod.ensure_client_registered("okta")

        assert register.call_args.kwargs["client_secret"] == "from-secrets-manager"

    def test_the_registry_never_supplies_the_secret(self):
        """Guards the design decision rather than an outcome: if someone later adds a
        ``client_secret`` field to ProviderConfig, this is where it should be noticed."""
        assert not hasattr(provider("okta"), "client_secret")


class TestAnExplicitRegistryIsNotOverridden:
    """The registry is the operator's statement of which providers exist.

    Leftover ``OIDC_*`` variables are the normal state after migrating to a registry, and must
    not resurrect a browser login path the operator removed. Raised in review of #347.
    """

    def _flat_config(self, stack: ExitStack) -> None:
        """Leftover flat variables, as they sit in the environment after a registry migration."""
        stack.enter_context(patch.object(oauth_mod.config, "OIDC_CLIENT_ID", "legacy-id"))
        stack.enter_context(patch.object(oauth_mod.config, "OIDC_CLIENT_SECRET", "legacy-secret"))
        stack.enter_context(patch.object(oauth_mod.config, "OIDC_DISCOVERY_URL", "https://old-idp.example.com/.well-known/openid-configuration"))

    def test_a_registry_with_no_oidc_provider_does_not_get_the_legacy_client(self):
        """Machine-only deployment: a k8s provider and nothing else. The old flat variables are
        still in the environment, and must stay inert."""
        k8s = ProviderConfig(id="cluster", type="k8s", audience="a", interactive=False)
        with ExitStack() as stack:
            stack.enter_context(with_registry(k8s))
            self._flat_config(stack)

            results = oauth_mod.ensure_all_clients_registered()

            assert results == {}
            assert oauth_mod.get_client() is None
            assert getattr(oauth_mod.oauth, "oidc", None) is None

    def test_the_same_holds_for_a_direct_registration_call(self):
        """``is_oidc_configured()`` reaches this path without going through
        ``ensure_all_clients_registered``, so gating only the latter would leave the hole open."""
        k8s = ProviderConfig(id="cluster", type="k8s", audience="a", interactive=False)
        with ExitStack() as stack:
            stack.enter_context(with_registry(k8s))
            self._flat_config(stack)

            assert oauth_mod.ensure_oidc_client_registered() is False
            assert oauth_mod.is_oidc_configured() is False

    def test_an_explicitly_empty_registry_does_not_get_the_legacy_client(self):
        with ExitStack() as stack:
            stack.enter_context(with_registry())
            self._flat_config(stack)

            assert oauth_mod.ensure_all_clients_registered() == {}

    def test_a_legacy_deployment_still_gets_it(self):
        """source='legacy' means no registry was configured at all — the case the fallback is
        actually for."""
        registry = RegistryLoadResult(providers=[], source="legacy")
        with ExitStack() as stack:
            stack.enter_context(patch.object(oauth_mod.config, "AUTH_PROVIDERS", registry))
            self._flat_config(stack)

            assert oauth_mod.ensure_all_clients_registered() == {DEFAULT_PROVIDER_ID: True}


class TestCollidingSecretKeys:
    """Two legal ids resolving to one secret key would cross-wire credentials.

    The failure would surface as an opaque ``invalid_client`` from the IdP rather than as a
    configuration error. Raised in review of #347.
    """

    def test_colliding_providers_are_both_refused(self):
        """Refused rather than resolved: with no way to tell which provider the operator meant,
        registering either one risks giving it the other's secret."""
        with (
            with_registry(provider("okta-eu"), provider("okta_eu")),
            with_secrets(OIDC_CLIENT_SECRET_OKTA_EU="shared"),
        ):
            results = oauth_mod.ensure_all_clients_registered()

        assert results == {"okta-eu": False, "okta_eu": False}
        assert oauth_mod.get_client("okta-eu") is None
        assert oauth_mod.get_client("okta_eu") is None

    def test_a_non_colliding_provider_alongside_them_still_registers(self):
        """One bad pair must not disable an unrelated provider."""
        with (
            with_registry(provider("okta-eu"), provider("okta_eu"), provider("entra")),
            with_secrets(OIDC_CLIENT_SECRET_OKTA_EU="shared", OIDC_CLIENT_SECRET_ENTRA="s"),
        ):
            results = oauth_mod.ensure_all_clients_registered()

        assert results == {"okta-eu": False, "okta_eu": False, "entra": True}

    @pytest.mark.parametrize("second_id", ["okta_eu", "okta.eu", "okta--eu"])
    def test_punctuation_variants_all_collide(self, second_id):
        with with_registry(provider("okta-eu"), provider(second_id)), with_secrets():
            assert set(oauth_mod._colliding_secret_keys()) == {"OIDC_CLIENT_SECRET_OKTA_EU"}

    def test_distinct_ids_do_not_collide(self):
        with with_registry(provider("okta"), provider("entra")), with_secrets():
            assert oauth_mod._colliding_secret_keys() == {}


class TestReset:
    def test_reset_clears_clients_and_state(self):
        with (
            with_registry(provider("okta")),
            with_secrets(OIDC_CLIENT_SECRET_OKTA="s1"),
        ):
            oauth_mod.ensure_client_registered("okta")
            assert oauth_mod.get_client("okta") is not None

            oauth_mod.reset_oauth()

            assert oauth_mod.get_client("okta") is None
            assert oauth_mod._registered == {}
