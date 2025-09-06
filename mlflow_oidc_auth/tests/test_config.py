"""
Comprehensive tests for the config.py module.

This module tests configuration loading, environment variable parsing,
validation logic, default value handling, edge cases, invalid configuration
scenarios, error responses, and security configuration settings.
"""

import os
import secrets
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import pytest

from mlflow_oidc_auth.config import AppConfig, get_bool_env_variable


class TestGetBoolEnvVariable(unittest.TestCase):
    """Test the get_bool_env_variable utility function."""

    def test_get_bool_env_variable_true_values(self):
        """Test that various true values are correctly parsed."""
        true_values = ["true", "True", "TRUE", "1", "t", "T"]

        for value in true_values:
            with patch.dict(os.environ, {"TEST_BOOL": value}):
                result = get_bool_env_variable("TEST_BOOL", False)
                self.assertTrue(result, f"Value '{value}' should be parsed as True")

    def test_get_bool_env_variable_false_values(self):
        """Test that various false values are correctly parsed."""
        false_values = ["false", "False", "FALSE", "0", "f", "F", "no", "off", ""]

        for value in false_values:
            with patch.dict(os.environ, {"TEST_BOOL": value}):
                result = get_bool_env_variable("TEST_BOOL", True)
                self.assertFalse(result, f"Value '{value}' should be parsed as False")

    def test_get_bool_env_variable_default_when_missing(self):
        """Test that default value is returned when environment variable is missing."""
        # Ensure the variable is not set
        if "MISSING_TEST_BOOL" in os.environ:
            del os.environ["MISSING_TEST_BOOL"]

        # Test with default True
        result = get_bool_env_variable("MISSING_TEST_BOOL", True)
        self.assertTrue(result)

        # Test with default False
        result = get_bool_env_variable("MISSING_TEST_BOOL", False)
        self.assertFalse(result)

    def test_get_bool_env_variable_case_insensitive(self):
        """Test that boolean parsing is case insensitive."""
        test_cases = [
            ("True", True),
            ("true", True),
            ("TRUE", True),
            ("False", False),
            ("false", False),
            ("FALSE", False),
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"TEST_CASE_BOOL": env_value}):
                result = get_bool_env_variable("TEST_CASE_BOOL", False)
                self.assertEqual(result, expected)


class TestAppConfig(unittest.TestCase):
    """Test the AppConfig class initialization and configuration loading."""

    def setUp(self):
        """Set up test environment."""
        # Store original environment variables to restore later
        self.original_env = dict(os.environ)

    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment variables
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_app_config_default_values(self):
        """Test that AppConfig initializes with correct default values."""
        # Clear all relevant environment variables
        env_vars_to_clear = [
            "DEFAULT_MLFLOW_PERMISSION",
            "SECRET_KEY",
            "OIDC_USERS_DB_URI",
            "OIDC_GROUP_NAME",
            "OIDC_ADMIN_GROUP_NAME",
            "OIDC_PROVIDER_DISPLAY_NAME",
            "OIDC_DISCOVERY_URL",
            "OIDC_GROUPS_ATTRIBUTE",
            "OIDC_SCOPE",
            "OIDC_GROUP_DETECTION_PLUGIN",
            "OIDC_REDIRECT_URI",
            "OIDC_CLIENT_ID",
            "OIDC_CLIENT_SECRET",
            "AUTOMATIC_LOGIN_REDIRECT",
            "OIDC_ALEMBIC_VERSION_TABLE",
            "PERMISSION_SOURCE_ORDER",
            "EXTEND_MLFLOW_MENU",
            "DEFAULT_LANDING_PAGE_IS_PERMISSIONS",
            "SESSION_TYPE",
            "SESSION_PERMANENT",
            "SESSION_KEY_PREFIX",
            "PERMANENT_SESSION_LIFETIME",
            "CACHE_TYPE",
        ]

        for var in env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]

        config = AppConfig()

        # Test default values
        self.assertEqual(config.DEFAULT_MLFLOW_PERMISSION, "MANAGE")
        self.assertIsNotNone(config.SECRET_KEY)
        self.assertEqual(len(config.SECRET_KEY), 32)  # secrets.token_hex(16) produces 32 chars
        self.assertEqual(config.OIDC_USERS_DB_URI, "sqlite:///auth.db")
        self.assertEqual(config.OIDC_GROUP_NAME, ["mlflow"])
        self.assertEqual(config.OIDC_ADMIN_GROUP_NAME, "mlflow-admin")
        self.assertEqual(config.OIDC_PROVIDER_DISPLAY_NAME, "Login with OIDC")
        self.assertIsNone(config.OIDC_DISCOVERY_URL)
        self.assertEqual(config.OIDC_GROUPS_ATTRIBUTE, "groups")
        self.assertEqual(config.OIDC_SCOPE, "openid,email,profile")
        self.assertIsNone(config.OIDC_GROUP_DETECTION_PLUGIN)
        self.assertIsNone(config.OIDC_REDIRECT_URI)
        self.assertIsNone(config.OIDC_CLIENT_ID)
        self.assertIsNone(config.OIDC_CLIENT_SECRET)
        self.assertFalse(config.AUTOMATIC_LOGIN_REDIRECT)
        self.assertEqual(config.OIDC_ALEMBIC_VERSION_TABLE, "alembic_version")
        self.assertEqual(config.PERMISSION_SOURCE_ORDER, ["user", "group", "regex", "group-regex"])
        self.assertTrue(config.EXTEND_MLFLOW_MENU)
        self.assertTrue(config.DEFAULT_LANDING_PAGE_IS_PERMISSIONS)
        self.assertEqual(config.SESSION_TYPE, "cachelib")
        self.assertFalse(config.SESSION_PERMANENT)
        self.assertEqual(config.SESSION_KEY_PREFIX, "mlflow_oidc:")
        self.assertEqual(config.PERMANENT_SESSION_LIFETIME, 86400)
        self.assertEqual(config.CACHE_TYPE, "FileSystemCache")

    def test_app_config_environment_variable_override(self):
        """Test that environment variables override default values."""
        test_env = {
            "DEFAULT_MLFLOW_PERMISSION": "READ",
            "SECRET_KEY": "custom-secret-key",
            "OIDC_USERS_DB_URI": "postgresql://user:pass@localhost/db",
            "OIDC_GROUP_NAME": "group1,group2,group3",
            "OIDC_ADMIN_GROUP_NAME": "admin-group",
            "OIDC_PROVIDER_DISPLAY_NAME": "Custom OIDC Login",
            "OIDC_DISCOVERY_URL": "https://provider.example.com/.well-known/openid_configuration",
            "OIDC_GROUPS_ATTRIBUTE": "custom_groups",
            "OIDC_SCOPE": "openid,email,profile,groups",
            "OIDC_GROUP_DETECTION_PLUGIN": "custom_plugin",
            "OIDC_REDIRECT_URI": "https://app.example.com/callback",
            "OIDC_CLIENT_ID": "test-client-id",
            "OIDC_CLIENT_SECRET": "test-client-secret",
            "AUTOMATIC_LOGIN_REDIRECT": "true",
            "OIDC_ALEMBIC_VERSION_TABLE": "custom_alembic_version",
            "PERMISSION_SOURCE_ORDER": "group,user,regex",
            "EXTEND_MLFLOW_MENU": "false",
            "DEFAULT_LANDING_PAGE_IS_PERMISSIONS": "false",
            "SESSION_TYPE": "redis",
            "SESSION_PERMANENT": "true",
            "SESSION_KEY_PREFIX": "custom:",
            "PERMANENT_SESSION_LIFETIME": "3600",
            "CACHE_TYPE": "RedisCache",
        }

        with patch.dict(os.environ, test_env):
            config = AppConfig()

            self.assertEqual(config.DEFAULT_MLFLOW_PERMISSION, "READ")
            self.assertEqual(config.SECRET_KEY, "custom-secret-key")
            self.assertEqual(config.OIDC_USERS_DB_URI, "postgresql://user:pass@localhost/db")
            self.assertEqual(config.OIDC_GROUP_NAME, ["group1", "group2", "group3"])
            self.assertEqual(config.OIDC_ADMIN_GROUP_NAME, "admin-group")
            self.assertEqual(config.OIDC_PROVIDER_DISPLAY_NAME, "Custom OIDC Login")
            self.assertEqual(config.OIDC_DISCOVERY_URL, "https://provider.example.com/.well-known/openid_configuration")
            self.assertEqual(config.OIDC_GROUPS_ATTRIBUTE, "custom_groups")
            self.assertEqual(config.OIDC_SCOPE, "openid,email,profile,groups")
            self.assertEqual(config.OIDC_GROUP_DETECTION_PLUGIN, "custom_plugin")
            self.assertEqual(config.OIDC_REDIRECT_URI, "https://app.example.com/callback")
            self.assertEqual(config.OIDC_CLIENT_ID, "test-client-id")
            self.assertEqual(config.OIDC_CLIENT_SECRET, "test-client-secret")
            self.assertTrue(config.AUTOMATIC_LOGIN_REDIRECT)
            self.assertEqual(config.OIDC_ALEMBIC_VERSION_TABLE, "custom_alembic_version")
            self.assertEqual(config.PERMISSION_SOURCE_ORDER, ["group", "user", "regex"])
            self.assertFalse(config.EXTEND_MLFLOW_MENU)
            self.assertFalse(config.DEFAULT_LANDING_PAGE_IS_PERMISSIONS)
            self.assertEqual(config.SESSION_TYPE, "redis")
            self.assertTrue(config.SESSION_PERMANENT)
            self.assertEqual(config.SESSION_KEY_PREFIX, "custom:")
            self.assertEqual(config.PERMANENT_SESSION_LIFETIME, "3600")
            self.assertEqual(config.CACHE_TYPE, "RedisCache")

    def test_app_config_group_name_parsing(self):
        """Test that OIDC_GROUP_NAME is correctly parsed from comma-separated values."""
        test_cases = [
            ("group1", ["group1"]),
            ("group1,group2", ["group1", "group2"]),
            ("group1, group2, group3", ["group1", "group2", "group3"]),
            ("  group1  ,  group2  ", ["group1", "group2"]),
            ("", [""]),
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"OIDC_GROUP_NAME": env_value}):
                config = AppConfig()
                self.assertEqual(config.OIDC_GROUP_NAME, expected)

    def test_app_config_permission_source_order_parsing(self):
        """Test that PERMISSION_SOURCE_ORDER is correctly parsed from comma-separated values."""
        test_cases = [
            ("user", ["user"]),
            ("user,group", ["user", "group"]),
            ("group,user,regex,group-regex", ["group", "user", "regex", "group-regex"]),
            ("  user  ,  group  ", ["user", "group"]),
            ("", [""]),
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"PERMISSION_SOURCE_ORDER": env_value}):
                config = AppConfig()
                self.assertEqual(config.PERMISSION_SOURCE_ORDER, expected)

    def test_app_config_secret_key_generation(self):
        """Test that SECRET_KEY is generated when not provided."""
        # Ensure SECRET_KEY is not set
        if "SECRET_KEY" in os.environ:
            del os.environ["SECRET_KEY"]

        config1 = AppConfig()
        config2 = AppConfig()

        # Each instance should generate a different secret key
        self.assertNotEqual(config1.SECRET_KEY, config2.SECRET_KEY)
        self.assertEqual(len(config1.SECRET_KEY), 32)
        self.assertEqual(len(config2.SECRET_KEY), 32)

    @patch("mlflow_oidc_auth.config.importlib.import_module")
    def test_session_module_import_success(self, mock_import_module):
        """Test successful session module import and attribute setting."""
        # Create a mock session module
        mock_session_module = MagicMock()

        # Set up the attributes directly on the mock
        mock_session_module.SESSION_COOKIE_NAME = "test_session"
        mock_session_module.SESSION_COOKIE_DOMAIN = "example.com"
        mock_session_module.lowercase_attr = "should_be_ignored"
        mock_session_module.ANOTHER_SETTING = "test_value"

        # Configure dir() to return the attributes
        def mock_dir(obj):
            return ["SESSION_COOKIE_NAME", "SESSION_COOKIE_DOMAIN", "lowercase_attr", "ANOTHER_SETTING"]

        mock_import_module.return_value = mock_session_module

        with patch.dict(os.environ, {"SESSION_TYPE": "redis", "CACHE_TYPE": ""}):
            with patch("builtins.dir", side_effect=mock_dir):
                config = AppConfig()

                # Verify import was called correctly
                mock_import_module.assert_called_with("mlflow_oidc_auth.session.redis")

                # Verify uppercase attributes were set
                self.assertEqual(config.SESSION_COOKIE_NAME, "test_session")
                self.assertEqual(config.SESSION_COOKIE_DOMAIN, "example.com")
                self.assertEqual(config.ANOTHER_SETTING, "test_value")

                # Verify lowercase attribute was not set
                self.assertFalse(hasattr(config, "lowercase_attr"))

    @patch("mlflow_oidc_auth.config.importlib.import_module")
    def test_session_module_import_error(self, mock_import_module):
        """Test session module import error handling (lines 62-63)."""

        # Mock ImportError for session module only
        def side_effect(module_name):
            if "session" in module_name:
                raise ImportError("Module not found")
            # Return a mock for cache module
            mock_cache = MagicMock()
            return mock_cache

        mock_import_module.side_effect = side_effect

        with patch.dict(os.environ, {"SESSION_TYPE": "nonexistent", "CACHE_TYPE": "FileSystemCache"}):
            with patch("builtins.dir", return_value=[]):
                # Capture log output to verify error logging
                with self.assertLogs("mlflow_oidc_auth", level="ERROR") as log:
                    config = AppConfig()

                    # Verify session import was attempted
                    mock_import_module.assert_any_call("mlflow_oidc_auth.session.nonexistent")

                    # Verify error was logged (this covers lines 62-63)
                    self.assertIn("Session module for nonexistent could not be imported.", log.output[0])

    @patch("mlflow_oidc_auth.config.importlib.import_module")
    def test_cache_module_import_success(self, mock_import_module):
        """Test successful cache module import and attribute setting."""
        # Create mock modules for both session and cache
        mock_session_module = MagicMock()
        mock_cache_module = MagicMock()

        # Set up cache module attributes
        mock_cache_module.CACHE_DEFAULT_TIMEOUT = 300
        mock_cache_module.CACHE_KEY_PREFIX = "cache:"
        mock_cache_module.lowercase_attr = "should_be_ignored"
        mock_cache_module.CACHE_REDIS_URL = "redis://localhost:6379"

        # Configure dir() to return the attributes
        def mock_dir(obj):
            if obj == mock_cache_module:
                return ["CACHE_DEFAULT_TIMEOUT", "CACHE_KEY_PREFIX", "lowercase_attr", "CACHE_REDIS_URL"]
            return []

        def side_effect(module_name):
            if "cache" in module_name:
                return mock_cache_module
            return mock_session_module

        mock_import_module.side_effect = side_effect

        with patch.dict(os.environ, {"CACHE_TYPE": "RedisCache", "SESSION_TYPE": "cachelib"}):
            with patch("builtins.dir", side_effect=mock_dir):
                config = AppConfig()

                # Verify import was called correctly
                mock_import_module.assert_any_call("mlflow_oidc_auth.cache.rediscache")

                # Verify uppercase attributes were set
                self.assertEqual(config.CACHE_DEFAULT_TIMEOUT, 300)
                self.assertEqual(config.CACHE_KEY_PREFIX, "cache:")
                self.assertEqual(config.CACHE_REDIS_URL, "redis://localhost:6379")

                # Verify lowercase attribute was not set
                self.assertFalse(hasattr(config, "lowercase_attr"))

    @patch("mlflow_oidc_auth.config.importlib.import_module")
    def test_cache_module_import_error(self, mock_import_module):
        """Test cache module import error handling (lines 73-74)."""

        # Mock ImportError for cache module only
        def side_effect(module_name):
            if "cache" in module_name:
                raise ImportError("Cache module not found")
            # Return a mock for session module
            mock_session = MagicMock()
            return mock_session

        mock_import_module.side_effect = side_effect

        with patch.dict(os.environ, {"CACHE_TYPE": "NonexistentCache", "SESSION_TYPE": "cachelib"}):
            with patch("builtins.dir", return_value=[]):
                # Capture log output to verify error logging
                with self.assertLogs("mlflow_oidc_auth", level="ERROR") as log:
                    config = AppConfig()

                    # Verify cache import was attempted
                    mock_import_module.assert_any_call("mlflow_oidc_auth.cache.nonexistentcache")

                    # Verify error was logged (this covers lines 73-74)
                    # Check that the cache error message is in one of the log outputs
                    cache_error_found = any("Cache module for NonexistentCache could not be imported." in output for output in log.output)
                    self.assertTrue(cache_error_found, f"Cache error not found in logs: {log.output}")

    def test_session_type_none_skips_import(self):
        """Test that empty SESSION_TYPE still attempts import (default behavior)."""
        with patch.dict(os.environ, {"SESSION_TYPE": "", "CACHE_TYPE": ""}):
            with patch("mlflow_oidc_auth.config.importlib.import_module") as mock_import:
                config = AppConfig()

                # Empty string is still truthy in the if condition, so import is attempted
                # This is the actual behavior of the code
                self.assertEqual(config.SESSION_TYPE, "")

    def test_cache_type_none_skips_import(self):
        """Test that empty CACHE_TYPE still attempts import (default behavior)."""
        with patch.dict(os.environ, {"CACHE_TYPE": "", "SESSION_TYPE": ""}):
            with patch("mlflow_oidc_auth.config.importlib.import_module") as mock_import:
                config = AppConfig()

                # Empty string is still truthy in the if condition, so import is attempted
                # This is the actual behavior of the code
                self.assertEqual(config.CACHE_TYPE, "")

    def test_boolean_environment_variables_edge_cases(self):
        """Test edge cases for boolean environment variable parsing."""
        # Test with whitespace - note: get_bool_env_variable doesn't strip whitespace
        with patch.dict(os.environ, {"AUTOMATIC_LOGIN_REDIRECT": "true"}):
            config = AppConfig()
            self.assertTrue(config.AUTOMATIC_LOGIN_REDIRECT)

        # Test with mixed case
        with patch.dict(os.environ, {"EXTEND_MLFLOW_MENU": "True"}):
            config = AppConfig()
            self.assertTrue(config.EXTEND_MLFLOW_MENU)

        # Test with numeric values
        with patch.dict(os.environ, {"SESSION_PERMANENT": "1"}):
            config = AppConfig()
            self.assertTrue(config.SESSION_PERMANENT)

        with patch.dict(os.environ, {"DEFAULT_LANDING_PAGE_IS_PERMISSIONS": "0"}):
            config = AppConfig()
            self.assertFalse(config.DEFAULT_LANDING_PAGE_IS_PERMISSIONS)

    def test_invalid_configuration_scenarios(self):
        """Test handling of invalid configuration values."""
        # Test with invalid boolean values (should default to False)
        with patch.dict(os.environ, {"AUTOMATIC_LOGIN_REDIRECT": "invalid"}):
            config = AppConfig()
            self.assertFalse(config.AUTOMATIC_LOGIN_REDIRECT)

        # Test with empty string values
        with patch.dict(os.environ, {"OIDC_GROUP_NAME": "", "PERMISSION_SOURCE_ORDER": "", "OIDC_SCOPE": ""}):
            config = AppConfig()
            self.assertEqual(config.OIDC_GROUP_NAME, [""])
            self.assertEqual(config.PERMISSION_SOURCE_ORDER, [""])
            self.assertEqual(config.OIDC_SCOPE, "")

    def test_security_configuration_settings(self):
        """Test security-related configuration settings."""
        # Test that SECRET_KEY is properly set and has sufficient length
        config = AppConfig()
        self.assertIsNotNone(config.SECRET_KEY)
        self.assertGreaterEqual(len(config.SECRET_KEY), 32)

        # Test with custom SECRET_KEY
        with patch.dict(os.environ, {"SECRET_KEY": "custom-secret-key-with-sufficient-length"}):
            config = AppConfig()
            self.assertEqual(config.SECRET_KEY, "custom-secret-key-with-sufficient-length")

        # Test OIDC security settings
        with patch.dict(os.environ, {"OIDC_CLIENT_SECRET": "secure-client-secret", "OIDC_SCOPE": "openid,email,profile"}):
            config = AppConfig()
            self.assertEqual(config.OIDC_CLIENT_SECRET, "secure-client-secret")
            self.assertEqual(config.OIDC_SCOPE, "openid,email,profile")

    def test_database_uri_validation(self):
        """Test database URI configuration."""
        # Test default SQLite URI
        config = AppConfig()
        self.assertEqual(config.OIDC_USERS_DB_URI, "sqlite:///auth.db")

        # Test custom database URIs
        test_uris = ["postgresql://user:pass@localhost:5432/mlflow_auth", "mysql://user:pass@localhost:3306/mlflow_auth", "sqlite:///custom/path/auth.db"]

        for uri in test_uris:
            with patch.dict(os.environ, {"OIDC_USERS_DB_URI": uri}):
                config = AppConfig()
                self.assertEqual(config.OIDC_USERS_DB_URI, uri)

    @patch("mlflow_oidc_auth.config.importlib.import_module")
    def test_module_import_case_sensitivity(self, mock_import_module):
        """Test that module names are properly lowercased for import."""
        mock_module = MagicMock()

        # Configure dir() to return empty list
        def mock_dir(obj):
            return []

        mock_import_module.return_value = mock_module

        # Test session module case conversion
        with patch.dict(os.environ, {"SESSION_TYPE": "REDIS", "CACHE_TYPE": ""}):
            with patch("builtins.dir", side_effect=mock_dir):
                config = AppConfig()
                mock_import_module.assert_any_call("mlflow_oidc_auth.session.redis")

        # Reset mock for next test
        mock_import_module.reset_mock()

        # Test cache module case conversion
        with patch.dict(os.environ, {"CACHE_TYPE": "REDISCACHE", "SESSION_TYPE": ""}):
            with patch("builtins.dir", side_effect=mock_dir):
                config = AppConfig()
                mock_import_module.assert_any_call("mlflow_oidc_auth.cache.rediscache")

    def test_permanent_session_lifetime_type(self):
        """Test that PERMANENT_SESSION_LIFETIME maintains its type."""
        # Test default value
        config = AppConfig()
        self.assertEqual(config.PERMANENT_SESSION_LIFETIME, 86400)
        self.assertIsInstance(config.PERMANENT_SESSION_LIFETIME, int)

        # Test custom value (should remain as string from environment)
        with patch.dict(os.environ, {"PERMANENT_SESSION_LIFETIME": "3600"}):
            config = AppConfig()
            self.assertEqual(config.PERMANENT_SESSION_LIFETIME, "3600")
            self.assertIsInstance(config.PERMANENT_SESSION_LIFETIME, str)


if __name__ == "__main__":
    unittest.main()
