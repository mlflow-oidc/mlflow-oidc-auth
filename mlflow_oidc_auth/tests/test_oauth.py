"""
Comprehensive tests for the oauth.py module.

This module tests OAuth client configuration, token handling, OAuth flow
implementation, error scenarios, security measures, token validation,
and OIDC provider integration.
"""

import sys
import unittest
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import patch
from typing import Callable


def _force_reimport(*names: str) -> Callable[[], None]:
    """Delete ``names`` from ``sys.modules`` so the next ``import`` re-executes them, and
    return a callback that restores the original module objects.

    These tests force a fresh import of `mlflow_oidc_auth.oauth` (and the
    `mlflow_oidc_auth.config` it reads at import time) to pick up mocked config or
    environment variables. Left in place, that deletion leaves a second, orphaned
    `AppConfig`/oauth module living in the process: whichever test runs next gets whichever
    copy happens to be in `sys.modules` at that moment, which is order-dependent under
    pytest-randomly (#353). `unittest.TestCase` methods cannot request the `monkeypatch`
    fixture directly, so register the returned callback with `self.addCleanup` instead —
    it runs even if the test fails, exactly like `monkeypatch.delitem(..., raising=False)`
    does for the plain pytest-style tests elsewhere in this suite.

    Restoring the ``sys.modules`` entry is not enough on its own: when the deleted name gets
    reimported, the import system also does ``setattr(parent_package, attr, new_module)`` on
    the parent package object (e.g. ``setattr(mlflow_oidc_auth, "oauth", <new module>)``), and
    a bare ``sys.modules`` restore does not touch that attribute. Code that reaches the module
    via ``mlflow_oidc_auth.oauth`` (rather than looking it up in ``sys.modules`` again) would
    keep seeing the duplicate. Snapshot and restore that attribute too.
    """
    originals = {name: sys.modules.get(name) for name in names}
    attr_originals = {}
    for name in names:
        if "." not in name:
            continue
        parent_name, _, attr = name.rpartition(".")
        parent = sys.modules.get(parent_name)
        if parent is not None and hasattr(parent, attr):
            attr_originals[(parent_name, attr)] = getattr(parent, attr)

    def _restore() -> None:
        for name, module in originals.items():
            if module is not None:
                sys.modules[name] = module
            else:
                sys.modules.pop(name, None)
        for (parent_name, attr), value in attr_originals.items():
            parent = sys.modules.get(parent_name)
            if parent is not None:
                setattr(parent, attr, value)

    for name in names:
        sys.modules.pop(name, None)
    return _restore


class TestOAuthModule(unittest.TestCase):
    """Test the OAuth module functionality."""

    def test_oauth_instance_exists(self):
        """Test that the oauth instance exists and is properly initialized."""
        import mlflow_oidc_auth.oauth

        # Verify the oauth instance exists
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

        # Verify it has the expected type
        from authlib.integrations.starlette_client import OAuth

        self.assertIsInstance(mlflow_oidc_auth.oauth.oauth, OAuth)

    def test_oauth_client_registration(self):
        """Test that the OIDC client is registered with the oauth instance."""
        import mlflow_oidc_auth.oauth

        # Verify the oauth instance has clients registered
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

        # Check if the 'oidc' client is registered
        # Note: We can't directly access the clients dict in authlib,
        # but we can verify the oauth instance exists and is configured
        self.assertTrue(hasattr(mlflow_oidc_auth.oauth.oauth, "register"))

    def test_oauth_configuration_access(self):
        """Test that OAuth configuration is accessible from the config module."""
        from mlflow_oidc_auth.config import config

        # Verify config attributes exist (they may be None if not set)
        self.assertTrue(hasattr(config, "OIDC_CLIENT_ID"))
        self.assertTrue(hasattr(config, "OIDC_CLIENT_SECRET"))
        self.assertTrue(hasattr(config, "OIDC_DISCOVERY_URL"))
        self.assertTrue(hasattr(config, "OIDC_SCOPE"))
        self.assertTrue(hasattr(config, "OIDC_CODE_CHALLENGE"))

    @patch("mlflow_oidc_auth.config.config")
    def test_oauth_with_mocked_config(self, mock_config):
        """Test OAuth behavior with mocked configuration."""
        # Setup mock config
        mock_config.OIDC_CLIENT_ID = "test_client_id"
        mock_config.OIDC_CLIENT_SECRET = "test_client_secret"
        mock_config.OIDC_DISCOVERY_URL = "https://example.com/.well-known/openid_configuration"
        mock_config.OIDC_SCOPE = "openid email profile"
        mock_config.OIDC_CODE_CHALLENGE = None

        # Clear the module cache to force re-import with mocked config
        self.addCleanup(_force_reimport("mlflow_oidc_auth.oauth"))

        # Import with mocked config
        import mlflow_oidc_auth.oauth

        # Verify the oauth instance exists
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

    @patch.dict(
        "os.environ",
        {
            "OIDC_CLIENT_ID": "test_client_id",
            "OIDC_CLIENT_SECRET": "test_client_secret",
            "OIDC_DISCOVERY_URL": "https://example.com/.well-known/openid_configuration",
            "OIDC_SCOPE": "openid email profile",
        },
    )
    def test_oauth_with_environment_variables(self):
        """Test OAuth initialization with environment variables."""
        # Clear the module cache to force re-import with new env vars
        self.addCleanup(_force_reimport("mlflow_oidc_auth.oauth", "mlflow_oidc_auth.config"))

        # Import with environment variables set
        import mlflow_oidc_auth.oauth

        # Verify the oauth instance exists
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

    @patch.dict(
        "os.environ",
        {
            "OIDC_CLIENT_ID": "",
            "OIDC_CLIENT_SECRET": "",
            "OIDC_DISCOVERY_URL": "",
            "OIDC_SCOPE": "",
        },
    )
    def test_oauth_with_empty_environment_variables(self):
        """Test OAuth initialization with empty environment variables."""
        # Clear the module cache to force re-import with new env vars
        self.addCleanup(_force_reimport("mlflow_oidc_auth.oauth", "mlflow_oidc_auth.config"))

        # Import with empty environment variables
        import mlflow_oidc_auth.oauth

        # Verify the oauth instance exists even with empty config
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

    def test_oauth_module_attributes(self):
        """Test that the oauth module has the expected attributes."""
        import mlflow_oidc_auth.oauth

        # Verify the module has the oauth attribute
        self.assertTrue(hasattr(mlflow_oidc_auth.oauth, "oauth"))

        # Verify the oauth instance has expected methods
        self.assertTrue(hasattr(mlflow_oidc_auth.oauth.oauth, "register"))

    def test_oauth_import_structure(self):
        """Test the import structure of the oauth module."""
        import mlflow_oidc_auth.oauth

        # Verify imports work correctly
        self.assertIsNotNone(mlflow_oidc_auth.oauth)

        # Verify the OAuth class is imported
        from authlib.integrations.starlette_client import OAuth

        self.assertTrue(issubclass(type(mlflow_oidc_auth.oauth.oauth), OAuth))

    @patch.dict(
        "os.environ",
        {
            "OIDC_CLIENT_ID": "client@#$%^&*()",
            "OIDC_CLIENT_SECRET": "secret!@#$%^&*()",
            "OIDC_DISCOVERY_URL": "https://example.com/path?query=value&other=test",
            "OIDC_SCOPE": "openid email profile custom:scope",
        },
    )
    def test_oauth_with_special_characters_in_config(self):
        """Test OAuth initialization with special characters in configuration."""
        # Clear the module cache to force re-import with new env vars
        self.addCleanup(_force_reimport("mlflow_oidc_auth.oauth", "mlflow_oidc_auth.config"))

        # Import with special characters in config
        import mlflow_oidc_auth.oauth

        # Verify the oauth instance exists
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

    @patch.dict(
        "os.environ",
        {
            "OIDC_CLIENT_ID": "client_测试_🔐",
            "OIDC_CLIENT_SECRET": "secret_тест_🔑",
            "OIDC_DISCOVERY_URL": "https://example.com/测试/.well-known/openid_configuration",
            "OIDC_SCOPE": "openid email profile custom:测试",
        },
    )
    def test_oauth_with_unicode_config(self):
        """Test OAuth initialization with Unicode characters in configuration."""
        # Clear the module cache to force re-import with new env vars
        self.addCleanup(_force_reimport("mlflow_oidc_auth.oauth", "mlflow_oidc_auth.config"))

        # Import with Unicode characters in config
        import mlflow_oidc_auth.oauth

        # Verify the oauth instance exists
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)


class TestOAuthIntegration(unittest.TestCase):
    """Test OAuth integration with OIDC providers."""

    @patch.dict(
        "os.environ",
        {
            "OIDC_CLIENT_ID": "mlflow-client-123",
            "OIDC_CLIENT_SECRET": "super-secret-key-456",
            "OIDC_DISCOVERY_URL": "https://auth.example.com/.well-known/openid_configuration",
            "OIDC_SCOPE": "openid email profile groups",
        },
    )
    def test_oauth_oidc_provider_integration(self):
        """Test OAuth integration with OIDC providers."""
        # Clear the module cache to force re-import with new env vars
        self.addCleanup(_force_reimport("mlflow_oidc_auth.oauth", "mlflow_oidc_auth.config"))

        # Import with realistic OIDC provider configuration
        import mlflow_oidc_auth.oauth

        # Verify proper OIDC provider integration setup
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

    @patch.dict(
        "os.environ",
        {
            "OIDC_CLIENT_ID": "azure-app-id-123",
            "OIDC_CLIENT_SECRET": "azure-client-secret",
            "OIDC_DISCOVERY_URL": "https://login.microsoftonline.com/tenant-id/v2.0/.well-known/openid_configuration",
            "OIDC_SCOPE": "openid email profile https://graph.microsoft.com/User.Read",
        },
    )
    def test_oauth_microsoft_entra_id_integration(self):
        """Test OAuth integration with Microsoft Entra ID (Azure AD)."""
        # Clear the module cache to force re-import with new env vars
        self.addCleanup(_force_reimport("mlflow_oidc_auth.oauth", "mlflow_oidc_auth.config"))

        # Import with Microsoft Entra ID configuration
        import mlflow_oidc_auth.oauth

        # Verify Microsoft Entra ID integration setup
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

    @patch.dict(
        "os.environ",
        {
            "OIDC_CLIENT_ID": "okta-client-id",
            "OIDC_CLIENT_SECRET": "okta-client-secret",
            "OIDC_DISCOVERY_URL": "https://dev-123456.okta.com/.well-known/openid_configuration",
            "OIDC_SCOPE": "openid email profile groups",
        },
    )
    def test_oauth_okta_integration(self):
        """Test OAuth integration with Okta."""
        # Clear the module cache to force re-import with new env vars
        self.addCleanup(_force_reimport("mlflow_oidc_auth.oauth", "mlflow_oidc_auth.config"))

        # Import with Okta configuration
        import mlflow_oidc_auth.oauth

        # Verify Okta integration setup
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

    def test_oauth_integration_with_default_config(self):
        """Test OAuth integration with default configuration."""
        import mlflow_oidc_auth.oauth

        # Verify integration works with default config
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

        # Verify the oauth instance has the expected interface
        self.assertTrue(hasattr(mlflow_oidc_auth.oauth.oauth, "register"))

    @patch.dict(
        "os.environ",
        {
            "OIDC_CLIENT_ID": "google-client-id",
            "OIDC_CLIENT_SECRET": "google-client-secret",
            "OIDC_DISCOVERY_URL": "https://accounts.google.com/.well-known/openid_configuration",
            "OIDC_SCOPE": "openid email profile",
        },
    )
    def test_oauth_google_integration(self):
        """Test OAuth integration with Google."""
        # Clear the module cache to force re-import with new env vars
        self.addCleanup(_force_reimport("mlflow_oidc_auth.oauth", "mlflow_oidc_auth.config"))

        # Import with Google configuration
        import mlflow_oidc_auth.oauth

        # Verify Google integration setup
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)


class TestOAuthSecurity(unittest.TestCase):
    """Test OAuth security measures and token validation."""

    @patch.dict(
        "os.environ",
        {
            "OIDC_CLIENT_ID": "secure-client-id",
            "OIDC_CLIENT_SECRET": "very-secure-client-secret-with-high-entropy",
            "OIDC_DISCOVERY_URL": "https://secure-auth.example.com/.well-known/openid_configuration",
            "OIDC_SCOPE": "openid email profile",
        },
    )
    def test_oauth_security_configuration(self):
        """Test OAuth security configuration and measures."""
        # Clear the module cache to force re-import with new env vars
        self.addCleanup(_force_reimport("mlflow_oidc_auth.oauth", "mlflow_oidc_auth.config"))

        # Import with secure configuration
        import mlflow_oidc_auth.oauth

        # Verify secure configuration is handled correctly
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

    @patch.dict(
        "os.environ",
        {
            "OIDC_CLIENT_ID": "client-id",
            "OIDC_CLIENT_SECRET": "client-secret",
            "OIDC_DISCOVERY_URL": "http://insecure-auth.example.com/.well-known/openid_configuration",
            "OIDC_SCOPE": "openid email profile",
        },
    )
    def test_oauth_insecure_http_url_handling(self):
        """Test OAuth handling of insecure HTTP URLs."""
        # Clear the module cache to force re-import with new env vars
        self.addCleanup(_force_reimport("mlflow_oidc_auth.oauth", "mlflow_oidc_auth.config"))

        # Import with insecure HTTP URL (should still work)
        import mlflow_oidc_auth.oauth

        # Verify insecure URL is handled (OAuth library should handle security warnings)
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

    @patch.dict(
        "os.environ",
        {
            "OIDC_CLIENT_ID": "client-id",
            "OIDC_CLIENT_SECRET": "client-secret",
            "OIDC_DISCOVERY_URL": "not-a-valid-url",
            "OIDC_SCOPE": "openid email profile",
        },
    )
    def test_oauth_malformed_url_handling(self):
        """Test OAuth handling of malformed URLs."""
        # Clear the module cache to force re-import with new env vars
        self.addCleanup(_force_reimport("mlflow_oidc_auth.oauth", "mlflow_oidc_auth.config"))

        # Import with malformed URL
        import mlflow_oidc_auth.oauth

        # Verify malformed URL is handled (OAuth library should handle validation)
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

    def test_oauth_security_attributes(self):
        """Test OAuth security-related attributes and methods."""
        import mlflow_oidc_auth.oauth

        # Verify the oauth instance exists
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

        # Verify it's using the secure authlib OAuth implementation
        from authlib.integrations.starlette_client import OAuth

        self.assertIsInstance(mlflow_oidc_auth.oauth.oauth, OAuth)

    @patch.dict(
        "os.environ",
        {
            "OIDC_CLIENT_ID": "test-client",
            "OIDC_CLIENT_SECRET": "test-secret",
            "OIDC_DISCOVERY_URL": "https://auth.example.com/.well-known/openid_configuration",
            "OIDC_SCOPE": "openid email profile groups admin",
        },
    )
    def test_oauth_scope_security(self):
        """Test OAuth scope configuration for security."""
        # Clear the module cache to force re-import with new env vars
        self.addCleanup(_force_reimport("mlflow_oidc_auth.oauth", "mlflow_oidc_auth.config"))

        # Import with extended scopes
        import mlflow_oidc_auth.oauth

        # Verify scope configuration is handled
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

    def test_oauth_default_security_settings(self):
        """Test OAuth with default security settings."""
        import mlflow_oidc_auth.oauth

        # Verify default security settings work
        self.assertIsNotNone(mlflow_oidc_auth.oauth.oauth)

        # Verify the oauth instance is properly configured
        self.assertTrue(hasattr(mlflow_oidc_auth.oauth.oauth, "register"))


class TestBuildScope(unittest.TestCase):
    """``_build_scope`` must always emit space-delimited scopes (RFC 6749 §3.3, issue #238)."""

    def test_comma_scope_is_normalized_to_spaces_when_refresh_disabled(self):
        """The #238 bug: a comma-separated scope must go out space-delimited, not verbatim."""
        from mlflow_oidc_auth import oauth as oauth_mod

        with (
            patch.object(oauth_mod.config, "OIDC_USE_REFRESH_TOKEN", False, create=True),
            patch.object(oauth_mod.config, "OIDC_SCOPE", "openid,email,profile", create=True),
        ):
            self.assertEqual(oauth_mod._build_scope(), "openid email profile")

    def test_space_scope_is_preserved_when_refresh_disabled(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        with (
            patch.object(oauth_mod.config, "OIDC_USE_REFRESH_TOKEN", False, create=True),
            patch.object(oauth_mod.config, "OIDC_SCOPE", "openid email profile", create=True),
        ):
            self.assertEqual(oauth_mod._build_scope(), "openid email profile")

    def test_mixed_and_padded_separators_are_normalized(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        with (
            patch.object(oauth_mod.config, "OIDC_USE_REFRESH_TOKEN", False, create=True),
            patch.object(oauth_mod.config, "OIDC_SCOPE", " openid, email profile ,groups ", create=True),
        ):
            self.assertEqual(oauth_mod._build_scope(), "openid email profile groups")

    def test_appends_offline_access_space_delimited_from_csv_scope(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        with (
            patch.object(oauth_mod.config, "OIDC_USE_REFRESH_TOKEN", True, create=True),
            patch.object(oauth_mod.config, "OIDC_SCOPE", "openid,email,profile", create=True),
        ):
            self.assertEqual(oauth_mod._build_scope(), "openid email profile offline_access")

    def test_appends_offline_access_to_space_separated_scope(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        with (
            patch.object(oauth_mod.config, "OIDC_USE_REFRESH_TOKEN", True, create=True),
            patch.object(oauth_mod.config, "OIDC_SCOPE", "openid email profile", create=True),
        ):
            self.assertEqual(oauth_mod._build_scope(), "openid email profile offline_access")

    def test_does_not_duplicate_offline_access(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        with (
            patch.object(oauth_mod.config, "OIDC_USE_REFRESH_TOKEN", True, create=True),
            patch.object(oauth_mod.config, "OIDC_SCOPE", "openid,offline_access,email", create=True),
        ):
            self.assertEqual(oauth_mod._build_scope(), "openid offline_access email")

    def test_duplicate_scopes_are_collapsed(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        with (
            patch.object(oauth_mod.config, "OIDC_USE_REFRESH_TOKEN", False, create=True),
            patch.object(oauth_mod.config, "OIDC_SCOPE", "openid,openid email email", create=True),
        ):
            self.assertEqual(oauth_mod._build_scope(), "openid email")

    def test_empty_scope_yields_empty_string(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        with (
            patch.object(oauth_mod.config, "OIDC_USE_REFRESH_TOKEN", False, create=True),
            patch.object(oauth_mod.config, "OIDC_SCOPE", "", create=True),
        ):
            self.assertEqual(oauth_mod._build_scope(), "")


_DISCOVERY = "https://auth.example.com/.well-known/openid-configuration"
_TOKEN_ENDPOINT = "https://auth.example.com/token"
_REVOCATION_ENDPOINT = "https://auth.example.com/revoke"
_SECRET = "test-client-secret"


@contextmanager
def _patch_config(oauth_mod, **kwargs):
    """Patch the ``config`` attributes that client registration reads.

    The default is a flat (legacy) deployment with a confidential client and PKCE on.
    """

    defaults = {
        "OIDC_CLIENT_ID": "test-client-id",
        "OIDC_CLIENT_SECRET": _SECRET,
        "OIDC_DISCOVERY_URL": _DISCOVERY,
        "OIDC_SCOPE": "openid,email,profile",
        "OIDC_USE_REFRESH_TOKEN": False,
        "OIDC_VERIFY_SSL": True,
        "OIDC_CODE_CHALLENGE": "S256",
        "OIDC_PUBLIC_CLIENT": False,
        # No registry configured, so the default provider falls back to the flat OIDC_*
        # variables — the shape a legacy deployment has.
        "AUTH_PROVIDERS": SimpleNamespace(providers=[], source="legacy", by_id=lambda _: None),
    }
    defaults.update(kwargs)
    with ExitStack() as stack:
        for key, value in defaults.items():
            stack.enter_context(patch.object(oauth_mod.config, key, value, create=True))
        stack.enter_context(patch.object(oauth_mod, "_registered", {}))
        stack.enter_context(patch.object(oauth_mod, "_refusals_logged", set()))
        yield


def _registry_with(oauth_mod, public_client: bool):
    """A registry holding one OIDC provider ``okta``, declared public or not."""
    provider = SimpleNamespace(
        id="okta",
        type="oidc",
        client_id="okta-id",
        discovery_url="https://okta.example.com/.well-known/openid-configuration",
        public_client=public_client,
    )
    return SimpleNamespace(providers=[provider], source="env", by_id=lambda pid: provider if pid == "okta" else None)


# (public_client, secret, pkce, registered, log fragment). Every row of the rules table in
# ``oauth._credentials_usable``.
_RULES = [
    (False, _SECRET, "S256", True, None),
    (False, _SECRET, None, True, None),
    (False, None, "S256", False, "has no client secret"),
    (False, None, None, False, "has no client secret"),
    (True, None, "S256", True, None),
    (True, None, None, False, "PKCE is disabled"),
    (True, _SECRET, None, False, "PKCE is disabled"),
    (True, _SECRET, "S256", False, "contradictory"),
]


class TestPublicClientRegistration(unittest.TestCase):
    """A client is public only when declared so (#300): a missing secret alone is refused."""

    def _assert_rule(self, oauth_mod, provider_id, public_client, secret, pkce, registered, fragment):
        with self.subTest(public_client=public_client, secret=bool(secret), pkce=pkce):
            if registered:
                settings = oauth_mod._client_settings(provider_id)
                self.assertIsNotNone(settings)
                if public_client:
                    self.assertNotIn("client_secret", settings)
                else:
                    self.assertEqual(settings["client_secret"], secret)
            else:
                with self.assertLogs(oauth_mod.logger, level="ERROR") as captured:
                    self.assertIsNone(oauth_mod._client_settings(provider_id))
                output = "".join(captured.output)
                self.assertIn(fragment, output)
                self.assertIn(f"'{provider_id}'", output)
                # The secret is never logged, whichever rule refused the provider.
                self.assertNotIn(_SECRET, output)

    def test_rules_for_the_flat_configuration(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        for public_client, secret, pkce, registered, fragment in _RULES:
            with _patch_config(oauth_mod, OIDC_PUBLIC_CLIENT=public_client, OIDC_CLIENT_SECRET=secret, OIDC_CODE_CHALLENGE=pkce):
                self._assert_rule(oauth_mod, oauth_mod.DEFAULT_PROVIDER_ID, public_client, secret, pkce, registered, fragment)

    def test_rules_for_a_registry_provider(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        for public_client, secret, pkce, registered, fragment in _RULES:
            with (
                _patch_config(oauth_mod, AUTH_PROVIDERS=_registry_with(oauth_mod, public_client), OIDC_CODE_CHALLENGE=pkce),
                patch.object(oauth_mod, "_client_secret_for", return_value=secret),
            ):
                self._assert_rule(oauth_mod, "okta", public_client, secret, pkce, registered, fragment)

    def test_the_synthesised_default_provider_carries_oidc_public_client(self):
        """The real legacy path: the registry synthesises ``default`` from the flat variables."""
        from mlflow_oidc_auth import oauth as oauth_mod
        from mlflow_oidc_auth.provider_registry import build_provider_registry

        for flag in (True, False):
            app_config = SimpleNamespace(OIDC_CLIENT_ID="test-client-id", OIDC_DISCOVERY_URL=_DISCOVERY, OIDC_PUBLIC_CLIENT=flag)
            registry = build_provider_registry(SimpleNamespace(get=lambda key, default=None: default), app_config)
            self.assertEqual(registry.providers[0].public_client, flag)

            with _patch_config(oauth_mod, AUTH_PROVIDERS=registry, OIDC_PUBLIC_CLIENT=flag, OIDC_CLIENT_SECRET=None):
                if flag:
                    self.assertNotIn("client_secret", oauth_mod._client_settings(oauth_mod.DEFAULT_PROVIDER_ID))
                else:
                    with self.assertLogs(oauth_mod.logger, level="ERROR"):
                        self.assertIsNone(oauth_mod._client_settings(oauth_mod.DEFAULT_PROVIDER_ID))

    def test_a_missing_secret_names_the_settings_to_change(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        with _patch_config(oauth_mod, OIDC_CLIENT_SECRET=None), self.assertLogs(oauth_mod.logger, level="ERROR") as captured:
            oauth_mod._client_settings(oauth_mod.DEFAULT_PROVIDER_ID)
        self.assertIn("OIDC_CLIENT_SECRET", "".join(captured.output))
        self.assertIn("OIDC_PUBLIC_CLIENT=true", "".join(captured.output))

        with (
            _patch_config(oauth_mod, AUTH_PROVIDERS=_registry_with(oauth_mod, False)),
            patch.object(oauth_mod, "_client_secret_for", return_value=None),
            self.assertLogs(oauth_mod.logger, level="ERROR") as captured,
        ):
            oauth_mod._client_settings("okta")
        self.assertIn("OIDC_CLIENT_SECRET_<PROVIDER_ID>", "".join(captured.output))
        self.assertIn('"public_client": true', "".join(captured.output))

    def test_legacy_config_without_a_secret_is_named_not_silently_dropped(self):
        """A deployment that set an id and a discovery URL must not be told nothing was configured."""
        from mlflow_oidc_auth import oauth as oauth_mod

        with _patch_config(oauth_mod, OIDC_CLIENT_SECRET=None):
            # The gate that decides whether registration is attempted at all must still pass, or
            # the specific error is never reached.
            self.assertTrue(oauth_mod._has_required_config())
            with self.assertLogs(oauth_mod.logger, level="ERROR"):
                self.assertEqual(oauth_mod.ensure_all_clients_registered(), {oauth_mod.DEFAULT_PROVIDER_ID: False})

    def test_registration_omits_client_secret_for_a_public_client(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        with (
            _patch_config(oauth_mod, OIDC_CLIENT_SECRET=None, OIDC_PUBLIC_CLIENT=True),
            patch.object(oauth_mod.oauth, "register") as mock_register,
        ):
            self.assertTrue(oauth_mod.ensure_client_registered())

        kwargs = mock_register.call_args.kwargs
        # Absent, not merely falsy: the "none" auth method must follow from there being no
        # secret, not from how authlib reads an empty one.
        self.assertNotIn("client_secret", kwargs)
        self.assertEqual(kwargs["client_id"], "test-client-id")
        self.assertEqual(kwargs["client_kwargs"]["code_challenge_method"], "S256")

    def test_a_refusal_is_logged_once_per_provider_not_per_check(self):
        """The readiness probe re-checks a refused provider every few seconds; one line is enough."""
        from mlflow_oidc_auth import oauth as oauth_mod

        with _patch_config(oauth_mod, OIDC_CLIENT_SECRET=None), self.assertLogs(oauth_mod.logger, level="ERROR") as captured:
            for _ in range(3):
                self.assertFalse(oauth_mod.is_oidc_configured())
        self.assertEqual(len([line for line in captured.output if "has no client secret" in line]), 1)

    def test_registration_does_not_happen_for_a_refused_provider(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        with (
            _patch_config(oauth_mod, OIDC_CLIENT_SECRET=None),
            patch.object(oauth_mod.oauth, "register") as mock_register,
            self.assertLogs(oauth_mod.logger, level="ERROR"),
        ):
            self.assertFalse(oauth_mod.ensure_client_registered())
        mock_register.assert_not_called()

    def test_registration_passes_client_secret_for_a_confidential_client(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        with _patch_config(oauth_mod), patch.object(oauth_mod.oauth, "register") as mock_register:
            self.assertTrue(oauth_mod.ensure_client_registered())

        self.assertEqual(mock_register.call_args.kwargs["client_secret"], _SECRET)


class TestPublicClientOnTheWire(unittest.TestCase):
    """A real authlib client built from our registration, against a mock token endpoint.

    Checks what actually reaches the provider: a public client sends ``client_id`` in the body and
    no ``Authorization`` header — on the code exchange, on a refresh, and on revocation — while a
    confidential client keeps authenticating with its secret.
    """

    def setUp(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        self.oauth_mod = oauth_mod
        oauth_mod.reset_oauth()
        self.addCleanup(oauth_mod.reset_oauth)
        self.requests = []

    def _handler(self, request):
        import httpx2

        self.requests.append(request)
        if str(request.url) == _REVOCATION_ENDPOINT:
            return httpx2.Response(200)
        return httpx2.Response(200, json={"access_token": "at", "token_type": "Bearer", "expires_in": 60, "refresh_token": "rt"})

    def _client(self, **config_overrides):
        """Register through ``ensure_client_registered`` and return the authlib client, wired to the mock."""
        from unittest.mock import AsyncMock

        import httpx2

        with _patch_config(self.oauth_mod, **config_overrides):
            self.assertTrue(self.oauth_mod.ensure_client_registered())
        client = self.oauth_mod.get_client()
        metadata = {"token_endpoint": _TOKEN_ENDPOINT, "revocation_endpoint": _REVOCATION_ENDPOINT}
        client.load_server_metadata = AsyncMock(return_value=metadata)
        # Reaches every session authlib builds for this client, including inside
        # fetch_access_token — the call routers/auth.py makes for the code exchange and for a refresh.
        client.client_kwargs["transport"] = httpx2.MockTransport(self._handler)
        return client

    @staticmethod
    def _body(request) -> dict:
        from urllib.parse import parse_qs

        return {key: values[0] for key, values in parse_qs(request.content.decode()).items()}

    def _exchange_refresh_and_revoke(self, client):
        import asyncio

        async def run():
            await client.fetch_access_token(code="the-code", code_verifier="the-verifier", redirect_uri="https://app/callback")
            await client.fetch_access_token(grant_type="refresh_token", refresh_token="rt")
            metadata = await client.load_server_metadata()
            async with client._get_oauth_client(**metadata) as session:
                await session.revoke_token(_REVOCATION_ENDPOINT, token="rt", token_type_hint="refresh_token")

        asyncio.run(run())
        self.assertEqual(len(self.requests), 3)
        return self.requests

    def test_a_public_client_authenticates_with_client_id_only(self):
        client = self._client(OIDC_CLIENT_SECRET=None, OIDC_PUBLIC_CLIENT=True)

        exchange, refresh, revoke = self._exchange_refresh_and_revoke(client)

        for request in (exchange, refresh, revoke):
            self.assertNotIn("authorization", request.headers)
            body = self._body(request)
            self.assertEqual(body["client_id"], "test-client-id")
            self.assertNotIn("client_secret", body)
        self.assertEqual(self._body(exchange)["grant_type"], "authorization_code")
        self.assertEqual(self._body(exchange)["code_verifier"], "the-verifier")
        self.assertEqual(self._body(refresh)["grant_type"], "refresh_token")
        self.assertEqual(self._body(revoke)["token"], "rt")

    def test_a_confidential_client_still_sends_its_secret(self):
        client = self._client()

        for request in self._exchange_refresh_and_revoke(client):
            self.assertTrue(request.headers["authorization"].startswith("Basic "))
            self.assertNotIn("client_secret", self._body(request))


if __name__ == "__main__":
    unittest.main()


class TestOidcClientRegistrationKwargs(unittest.TestCase):
    """PKCE and TLS-verify settings must flow into the registered client kwargs."""

    def test_client_kwargs_include_verify_and_code_challenge(self):
        from unittest.mock import MagicMock, patch

        import mlflow_oidc_auth.oauth as oauth_mod

        with (
            # Registration state is now per provider id rather than one global flag (#315).
            patch.object(oauth_mod, "_registered", {}),
            patch.object(oauth_mod, "_has_required_config", return_value=True),
            patch.object(
                oauth_mod, "_client_settings", return_value={"client_id": "id", "client_secret": "s", "server_metadata_url": "https://idp/.well-known"}
            ),
            patch.object(oauth_mod, "_build_scope", return_value="openid email"),
            patch.object(oauth_mod.oauth, "register") as mock_register,
            patch.object(oauth_mod.config, "OIDC_VERIFY_SSL", False),
            patch.object(oauth_mod.config, "OIDC_CODE_CHALLENGE", "S256"),
        ):
            assert oauth_mod.ensure_oidc_client_registered() is True
            kwargs = mock_register.call_args.kwargs["client_kwargs"]
            assert kwargs["scope"] == "openid email"
            assert kwargs["verify"] is False
            assert kwargs["code_challenge_method"] == "S256"
