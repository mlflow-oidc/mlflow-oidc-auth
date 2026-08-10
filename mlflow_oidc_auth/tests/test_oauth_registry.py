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
        """No registry entry at all, just the flat OIDC_* variables — exactly today's
        deployment."""
        with (
            with_registry(),
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

    def test_a_provider_with_no_secret_is_skipped_not_raised(self):
        with (
            with_registry(provider("okta"), provider("nosecret")),
            with_secrets(OIDC_CLIENT_SECRET_OKTA="s1"),
        ):
            results = oauth_mod.ensure_all_clients_registered()

        assert results == {"okta": True, "nosecret": False}
        assert oauth_mod.get_client("nosecret") is None

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
