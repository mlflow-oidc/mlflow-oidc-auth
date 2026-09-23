"""Identity provider registry parsing, back-compat and validation (issue #308).

The registry is configuration only — nothing authenticates against it yet — so what these tests
defend is that it describes today's deployment faithfully, and that a misconfigured entry is
dropped rather than half-applied.

Every rejection below is security-relevant, and each has its own test: an entry that survives
one of these checks by accident is a provider someone can authenticate through under a policy
the operator did not write.
"""

import functools
import importlib
import json
from types import SimpleNamespace

import pytest

from mlflow_oidc_auth.provider_registry import (
    ASYMMETRIC_ALGORITHMS,
    DEFAULT_ALGORITHMS,
    DEFAULT_PROVIDER_ID,
    ProviderConfig,
    build_provider_registry,
)

# Force the AppConfig singleton into existence now, from the real environment. ``config.py``
# builds it at module import, so a test that imports it *while* holding a patched
# AUTH_PROVIDERS would bake that patched value in for every test that runs afterwards — the
# kind of order-dependent pollution these tests exist to catch elsewhere.
importlib.import_module("mlflow_oidc_auth.config")


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
    """A minimal entry that passes every check, for tests that break one thing at a time.

    ``issuer`` and ``discovery_url`` are part of the minimum for a token-validating provider
    since #313: without the first nothing pins ``iss``, and without the second the provider
    shares the deployment-wide key cache with every other provider that omits one.
    """
    provider_id = overrides.get("id", "okta")
    entry = {
        "id": provider_id,
        "type": "oidc",
        "audience": "mlflow",
        # Derived from the id: two entries in one registry must not accidentally share an
        # issuer, which is now rejected — a token can only be validated under one policy.
        "issuer": f"https://{provider_id}.example.com",
        "discovery_url": f"https://{provider_id}.example.com/.well-known/openid-configuration",
    }
    entry.update(overrides)
    if entry.get("type") == "k8s":
        # A cluster provider carries two more requirements (#314): somewhere to get keys, and a
        # namespace allowlist, since a service-account token has no groups claim to gate on.
        entry.setdefault("namespace_allowlist", ["team-a"])
    return entry


@functools.lru_cache(maxsize=None)
def _test_keypair(common_name: str):
    """A throwaway RSA key and self-signed certificate, generated per test run and never committed."""
    from datetime import datetime, timedelta, timezone

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    return key_pem, cert.public_bytes(serialization.Encoding.PEM).decode()


def _cert_body(pem: str) -> str:
    return "".join(line for line in pem.splitlines() if "-----" not in line)


def saml_entry(**overrides) -> dict:
    """A minimal SAML entry that passes every check."""
    _, idp_cert = _test_keypair("idp")
    entry = {
        "id": "corp-saml",
        "type": "saml",
        "entity_id": "https://mlflow.example.com/saml/sp",
        "idp_entity_id": "https://idp.example.com/saml",
        "idp_sso_url": "https://idp.example.com/sso",
        "idp_x509_cert": idp_cert,
    }
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

    def test_the_default_provider_accepts_every_asymmetric_algorithm(self):
        """Not ``DEFAULT_ALGORITHMS`` — that is the default for an entry an operator *writes*.

        Before per-provider validation (#313), token validation accepted the whole asymmetric
        set, so a deployment whose IdP signs with ES256 or RS512 is working today. Narrowing the
        synthesised entry to RS256 would lock those deployments out on upgrade without them
        changing any configuration, which is the one thing this entry exists to prevent.
        """
        provider = build().providers[0]

        assert provider.allowed_algorithms == ASYMMETRIC_ALGORITHMS
        assert "RS256" in provider.allowed_algorithms
        assert not any(algorithm.startswith("HS") for algorithm in provider.allowed_algorithms)

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
        caller mint a token the server accepts. See TestAlgorithmValidation for the stronger
        rule this became."""
        result = build([valid_entry(allowed_algorithms=["RS256", "HS256"], issuer="https://idp.example.com")])

        self._assert_rejected(result, "symmetric algorithm")

    def test_hmac_algorithm_with_a_discovery_url_is_rejected(self):
        result = build([valid_entry(allowed_algorithms=["HS512"], discovery_url="https://idp.example.com/.well-known/openid-configuration")])

        self._assert_rejected(result, "symmetric algorithm")

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

    def test_a_saml_provider_without_the_extra_is_rejected(self, monkeypatch):
        """Monkeypatched rather than assumed: the extra is installed in the dev environment."""
        from mlflow_oidc_auth import provider_registry as registry_module

        monkeypatch.setattr(registry_module, "_saml_extra_installed", lambda: False)
        result = build([saml_entry()])

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


class TestAlgorithmValidation:
    """``allowed_algorithms`` decides what a signature check will accept, so an unvalidated
    value here is the most dangerous field in the entry. Raised in review of #344."""

    def _assert_rejected(self, result, fragment: str):
        assert result.providers == []
        assert any(fragment in e for e in result.errors), f"expected an error mentioning {fragment!r}, got {result.errors}"

    @pytest.mark.parametrize("spelling", ["none", "None", "NONE"])
    def test_alg_none_is_rejected_in_any_spelling(self, spelling):
        """``alg: none`` means the token carries no signature at all, so anyone can mint one.

        Worse than the algorithm-confusion case the original check covered, and it passed.
        """
        result = build([valid_entry(issuer="https://idp.example.com", allowed_algorithms=[spelling])])

        self._assert_rejected(result, "algorithm 'none' is never allowed")

    def test_alg_none_alongside_a_valid_algorithm_is_still_rejected(self):
        """The whole entry goes, not just the offending value — a provider that accepts RS256
        *or* nothing accepts nothing."""
        result = build([valid_entry(allowed_algorithms=["RS256", "none"])])

        self._assert_rejected(result, "algorithm 'none' is never allowed")

    @pytest.mark.parametrize("algorithm", ["HS256", "HS384", "HS512", "hs256"])
    def test_hmac_algorithms_are_rejected_even_with_no_key_source_on_the_entry(self, algorithm):
        """Stricter than #308 asked, deliberately.

        Gating on whether the entry named ``issuer``/``discovery_url`` was evadable: omit both
        and the deployment's flat ``OIDC_DISCOVERY_URL`` still supplies a key set, restoring
        the confusion setup. This plugin has no symmetric-key verification path, so an HMAC
        entry cannot work regardless — the only question was whether it failed safely.
        """
        entry = valid_entry(allowed_algorithms=[algorithm])
        entry.pop("issuer", None)
        entry.pop("discovery_url", None)

        self._assert_rejected(build([entry]), "symmetric algorithm")

    def test_unknown_algorithms_are_rejected(self):
        """A typo must become a startup message, not an algorithm a consumer quietly ignores."""
        self._assert_rejected(build([valid_entry(allowed_algorithms=["RS256-ish"])]), "unknown algorithm")

    @pytest.mark.parametrize("written,canonical", [("rs256", "RS256"), ("eddsa", "EdDSA"), ("Es384", "ES384")])
    def test_algorithms_are_stored_canonically(self, written, canonical):
        """A consumer comparing against ``"RS256"`` must match an entry written ``"rs256"``,
        rather than falling through to its own default."""
        result = build([valid_entry(allowed_algorithms=[written])])

        assert result.providers[0].allowed_algorithms == (canonical,)

    def test_supported_asymmetric_algorithms_are_accepted(self):
        result = build([valid_entry(allowed_algorithms=["RS256", "PS512", "ES256", "EdDSA"])])

        assert result.providers[0].allowed_algorithms == ("RS256", "PS512", "ES256", "EdDSA")

    def test_an_absent_list_defaults_to_rs256(self):
        entry = valid_entry()
        entry.pop("allowed_algorithms", None)

        assert build([entry]).providers[0].allowed_algorithms == DEFAULT_ALGORITHMS


class TestAlreadyParsedConfigValues:
    """``config_providers`` are typed ``-> Any`` and the AWS Secrets Manager provider
    ``json.loads`` its whole secret, so a registry stored as nested JSON arrives already
    parsed. Treating that as "not a string, therefore unset" silently discarded it."""

    def test_an_already_parsed_list_is_accepted(self):
        result = build_provider_registry(FakeConfigManager(AUTH_PROVIDERS=[valid_entry(id="from-secret")]), legacy_app_config())

        assert [p.id for p in result.providers] == ["from-secret"]
        assert result.errors == []

    def test_an_already_parsed_dict_wrapper_is_accepted(self):
        result = build_provider_registry(FakeConfigManager(AUTH_PROVIDERS={"providers": [valid_entry(id="wrapped")]}), legacy_app_config())

        assert [p.id for p in result.providers] == ["wrapped"]

    def test_a_value_of_an_unusable_type_is_reported_rather_than_ignored(self):
        """The silent-fallback failure this class exists to prevent: configured, ignored, and
        no diagnostic anywhere."""
        result = build_provider_registry(FakeConfigManager(AUTH_PROVIDERS=42), legacy_app_config())

        assert [p.id for p in result.providers] == [DEFAULT_PROVIDER_ID]
        assert any("expected a JSON array" in e for e in result.errors)

    def test_an_explicitly_empty_list_is_honoured(self):
        """Writing ``[]`` says "no providers"; it is not the same as leaving it unset."""
        result = build_provider_registry(FakeConfigManager(AUTH_PROVIDERS=[]), legacy_app_config())

        assert result.providers == []


class TestInteractiveFlag:
    """Whether a provider belongs on the login page is a separate axis from how its credentials
    are verified.

    A Kubernetes service-account provider verifies tokens exactly as an OIDC one does — JWT
    against the cluster's JWKS — but a projected token is presented directly as a bearer
    credential, so there is no flow a browser can start. Without this flag #317 would render a
    login button for it that cannot complete.
    """

    def test_oidc_providers_are_interactive_by_default(self):
        assert build([valid_entry()]).providers[0].interactive is True

    def test_k8s_providers_are_not_interactive_by_default(self):
        result = build([valid_entry(type="k8s")])

        assert result.providers[0].interactive is False
        assert result.errors == []

    def test_a_k8s_provider_cannot_be_marked_interactive(self):
        """Rejected rather than silently corrected: an operator who asked for a login button
        expects one, and a silently-dropped flag is a worse surprise than a startup message."""
        result = build([valid_entry(type="k8s", interactive=True)])

        assert result.providers == []
        assert any("no browser login flow" in e for e in result.errors)

    def test_an_oidc_provider_may_opt_out_of_the_login_page(self):
        """A machine-to-machine OIDC issuer is a real configuration: tokens are accepted, but
        nobody should be offered a button for it."""
        result = build([valid_entry(interactive=False)])

        assert result.providers[0].interactive is False

    def test_a_non_boolean_interactive_is_rejected(self):
        result = build([valid_entry(interactive="yes")])

        assert result.providers == []
        assert any("'interactive' must be true or false" in e for e in result.errors)

    def test_the_login_page_sees_only_interactive_providers(self):
        result = build([valid_entry(id="okta"), valid_entry(id="cluster", type="k8s")])

        assert [p.id for p in result.providers] == ["okta", "cluster"]
        assert [p.id for p in result.interactive_providers()] == ["okta"]

    def test_the_legacy_provider_is_interactive(self):
        """Today's single provider is a browser login provider, and must stay on the page."""
        assert build().providers[0].interactive is True


class TestFieldTypesAreValidated:
    """JSON can put a list or object in any field, and this module must report that rather than
    raise.

    ``AppConfig`` is instantiated at import time, so an exception here does not degrade login —
    it stops the plugin and Alembic from importing at all. That is the opposite of what dropping
    invalid entries is for, and it is what a bare ``dict.get`` on an unvalidated value did.
    Raised in review of #344.
    """

    @pytest.mark.parametrize("field", ["type", "display_name", "provisioning", "admin_source", "identity_binding", "audience", "issuer", "client_id"])
    @pytest.mark.parametrize("bad_value", [["a"], {"a": 1}, 5])
    def test_a_non_string_scalar_field_is_rejected_without_raising(self, field, bad_value):
        result = build([valid_entry(**{field: bad_value})])

        assert result.providers == []
        assert any(f"'{field}' must be a string" in e for e in result.errors), result.errors

    @pytest.mark.parametrize("field", ["allowed_algorithms", "allowed_email_domains"])
    def test_a_list_field_of_the_wrong_type_is_rejected(self, field):
        result = build([valid_entry(**{field: 5})])

        assert result.providers == []
        assert any("must be a string or a list of strings" in e for e in result.errors)

    def test_the_error_names_the_field_not_our_data_structure(self):
        """``'type' must be a string, got list`` points at the operator's mistake;
        ``unhashable type: 'list'`` points at our dictionary."""
        result = build([valid_entry(type=["oidc"])])

        assert any("'type' must be a string, got list" in e for e in result.errors)

    def test_importing_config_survives_a_malformed_entry(self, monkeypatch):
        """The blast radius that made this more than a validation gap.

        ``config = AppConfig()`` is module-level, so a raise here takes down every importer,
        including Alembic's migration environment — which never reads a provider.
        """
        monkeypatch.setenv("AUTH_PROVIDERS", json.dumps([valid_entry(type=["oidc"])]))
        from mlflow_oidc_auth.config import AppConfig

        app_config = AppConfig()

        assert app_config.AUTH_PROVIDERS.providers == []
        assert any("must be a string" in e for e in app_config.AUTH_PROVIDERS.errors)


class TestAlgorithmsPresentButUnusable:
    """Silently discarding a configured value leaves nothing to debug from — the same failure
    that was fixed one level up for ``AUTH_PROVIDERS`` itself."""

    def test_an_empty_algorithm_list_is_reported(self):
        result = build([valid_entry(allowed_algorithms=[])])

        assert result.providers == []
        assert any("lists no algorithm" in e for e in result.errors)

    def test_a_list_with_a_non_string_member_is_reported(self):
        result = build([valid_entry(allowed_algorithms=["RS256", 5])])

        assert result.providers == []
        assert any("must contain only strings" in e for e in result.errors)

    def test_an_absent_list_is_still_a_silent_default(self):
        """Absent is not the same as unusable: omitting the field is the documented way to
        accept RS256, and must stay quiet."""
        entry = valid_entry()
        entry.pop("allowed_algorithms", None)

        result = build([entry])

        assert result.providers[0].allowed_algorithms == DEFAULT_ALGORITHMS
        assert result.errors == []


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

    def test_has_own_key_source_reports_only_what_the_entry_says(self):
        assert ProviderConfig(id="x", audience="a", issuer="https://i").has_own_key_source() is True
        assert ProviderConfig(id="x", audience="a").has_own_key_source() is False


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


class TestATokenProviderMustPinItsOwnIssuerAndKeys:
    """Both became load-bearing when validation went per-provider (#313).

    Before that, a registry entry was configuration nothing authenticated against, so an
    optional field was harmless. Now the entry *is* the policy a bearer token is judged by.
    """

    def test_an_entry_without_an_issuer_is_rejected(self):
        """Without it nothing pins ``iss``, so every issuer sharing that key set is accepted.

        The realistic shape is a multi-tenant endpoint — Entra's ``common``, a shared Keycloak
        realm, a cluster issuer fronting several namespaces — where one JWKS serves many
        issuers. An attacker with their own tenant on that endpoint holds a token with a valid
        signature and the right audience; only ``iss`` distinguishes it.
        """
        entry = valid_entry()
        entry.pop("issuer")

        result = build([entry])

        assert result.providers == []
        assert any("issuer" in error and "iss" in error for error in result.errors)

    @pytest.mark.parametrize("blank", [None, "", "   "])
    def test_a_blank_issuer_is_rejected(self, blank):
        result = build([valid_entry(issuer=blank)])

        assert result.providers == []

    def test_an_entry_without_a_discovery_url_is_rejected(self):
        """Without one it inherits the deployment-wide key source and its single-entry cache, so
        two such providers evict each other's keys on every rotation refresh."""
        entry = valid_entry()
        entry.pop("discovery_url")

        result = build([entry])

        assert result.providers == []
        assert any("discovery_url" in error for error in result.errors)

    def test_a_saml_provider_needs_neither(self, monkeypatch):
        """The requirement is about validating bearer tokens against a key set. SAML asserts
        identity through a browser POST and never resolves a token here."""
        from mlflow_oidc_auth import provider_registry as registry_module

        monkeypatch.setattr(registry_module, "_saml_extra_installed", lambda: True)
        result = build([saml_entry()])

        assert result.errors == []
        assert [provider.id for provider in result.providers] == ["corp-saml"]

    def test_the_legacy_provider_is_unaffected(self):
        """It is synthesised from flat variables that may legitimately be unset, and it is the
        one provider that must keep working with no configuration change at all."""
        provider = build().providers[0]

        assert provider.id == DEFAULT_PROVIDER_ID
        assert provider.issuer is None


class TestTwoProvidersCannotClaimOneIssuer:
    """Validation takes the first exact ``iss`` match, so a duplicate means the second entry's
    policy — its audience, binding and group rules — is silently never applied."""

    def test_the_later_entry_is_rejected(self):
        first = valid_entry(id="first", issuer="https://shared.example.com")
        second = valid_entry(id="second", issuer="https://shared.example.com")

        result = build([first, second])

        assert [provider.id for provider in result.providers] == ["first"]
        assert any("already claimed" in error for error in result.errors)

    def test_distinct_issuers_both_survive(self):
        result = build([valid_entry(id="first"), valid_entry(id="second")])

        assert [provider.id for provider in result.providers] == ["first", "second"]


class TestAllowTokensWithoutExpiry:
    """``allow_tokens_without_expiry`` switches off the one check that makes a token stop working
    on its own (#356). Off by default everywhere, refused where it could not mean anything, and
    never inferred from a truthy value."""

    def test_it_defaults_to_false_on_an_explicit_entry(self):
        assert build([valid_entry()]).providers[0].allow_tokens_without_expiry is False

    def test_the_legacy_provider_never_allows_it(self):
        """The synthesised provider has no flat variable to opt in with."""
        provider = build(app_config=legacy_app_config(OIDC_AUDIENCE="aud", OIDC_ISSUER="https://idp.example.com")).providers[0]

        assert provider.allow_tokens_without_expiry is False

    def test_the_dataclass_default_is_false(self):
        assert ProviderConfig(id="bare").allow_tokens_without_expiry is False

    @pytest.mark.parametrize("provider_type", ["oidc", "k8s"])
    def test_a_token_provider_may_opt_in(self, provider_type):
        result = build([valid_entry(type=provider_type, allow_tokens_without_expiry=True)])

        assert result.errors == []
        assert result.providers[0].allow_tokens_without_expiry is True

    def test_it_is_refused_on_a_saml_provider(self, monkeypatch):
        """Refused for the field itself, not incidentally for a missing [saml] extra."""
        from mlflow_oidc_auth import provider_registry as registry_module

        monkeypatch.setattr(registry_module, "_saml_extra_installed", lambda: True)
        entry = saml_entry(allow_tokens_without_expiry=True)

        result = build([entry])

        assert result.providers == []
        assert any("'allow_tokens_without_expiry' applies only to a token provider" in error for error in result.errors)

    def test_a_saml_provider_without_it_is_unaffected(self, monkeypatch):
        from mlflow_oidc_auth import provider_registry as registry_module

        monkeypatch.setattr(registry_module, "_saml_extra_installed", lambda: True)

        result = build([saml_entry()])

        assert [provider.id for provider in result.providers] == ["corp-saml"]
        assert result.providers[0].allow_tokens_without_expiry is False

    def test_it_is_refused_on_an_unknown_type(self):
        result = build([valid_entry(type="ldap", allow_tokens_without_expiry=True)])

        assert result.providers == []
        assert any("'allow_tokens_without_expiry' applies only to a token provider" in error for error in result.errors)

    @pytest.mark.parametrize("bad_value", ["true", "false", 1, 0, None, [], {}])
    def test_a_non_boolean_is_refused(self, bad_value):
        """``"false"`` is truthy; reading it as true would disable the check the operator meant to keep."""
        result = build([valid_entry(allow_tokens_without_expiry=bad_value)])

        assert result.providers == []
        assert any("'allow_tokens_without_expiry' must be true or false" in error for error in result.errors)

    def test_opting_in_is_logged_once_per_provider_without_token_content(self, caplog):
        entries = [
            valid_entry(id="first", allow_tokens_without_expiry=True),
            valid_entry(id="second"),
            valid_entry(id="third", allow_tokens_without_expiry=True),
        ]

        with caplog.at_level("WARNING"):
            result = build(entries)

        assert [provider.id for provider in result.providers] == ["first", "second", "third"]
        warnings = [record.getMessage() for record in caplog.records if "allow_tokens_without_expiry" in record.getMessage()]
        assert len(warnings) == 2
        assert any("'first'" in message for message in warnings)
        assert any("'third'" in message for message in warnings)
        assert not any("'second'" in message for message in warnings)


class TestSamlProviders:
    """SAML entries (#328, #329). What makes one safe to accept is that every assertion it can
    produce is checked against something the operator wrote: the IdP's entity id, its
    certificate, and this SP's entity id. Each is required, and each rejection has a test."""

    @pytest.fixture(autouse=True)
    def extra_installed(self, monkeypatch):
        from mlflow_oidc_auth import provider_registry as registry_module

        monkeypatch.setattr(registry_module, "_saml_extra_installed", lambda: True)
        return registry_module

    def _rejected(self, result, fragment):
        assert result.providers == [], "an invalid SAML entry must not survive into the registry"
        assert any(fragment in error for error in result.errors), f"expected {fragment!r} in {result.errors}"

    def test_a_valid_entry_is_accepted_with_safe_defaults(self):
        _, idp_cert = _test_keypair("idp")

        [provider] = build([saml_entry()]).providers

        assert provider.type == "saml"
        assert provider.interactive is True
        assert provider.entity_id == "https://mlflow.example.com/saml/sp"
        assert provider.idp_x509_certs == (_cert_body(idp_cert),)
        assert provider.want_assertions_signed is True
        assert provider.want_response_signed is False
        assert provider.sign_requests is False
        assert provider.clock_skew_seconds == 60
        assert provider.attribute_username == "email"
        assert provider.audience is None and provider.issuer is None

    def test_a_bare_base64_certificate_and_a_rotation_list_are_accepted(self):
        _, first = _test_keypair("idp")
        _, second = _test_keypair("idp-next")

        [provider] = build([saml_entry(idp_x509_cert=[_cert_body(first), second])]).providers

        assert provider.idp_x509_certs == (_cert_body(first), _cert_body(second))

    @pytest.mark.parametrize("field", ["entity_id", "idp_entity_id", "idp_sso_url", "idp_x509_cert"])
    def test_each_required_field_is_enforced(self, field):
        entry = saml_entry()
        entry.pop(field)

        self._rejected(build([entry]), f"'{field}' is required")

    @pytest.mark.parametrize("field", ["idp_sso_url", "idp_slo_url", "idp_metadata_url"])
    def test_idp_urls_must_be_https(self, field):
        self._rejected(build([saml_entry(**{field: "http://idp.example.com/x"})]), f"'{field}' must be an https URL")

    @pytest.mark.parametrize("value", ["not a certificate", "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA", 42, [], ["garbage"]])
    def test_an_unusable_certificate_is_refused(self, value):
        result = build([saml_entry(idp_x509_cert=value)])

        assert result.providers == []
        assert any("idp_x509_cert" in error for error in result.errors)

    @pytest.mark.parametrize(
        "field, value",
        [
            ("audience", "mlflow"),
            ("issuer", "https://idp.example.com"),
            ("discovery_url", "https://idp.example.com/.well-known/openid-configuration"),
            ("client_id", "abc"),
            ("allowed_algorithms", ["RS256"]),
            ("jwks_uri", "https://idp.example.com/jwks"),
            ("in_cluster", True),
            ("namespace_allowlist", ["team-a"]),
        ],
    )
    def test_token_validation_fields_are_refused_on_saml(self, field, value):
        self._rejected(build([saml_entry(**{field: value})]), f"'{field}' does not apply to a 'saml' provider")

    @pytest.mark.parametrize(
        "field, value",
        [
            ("entity_id", "https://sp"),
            ("idp_entity_id", "https://idp"),
            ("idp_sso_url", "https://idp/sso"),
            ("idp_x509_cert", "MII"),
            ("idp_metadata_url", "https://idp/metadata"),
            ("sp_private_key", "key"),
            ("sp_private_key_file", "/etc/key.pem"),
            ("want_assertions_signed", True),
            ("sign_requests", True),
        ],
    )
    @pytest.mark.parametrize("provider_type", ["oidc", "k8s"])
    def test_saml_fields_are_refused_on_other_types(self, field, value, provider_type):
        result = build([valid_entry(type=provider_type, **{field: value})])

        assert result.providers == []
        assert any(f"'{field}' applies only to a 'saml' provider" in error for error in result.errors)

    def test_the_default_id_is_refused(self):
        """``default`` may adopt existing accounts by name; a SAML attribute must never get that."""
        self._rejected(build([saml_entry(id="default")]), "cannot use the id 'default'")

    def test_email_binding_is_refused(self):
        """SAML asserts no verified-email flag, so email binding could only ever be faked."""
        self._rejected(build([saml_entry(identity_binding="email", allowed_email_domains=["example.com"])]), "identity_binding 'email'")

    def test_an_entry_requiring_no_signature_at_all_is_refused(self):
        self._rejected(build([saml_entry(want_assertions_signed=False, want_response_signed=False)]), "an unsigned assertion proves nothing")

    def test_a_signed_response_alone_is_accepted(self):
        [provider] = build([saml_entry(want_assertions_signed=False, want_response_signed=True)]).providers

        assert provider.want_response_signed is True

    @pytest.mark.parametrize("field", ["want_assertions_signed", "want_response_signed", "sign_requests"])
    @pytest.mark.parametrize("value", ["false", "true", 0, 1, None])
    def test_flags_must_be_booleans(self, field, value):
        self._rejected(build([saml_entry(**{field: value})]), f"'{field}' must be true or false")

    @pytest.mark.parametrize("value", [-1, 301, True, "60", 1.5])
    def test_clock_skew_is_bounded(self, value):
        self._rejected(build([saml_entry(clock_skew_seconds=value)]), "'clock_skew_seconds'")

    def test_signing_needs_a_key(self):
        self._rejected(build([saml_entry(sign_requests=True)]), "'sign_requests' needs")

    def test_a_key_without_a_certificate_is_refused(self):
        key, _ = _test_keypair("sp")

        self._rejected(build([saml_entry(sp_private_key=key)]), "must be configured together")

    def test_a_mismatched_certificate_and_key_are_refused(self):
        key, _ = _test_keypair("sp")
        _, other_cert = _test_keypair("other")

        self._rejected(build([saml_entry(sp_private_key=key, sp_x509_cert=other_cert)]), "does not match")

    def test_an_inline_key_and_certificate_enable_signing(self):
        key, cert = _test_keypair("sp")

        [provider] = build([saml_entry(sp_private_key=key, sp_x509_cert=cert, sign_requests=True)]).providers

        assert provider.sign_requests is True
        assert provider.sp_x509_cert == _cert_body(cert)
        assert "PRIVATE KEY" in provider.sp_private_key

    def test_a_key_file_is_read(self, tmp_path):
        key, cert = _test_keypair("sp")
        key_file = tmp_path / "sp.key"
        key_file.write_text(key)

        [provider] = build([saml_entry(sp_private_key_file=str(key_file), sp_x509_cert=cert, sign_requests=True)]).providers

        assert provider.sp_private_key.strip() == key.strip()

    def test_an_unreadable_key_file_is_refused(self, tmp_path):
        _, cert = _test_keypair("sp")

        self._rejected(build([saml_entry(sp_private_key_file=str(tmp_path / "missing.key"), sp_x509_cert=cert)]), "could not be read")

    def test_both_key_sources_are_refused(self, tmp_path):
        key, cert = _test_keypair("sp")

        self._rejected(build([saml_entry(sp_private_key=key, sp_private_key_file=str(tmp_path / "k"), sp_x509_cert=cert)]), "not both")

    def test_the_private_key_never_reaches_an_error_or_a_repr(self):
        key, cert = _test_keypair("sp")
        key_body = _cert_body(key)
        broken = key.replace(key_body[10:40], "A" * 30)

        rejected = build([saml_entry(sp_private_key=broken, sp_x509_cert=cert)])
        [accepted] = build([saml_entry(sp_private_key=key, sp_x509_cert=cert)]).providers

        assert not any(key_body[:40] in error or broken[40:80] in error for error in rejected.errors)
        assert key_body[:40] not in repr(accepted)
        assert "sp_private_key" not in repr(accepted)

    def test_without_the_extra_the_saml_entry_is_dropped_and_the_rest_survive(self, extra_installed, monkeypatch):
        monkeypatch.setattr(extra_installed, "_saml_extra_installed", lambda: False)

        result = build([valid_entry(), saml_entry()])

        assert [provider.id for provider in result.providers] == ["okta"]
        assert any("[saml] extra" in error for error in result.errors)


class TestSamlMetadataUrl:
    """``idp_metadata_url`` is read once at registry build; any failure drops the provider."""

    @pytest.fixture(autouse=True)
    def extra_installed(self, monkeypatch):
        from mlflow_oidc_auth import provider_registry as registry_module

        monkeypatch.setattr(registry_module, "_saml_extra_installed", lambda: True)
        monkeypatch.setattr(registry_module, "_METADATA_CACHE", {})
        return registry_module

    def _entry(self, **overrides):
        entry = saml_entry(idp_metadata_url="https://idp.example.com/metadata")
        entry.pop("idp_x509_cert")
        entry.pop("idp_sso_url")
        entry.update(overrides)
        return entry

    def test_metadata_fills_what_was_left_out(self, extra_installed, monkeypatch):
        _, cert = _test_keypair("idp")
        calls = []

        def _fetch(url, entity_id):
            calls.append((url, entity_id))
            return {"sso_url": "https://idp.example.com/sso", "slo_url": "https://idp.example.com/slo", "certs": [_cert_body(cert)]}

        monkeypatch.setattr(extra_installed, "_fetch_idp_metadata", _fetch)

        [provider] = build([self._entry()]).providers

        assert calls == [("https://idp.example.com/metadata", "https://idp.example.com/saml")]
        assert provider.idp_sso_url == "https://idp.example.com/sso"
        assert provider.idp_slo_url == "https://idp.example.com/slo"
        assert provider.idp_x509_certs == (_cert_body(cert),)

    def test_explicit_values_win_and_skip_the_fetch(self, extra_installed, monkeypatch):
        def _fetch(url, entity_id):
            raise AssertionError("nothing left to fill, so nothing should be fetched")

        monkeypatch.setattr(extra_installed, "_fetch_idp_metadata", _fetch)

        [provider] = build([saml_entry(idp_metadata_url="https://idp.example.com/metadata", idp_slo_url="https://idp.example.com/slo")]).providers

        assert provider.idp_sso_url == "https://idp.example.com/sso"

    def test_a_failed_fetch_drops_the_provider_with_the_reason(self, extra_installed, monkeypatch):
        def _fetch(url, entity_id):
            raise ValueError("the request failed (ConnectTimeout)")

        monkeypatch.setattr(extra_installed, "_fetch_idp_metadata", _fetch)

        result = build([valid_entry(), self._entry()])

        assert [provider.id for provider in result.providers] == ["okta"]
        assert any("could not load IdP metadata" in error and "ConnectTimeout" in error for error in result.errors)

    def test_metadata_without_a_certificate_drops_the_provider(self, extra_installed, monkeypatch):
        monkeypatch.setattr(extra_installed, "_fetch_idp_metadata", lambda url, entity_id: {"sso_url": "https://idp/sso", "slo_url": None, "certs": []})

        assert build([self._entry()]).providers == []

    def test_an_entry_invalid_for_other_reasons_is_never_fetched(self, extra_installed, monkeypatch):
        def _fetch(url, entity_id):
            raise AssertionError("fetched for an entry that is dropped anyway")

        monkeypatch.setattr(extra_installed, "_fetch_idp_metadata", _fetch)

        assert build([self._entry(audience="mlflow")]).providers == []


@pytest.mark.skipif(not importlib.import_module("mlflow_oidc_auth.provider_registry")._saml_extra_installed(), reason="the [saml] extra is not installed")
class TestSamlMetadataFetch:
    """The fetch itself, with ``requests`` replaced — no network."""

    ENTITY = "https://idp.example.com/saml"

    def _metadata(self, entity_id=ENTITY):
        _, cert = _test_keypair("idp")
        return (
            '<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" entityID="' + entity_id + '">'
            '<md:IDPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">'
            '<md:KeyDescriptor use="signing"><ds:KeyInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#"><ds:X509Data><ds:X509Certificate>'
            + _cert_body(cert)
            + "</ds:X509Certificate></ds:X509Data></ds:KeyInfo></md:KeyDescriptor>"
            '<md:SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect" Location="https://idp.example.com/slo"/>'
            '<md:SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect" Location="https://idp.example.com/sso"/>'
            "</md:IDPSSODescriptor></md:EntityDescriptor>"
        ).encode()

    @pytest.fixture
    def fake_get(self, monkeypatch):
        import requests

        from mlflow_oidc_auth import provider_registry as registry_module

        monkeypatch.setattr(registry_module, "_METADATA_CACHE", {})
        seen = {}

        def _install(body=b"", status=200):
            class _Raw:
                def read(self, amount, decode_content=True):
                    return body[:amount]

            class _Response:
                status_code = status
                raw = _Raw()

                def close(self):
                    pass

            def _get(url, **kwargs):
                seen.update(kwargs, url=url)
                return _Response()

            monkeypatch.setattr(requests, "get", _get)
            return seen

        return _install

    def test_it_reads_the_signing_certificate_and_endpoints(self, fake_get):
        from mlflow_oidc_auth.provider_registry import _fetch_idp_metadata

        seen = fake_get(self._metadata())

        result = _fetch_idp_metadata("https://idp.example.com/metadata", self.ENTITY)

        assert result["sso_url"] == "https://idp.example.com/sso"
        assert result["slo_url"] == "https://idp.example.com/slo"
        assert len(result["certs"]) == 1
        assert seen["timeout"] == 10
        assert seen["allow_redirects"] is False

    def test_metadata_for_another_entity_is_refused(self, fake_get):
        from mlflow_oidc_auth.provider_registry import _fetch_idp_metadata

        fake_get(self._metadata(entity_id="https://someone-else.example.com"))

        with pytest.raises(ValueError, match="idp_entity_id"):
            _fetch_idp_metadata("https://idp.example.com/metadata", self.ENTITY)

    def test_a_redirect_is_not_followed(self, fake_get):
        from mlflow_oidc_auth.provider_registry import _fetch_idp_metadata

        fake_get(status=302)

        with pytest.raises(ValueError, match="HTTP 302"):
            _fetch_idp_metadata("https://idp.example.com/metadata", self.ENTITY)

    def test_an_oversized_document_is_refused(self, fake_get):
        from mlflow_oidc_auth.provider_registry import _fetch_idp_metadata

        fake_get(b"<" + b"a" * (1024 * 1024 + 10))

        with pytest.raises(ValueError, match="1 MiB"):
            _fetch_idp_metadata("https://idp.example.com/metadata", self.ENTITY)

    def test_a_document_with_a_dtd_is_refused(self, fake_get):
        from mlflow_oidc_auth.provider_registry import _fetch_idp_metadata

        fake_get(b'<!DOCTYPE r [<!ENTITY e SYSTEM "file:///etc/passwd">]>' + self._metadata())

        with pytest.raises(ValueError, match="not usable SAML metadata"):
            _fetch_idp_metadata("https://idp.example.com/metadata", self.ENTITY)
