"""
Comprehensive tests for the config.py module.

This module tests configuration loading, environment variable parsing,
validation logic, default value handling, edge cases, invalid configuration
scenarios, error responses, and security configuration settings.
"""

import os
import unittest
from unittest.mock import patch, MagicMock


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
        self.assertEqual(config.OIDC_ADMIN_GROUP_NAME, ["mlflow-admin"])
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
        }

        with patch.dict(os.environ, test_env):
            config = AppConfig()

            self.assertEqual(config.DEFAULT_MLFLOW_PERMISSION, "READ")
            self.assertEqual(config.SECRET_KEY, "custom-secret-key")
            self.assertEqual(config.OIDC_USERS_DB_URI, "postgresql://user:pass@localhost/db")
            self.assertEqual(config.OIDC_GROUP_NAME, ["group1", "group2", "group3"])
            self.assertEqual(config.OIDC_ADMIN_GROUP_NAME, ["admin-group"])
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
        # Test that a generated SECRET_KEY is properly set and has sufficient length
        if "SECRET_KEY" in os.environ:
            del os.environ["SECRET_KEY"]
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


if __name__ == "__main__":
    unittest.main()
