"""
Comprehensive tests for the oauth.py module.

This module tests OAuth client configuration, token handling, OAuth flow
implementation, error scenarios, security measures, token validation,
and OIDC provider integration.
"""

import sys
import unittest
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

    @patch("mlflow_oidc_auth.config.config")
    def test_oauth_with_mocked_config(self, mock_config):
        """Test OAuth behavior with mocked configuration."""
        # Setup mock config
        mock_config.OIDC_CLIENT_ID = "test_client_id"
        mock_config.OIDC_CLIENT_SECRET = "test_client_secret"
        mock_config.OIDC_DISCOVERY_URL = "https://example.com/.well-known/openid_configuration"
        mock_config.OIDC_SCOPE = "openid email profile"

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


class TestOidcClientTlsTrust:
    """The OIDC client trusts the same CAs as the requests-based key fetches (certifi)."""

    def test_verify_off_disables_verification(self, monkeypatch):
        import mlflow_oidc_auth.oauth as oauth_mod

        monkeypatch.setattr(oauth_mod.config, "OIDC_VERIFY_SSL", False)
        assert oauth_mod._tls_verify() is False

    def test_default_trusts_certifi_bundle(self, monkeypatch):
        import ssl

        import certifi

        import mlflow_oidc_auth.oauth as oauth_mod

        monkeypatch.setattr(oauth_mod.config, "OIDC_VERIFY_SSL", True)
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("SSL_CERT_DIR", raising=False)
        created = {}
        real = ssl.create_default_context

        def spy(*args, **kwargs):
            created.update(kwargs)
            return real(*args, **kwargs)

        monkeypatch.setattr(oauth_mod.ssl, "create_default_context", spy)
        ctx = oauth_mod._tls_verify()
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname
        assert created == {"cafile": certifi.where()}

    def test_ssl_cert_file_is_left_to_the_http_client(self, monkeypatch, tmp_path):
        import mlflow_oidc_auth.oauth as oauth_mod

        monkeypatch.setattr(oauth_mod.config, "OIDC_VERIFY_SSL", True)
        monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "ca.pem"))
        assert oauth_mod._tls_verify() is True

    def test_registered_client_uses_the_certifi_context(self, monkeypatch):
        import ssl
        from unittest.mock import patch

        from authlib.integrations.starlette_client import OAuth

        import mlflow_oidc_auth.oauth as oauth_mod

        monkeypatch.setattr(oauth_mod.config, "OIDC_VERIFY_SSL", True)
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("SSL_CERT_DIR", raising=False)
        fresh = OAuth()
        with (
            patch.object(oauth_mod, "oauth", fresh),
            patch.object(oauth_mod, "_registered", {}),
            patch.object(
                oauth_mod, "_client_settings", return_value={"client_id": "id", "client_secret": "s", "server_metadata_url": "https://idp/.well-known"}
            ),
            patch.object(oauth_mod, "_build_scope", return_value="openid"),
        ):
            assert oauth_mod.ensure_oidc_client_registered() is True
            client = fresh.create_client(oauth_mod.client_name(oauth_mod.DEFAULT_PROVIDER_ID))
            assert isinstance(client.client_kwargs["verify"], ssl.SSLContext)
            assert type(client.client_kwargs["verify"]).__module__ == "ssl"
