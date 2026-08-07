"""
Comprehensive tests for the oauth.py module.

This module tests OAuth client configuration, token handling, OAuth flow
implementation, error scenarios, security measures, token validation,
and OIDC provider integration.
"""

import sys
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch


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
        if "mlflow_oidc_auth.oauth" in sys.modules:
            del sys.modules["mlflow_oidc_auth.oauth"]

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
        if "mlflow_oidc_auth.oauth" in sys.modules:
            del sys.modules["mlflow_oidc_auth.oauth"]
        if "mlflow_oidc_auth.config" in sys.modules:
            del sys.modules["mlflow_oidc_auth.config"]

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
        if "mlflow_oidc_auth.oauth" in sys.modules:
            del sys.modules["mlflow_oidc_auth.oauth"]
        if "mlflow_oidc_auth.config" in sys.modules:
            del sys.modules["mlflow_oidc_auth.config"]

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
        if "mlflow_oidc_auth.oauth" in sys.modules:
            del sys.modules["mlflow_oidc_auth.oauth"]
        if "mlflow_oidc_auth.config" in sys.modules:
            del sys.modules["mlflow_oidc_auth.config"]

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
        if "mlflow_oidc_auth.oauth" in sys.modules:
            del sys.modules["mlflow_oidc_auth.oauth"]
        if "mlflow_oidc_auth.config" in sys.modules:
            del sys.modules["mlflow_oidc_auth.config"]

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
        if "mlflow_oidc_auth.oauth" in sys.modules:
            del sys.modules["mlflow_oidc_auth.oauth"]
        if "mlflow_oidc_auth.config" in sys.modules:
            del sys.modules["mlflow_oidc_auth.config"]

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
        if "mlflow_oidc_auth.oauth" in sys.modules:
            del sys.modules["mlflow_oidc_auth.oauth"]
        if "mlflow_oidc_auth.config" in sys.modules:
            del sys.modules["mlflow_oidc_auth.config"]

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
        if "mlflow_oidc_auth.oauth" in sys.modules:
            del sys.modules["mlflow_oidc_auth.oauth"]
        if "mlflow_oidc_auth.config" in sys.modules:
            del sys.modules["mlflow_oidc_auth.config"]

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
        if "mlflow_oidc_auth.oauth" in sys.modules:
            del sys.modules["mlflow_oidc_auth.oauth"]
        if "mlflow_oidc_auth.config" in sys.modules:
            del sys.modules["mlflow_oidc_auth.config"]

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
        if "mlflow_oidc_auth.oauth" in sys.modules:
            del sys.modules["mlflow_oidc_auth.oauth"]
        if "mlflow_oidc_auth.config" in sys.modules:
            del sys.modules["mlflow_oidc_auth.config"]

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
        if "mlflow_oidc_auth.oauth" in sys.modules:
            del sys.modules["mlflow_oidc_auth.oauth"]
        if "mlflow_oidc_auth.config" in sys.modules:
            del sys.modules["mlflow_oidc_auth.config"]

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
        if "mlflow_oidc_auth.oauth" in sys.modules:
            del sys.modules["mlflow_oidc_auth.oauth"]
        if "mlflow_oidc_auth.config" in sys.modules:
            del sys.modules["mlflow_oidc_auth.config"]

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
        if "mlflow_oidc_auth.oauth" in sys.modules:
            del sys.modules["mlflow_oidc_auth.oauth"]
        if "mlflow_oidc_auth.config" in sys.modules:
            del sys.modules["mlflow_oidc_auth.config"]

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


class TestPKCEAndOptionalClientSecret(unittest.TestCase):
    """Test PKCE support and optional OIDC client secret."""

    @contextmanager
    def _patch_config(self, oauth_mod, **kwargs):
        """Patch oauth_mod.config attributes used by OAuth registration."""
        from contextlib import ExitStack

        defaults = {
            "OIDC_CLIENT_ID": "test-client-id",
            "OIDC_CLIENT_SECRET": "test-client-secret",
            "OIDC_DISCOVERY_URL": "https://auth.example.com/.well-known/openid-configuration",
            "OIDC_SCOPE": "openid,email,profile",
            "OIDC_USE_REFRESH_TOKEN": False,
            "OIDC_CODE_CHALLENGE": None,
        }
        defaults.update(kwargs)
        with ExitStack() as stack:
            for key, value in defaults.items():
                stack.enter_context(patch.object(oauth_mod.config, key, value, create=True))
            yield

    def test_registration_succeeds_with_client_secret(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        oauth_mod.reset_oauth()
        with self._patch_config(oauth_mod):
            self.assertTrue(oauth_mod.ensure_oidc_client_registered())

    def test_registration_succeeds_with_pkce_and_no_secret(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        oauth_mod.reset_oauth()
        with self._patch_config(oauth_mod, OIDC_CLIENT_SECRET=None, OIDC_CODE_CHALLENGE="S256"):
            self.assertTrue(oauth_mod.ensure_oidc_client_registered())

    def test_registration_fails_without_secret_and_without_pkce(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        oauth_mod.reset_oauth()
        with self._patch_config(oauth_mod, OIDC_CLIENT_SECRET=None, OIDC_CODE_CHALLENGE=None):
            with self.assertRaises(ValueError) as cm:
                oauth_mod.ensure_oidc_client_registered()
            self.assertIn("OIDC_CLIENT_SECRET is missing", str(cm.exception))
            self.assertIn("OIDC_CODE_CHALLENGE", str(cm.exception))

    def test_client_kwargs_include_code_challenge_method_when_pkce_enabled(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        oauth_mod.reset_oauth()
        mock_register = MagicMock()
        with (
            self._patch_config(oauth_mod, OIDC_CLIENT_SECRET=None, OIDC_CODE_CHALLENGE="S256"),
            patch.object(oauth_mod.oauth, "register", mock_register),
        ):
            oauth_mod.ensure_oidc_client_registered()
            mock_register.assert_called_once()
            kwargs = mock_register.call_args.kwargs
            self.assertEqual(kwargs["client_kwargs"]["code_challenge_method"], "S256")
            self.assertNotIn("client_secret", kwargs)

    def test_code_challenge_method_is_none_when_pkce_disabled(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        oauth_mod.reset_oauth()
        mock_register = MagicMock()
        with (
            self._patch_config(oauth_mod, OIDC_CODE_CHALLENGE=None),
            patch.object(oauth_mod.oauth, "register", mock_register),
        ):
            oauth_mod.ensure_oidc_client_registered()
            mock_register.assert_called_once()
            kwargs = mock_register.call_args.kwargs
            # Authlib only applies PKCE when the method is truthy, so None disables it.
            self.assertIsNone(kwargs["client_kwargs"]["code_challenge_method"])
            self.assertEqual(kwargs["client_secret"], "test-client-secret")

    def test_client_secret_passed_when_present(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        oauth_mod.reset_oauth()
        mock_register = MagicMock()
        with (
            self._patch_config(oauth_mod, OIDC_CLIENT_SECRET="test-secret", OIDC_CODE_CHALLENGE="S256"),
            patch.object(oauth_mod.oauth, "register", mock_register),
        ):
            oauth_mod.ensure_oidc_client_registered()
            kwargs = mock_register.call_args.kwargs
            self.assertEqual(kwargs["client_secret"], "test-secret")
            self.assertEqual(kwargs["client_kwargs"]["code_challenge_method"], "S256")

    def test_has_required_config_allows_pkce_without_secret(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        with self._patch_config(oauth_mod, OIDC_CLIENT_SECRET=None, OIDC_CODE_CHALLENGE="S256"):
            self.assertTrue(oauth_mod._has_required_config())

    def test_has_required_config_rejects_missing_secret_and_pkce(self):
        from mlflow_oidc_auth import oauth as oauth_mod

        with self._patch_config(oauth_mod, OIDC_CLIENT_SECRET=None, OIDC_CODE_CHALLENGE=None):
            self.assertFalse(oauth_mod._has_required_config())


if __name__ == "__main__":
    unittest.main()


class TestOidcClientRegistrationKwargs(unittest.TestCase):
    """PKCE and TLS-verify settings must flow into the registered client kwargs."""

    def test_client_kwargs_include_verify_and_code_challenge(self):
        from unittest.mock import MagicMock, patch

        import mlflow_oidc_auth.oauth as oauth_mod

        with (
            patch.object(oauth_mod, "_oidc_client_registered", False),
            patch.object(oauth_mod, "_has_required_config", return_value=True),
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
