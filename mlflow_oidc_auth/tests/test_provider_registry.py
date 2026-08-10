"""Identity provider registry parsing, back-compat and validation (issue #308).

The registry is configuration only — nothing authenticates against it yet — so what these tests
defend is that it describes today's deployment faithfully, and that a misconfigured entry is
dropped rather than half-applied.

Every rejection below is security-relevant, and each has its own test: an entry that survives
one of these checks by accident is a provider someone can authenticate through under a policy
the operator did not write.
"""

import json
from types import SimpleNamespace

import pytest

from mlflow_oidc_auth.provider_registry import (
    DEFAULT_ALGORITHMS,
    DEFAULT_PROVIDER_ID,
    ProviderConfig,
    build_provider_registry,
)


class FakeConfigManager:
    """A stand-in for the ``config_providers`` chain, returning fixed values."""

    def __init__(self, **values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


def legacy_app_config(**overrides) -> SimpleNamespace:
    """The flat ``OIDC_*`` attributes the synthesiser reads."""
    values = {
        "OIDC_PROVIDER_DISPLAY_NAME": "Login with OIDC",
        "OIDC_AUDIENCE": None,
        "OIDC_ISSUER": None,
        "OIDC_DISCOVERY_URL": "https://idp.example.com/.well-known/openid-configuration",
        "OIDC_CLIENT_ID": "client-123",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def valid_entry(**overrides) -> dict:
    """A minimal entry that passes every check, for tests that break one thing at a time."""
    entry = {"id": "okta", "type": "oidc", "audience": "mlflow"}
    entry.update(overrides)
    return entry


def build(entries=None, app_config=None, **manager_values):
    """Build a registry from ``entries`` as inline JSON."""
    if entries is not None:
        manager_values.setdefault("AUTH_PROVIDERS", json.dumps(entries))
    return build_provider_registry(FakeConfigManager(**manager_values), app_config or legacy_app_config())


class TestLegacyBackCompat:
    """With no registry configured, behaviour must be exactly what it is today."""

    def test_no_registry_synthesises_a_single_default_provider(self):
        result = build()

        assert result.source == "legacy"
        assert [p.id for p in result.providers] == [DEFAULT_PROVIDER_ID]
        assert result.errors == []

    def test_the_default_provider_carries_todays_policy(self):
        """jit / every_login / authoritative — the behaviour the plugin already has."""
        provider = build().providers[0]

        assert provider.provisioning == "jit"
        assert provider.group_sync == "every_login"
        assert provider.group_sync_mode == "authoritative"
        assert provider.admin_source == "claims"
        assert provider.identity_binding == "subject"
        assert provider.allowed_algorithms == DEFAULT_ALGORITHMS

    def test_the_default_provider_carries_the_flat_oidc_values(self):
        provider = build(app_config=legacy_app_config(OIDC_AUDIENCE="aud-1", OIDC_ISSUER="https://idp.example.com")).providers[0]

        assert provider.audience == "aud-1"
        assert provider.issuer == "https://idp.example.com"
        assert provider.discovery_url == "https://idp.example.com/.well-known/openid-configuration"
        assert provider.client_id == "client-123"

    def test_a_deployment_without_an_audience_still_gets_its_provider(self):
        """The asymmetry that keeps back-compat non-negotiable.

        ``audience`` is required of an explicitly configured entry, but ``OIDC_AUDIENCE`` is
        optional today and most installations leave it unset. Holding the synthesised provider
        to the stricter rule would hand those deployments an empty registry — exactly the break
        this synthesis exists to prevent. New config is held higher; existing config is
        described faithfully, including where it is weak.
        """
        result = build(app_config=legacy_app_config(OIDC_AUDIENCE=None))

        assert [p.id for p in result.providers] == [DEFAULT_PROVIDER_ID]
        assert result.providers[0].audience is None
        assert result.errors == []


class TestParsingSources:
    def test_registry_parses_from_the_env_variable(self):
        result = build([valid_entry()])

        assert result.source == "env"
        assert [p.id for p in result.providers] == ["okta"]

    def test_registry_parses_from_a_file(self, tmp_path):
        path = tmp_path / "providers.json"
        path.write_text(json.dumps([valid_entry(id="from-file")]))

        result = build_provider_registry(FakeConfigManager(AUTH_PROVIDERS_FILE=str(path)), legacy_app_config())

        assert result.source == "file"
        assert [p.id for p in result.providers] == ["from-file"]

    def test_the_env_variable_wins_over_the_file(self, tmp_path):
        path = tmp_path / "providers.json"
        path.write_text(json.dumps([valid_entry(id="from-file")]))

        result = build([valid_entry(id="from-env")], AUTH_PROVIDERS_FILE=str(path))

        assert [p.id for p in result.providers] == ["from-env"]

    def test_a_providers_key_wrapper_is_accepted(self):
        """``{"providers": [...]}`` is what most people write first."""
        result = build({"providers": [valid_entry()]})

        assert [p.id for p in result.providers] == ["okta"]

    def test_malformed_json_falls_back_to_legacy_rather_than_emptying_the_registry(self):
        """An operator typo must not lock a working deployment out."""
        result = build(AUTH_PROVIDERS="{not json")

        assert [p.id for p in result.providers] == [DEFAULT_PROVIDER_ID]
        assert any("JSON" in e for e in result.errors)

    def test_an_unreadable_file_falls_back_to_legacy(self, tmp_path):
        result = build_provider_registry(FakeConfigManager(AUTH_PROVIDERS_FILE=str(tmp_path / "missing.json")), legacy_app_config())

        assert [p.id for p in result.providers] == [DEFAULT_PROVIDER_ID]
        assert any("could not be read" in e for e in result.errors)


class TestValidationRejections:
    """One test per rule the issue requires. Each asserts the entry is *gone*, not merely
    flagged — a rejected provider that stays in the registry is a provider people can use."""

    def _assert_rejected(self, result, fragment: str):
        assert result.providers == [], "an invalid entry must not survive into the registry"
        assert any(fragment in e for e in result.errors), f"expected an error mentioning {fragment!r}, got {result.errors}"

    def test_duplicate_ids_reject_every_copy(self):
        """Not just the second one: with two entries claiming an id there is no way to tell
        which policy was meant, and guessing would silently apply the wrong one."""
        result = build([valid_entry(id="dup", audience="a"), valid_entry(id="dup", audience="b")])

        self._assert_rejected(result, "duplicate id")

    def test_admin_source_scim_is_rejected(self):
        """Whoever controls group naming in the directory would otherwise grant themselves
        admin — the Grafana privilege-escalation shape."""
        result = build([valid_entry(admin_source="scim")])

        self._assert_rejected(result, "admin_source 'scim' is not allowed")

    def test_admin_source_claims_and_none_are_allowed(self):
        for source in ("claims", "none"):
            result = build([valid_entry(admin_source=source)])
            assert [p.admin_source for p in result.providers] == [source]

    def test_hmac_algorithm_with_a_jwks_source_is_rejected(self):
        """Algorithm confusion: a public verification key replayed as an HMAC secret lets any
        caller mint a token the server accepts."""
        result = build([valid_entry(allowed_algorithms=["RS256", "HS256"], issuer="https://idp.example.com")])

        self._assert_rejected(result, "algorithm-confusion")

    def test_hmac_algorithm_with_a_discovery_url_is_rejected(self):
        result = build([valid_entry(allowed_algorithms=["HS512"], discovery_url="https://idp.example.com/.well-known/openid-configuration")])

        self._assert_rejected(result, "algorithm-confusion")

    def test_a_missing_audience_is_rejected(self):
        """A token validated with no audience check is valid for every relying party of that
        issuer."""
        entry = valid_entry()
        del entry["audience"]

        self._assert_rejected(build([entry]), "'audience' is required")

    def test_a_blank_audience_is_rejected(self):
        self._assert_rejected(build([valid_entry(audience="   ")]), "'audience' is required")

    def test_email_binding_without_allowed_domains_is_rejected(self):
        """Otherwise anyone who can prove any address at any domain can claim a local user."""
        result = build([valid_entry(identity_binding="email")])

        self._assert_rejected(result, "allowed_email_domains")

    def test_email_binding_with_allowed_domains_is_accepted(self):
        result = build([valid_entry(identity_binding="email", allowed_email_domains=["example.com"])])

        assert [p.allowed_email_domains for p in result.providers] == [("example.com",)]

    def test_a_saml_provider_without_the_extra_is_rejected(self):
        result = build([valid_entry(type="saml")])

        self._assert_rejected(result, "[saml] extra")

    def test_an_unknown_id_is_rejected(self):
        entry = valid_entry()
        del entry["id"]

        self._assert_rejected(build([entry]), "'id' is required")

    @pytest.mark.parametrize(
        "field,value,fragment",
        [
            ("type", "ldap", "unknown type"),
            ("provisioning", "magic", "unknown provisioning"),
            ("group_sync", "sometimes", "unknown group_sync"),
            ("group_sync_mode", "merge", "unknown group_sync_mode"),
            ("admin_source", "whoever", "unknown admin_source"),
            ("identity_binding", "phone", "unknown identity_binding"),
        ],
    )
    def test_unknown_enum_values_are_rejected(self, field, value, fragment):
        self._assert_rejected(build([valid_entry(**{field: value})]), fragment)


class TestPartialFailureIsolation:
    def test_a_valid_provider_survives_alongside_an_invalid_one(self):
        """One bad entry must not take the whole registry down with it."""
        result = build([valid_entry(id="good"), valid_entry(id="bad", admin_source="scim")])

        assert [p.id for p in result.providers] == ["good"]
        assert any("admin_source 'scim'" in e for e in result.errors)

    def test_an_entry_is_never_partially_accepted(self):
        """Several problems at once still yields no provider, not a half-configured one."""
        entry = {"id": "broken", "type": "ldap", "provisioning": "magic", "identity_binding": "email"}

        result = build([entry])

        assert result.providers == []
        assert len(result.errors) >= 3

    def test_a_non_object_entry_is_reported_and_skipped(self):
        result = build(["not-an-object", valid_entry(id="ok")])

        assert [p.id for p in result.providers] == ["ok"]
        assert any("is not an object" in e for e in result.errors)


class TestProviderConfigShape:
    def test_providers_are_immutable(self):
        """The registry is read at startup and shared; a consumer mutating a provider in place
        would change authentication policy for every later request."""
        provider = build([valid_entry()]).providers[0]

        with pytest.raises(Exception):
            provider.admin_source = "none"  # type: ignore[misc]

    def test_lookup_by_id(self):
        result = build([valid_entry(id="a"), valid_entry(id="b")])

        assert result.by_id("b").id == "b"
        assert result.by_id("missing") is None

    def test_display_name_defaults_to_the_id(self):
        assert build([valid_entry(id="okta")]).providers[0].display_name == "okta"

    def test_uses_jwks_is_true_only_with_a_key_source(self):
        assert ProviderConfig(id="x", audience="a", issuer="https://i").uses_jwks() is True
        assert ProviderConfig(id="x", audience="a").uses_jwks() is False


class TestAppConfigIntegration:
    def test_app_config_exposes_a_registry(self):
        """The one consumer that exists today: AppConfig builds it at startup."""
        from mlflow_oidc_auth.config import config

        assert [p.id for p in config.AUTH_PROVIDERS.providers] == [DEFAULT_PROVIDER_ID]

    def test_invalid_entries_are_logged_not_raised(self, caplog):
        """Raising would take down tooling that never touches login — Alembic's migration
        environment imports this same singleton."""
        from mlflow_oidc_auth.config import AppConfig

        with caplog.at_level("WARNING"):
            app_config = AppConfig()
            app_config.AUTH_PROVIDERS.errors = ["provider 'x': something is wrong"]
            app_config._warn_if_provider_registry_invalid()

        assert any("something is wrong" in r.message for r in caplog.records)
