"""
Comprehensive tests for the cache/filesystemcache.py module.

This module tests filesystem cache configuration constants, environment variable parsing,
default value handling, security configurations, error scenarios, and integration
with the application's caching system.
"""

import os
import unittest
from unittest.mock import patch, MagicMock


from mlflow_oidc_auth.cache import filesystemcache


class TestFileSystemCacheModule(unittest.TestCase):
    """Test the filesystem cache module configuration constants and initialization."""

    def setUp(self):
        """Set up test environment."""
        # Store original environment variables to restore later
        self.original_env = dict(os.environ)

    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment variables
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_cache_type_constant(self):
        """Test that CACHE_TYPE constant is correctly set."""
        self.assertEqual(filesystemcache.CACHE_TYPE, "FileSystemCache")

    def test_default_cache_timeout_constant(self):
        """Test CACHE_DEFAULT_TIMEOUT with default value."""
        # Clear the environment variable to test default
        if "CACHE_DEFAULT_TIMEOUT" in os.environ:
            del os.environ["CACHE_DEFAULT_TIMEOUT"]

        # Reload the module to get default value
        import importlib

        importlib.reload(filesystemcache)

        self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, 300)

    def test_custom_cache_timeout_constant(self):
        """Test CACHE_DEFAULT_TIMEOUT with custom environment variable."""
        custom_timeout = "600"

        with patch.dict(os.environ, {"CACHE_DEFAULT_TIMEOUT": custom_timeout}):
            import importlib

            importlib.reload(filesystemcache)

            self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, custom_timeout)

    def test_default_cache_ignore_errors_constant(self):
        """Test CACHE_IGNORE_ERRORS with default value."""
        # Clear the environment variable to test default
        if "CACHE_IGNORE_ERRORS" in os.environ:
            del os.environ["CACHE_IGNORE_ERRORS"]

        # Reload the module to get default value
        import importlib

        importlib.reload(filesystemcache)

        self.assertTrue(filesystemcache.CACHE_IGNORE_ERRORS)

    def test_custom_cache_ignore_errors_constant(self):
        """Test CACHE_IGNORE_ERRORS with custom environment variable."""
        # Test various true values
        true_values = ["true", "True", "TRUE", "1", "t", "T"]

        for true_value in true_values:
            with patch.dict(os.environ, {"CACHE_IGNORE_ERRORS": true_value}):
                import importlib

                importlib.reload(filesystemcache)

                self.assertTrue(filesystemcache.CACHE_IGNORE_ERRORS, f"Should be True for value '{true_value}'")

        # Test various false values
        false_values = ["false", "False", "FALSE", "0", "f", "F", "no", "off"]

        for false_value in false_values:
            with patch.dict(os.environ, {"CACHE_IGNORE_ERRORS": false_value}):
                import importlib

                importlib.reload(filesystemcache)

                self.assertFalse(filesystemcache.CACHE_IGNORE_ERRORS, f"Should be False for value '{false_value}'")

    def test_default_cache_dir_constant(self):
        """Test CACHE_DIR with default value."""
        # Clear the environment variable to test default
        if "CACHE_DIR" in os.environ:
            del os.environ["CACHE_DIR"]

        # Reload the module to get default value
        import importlib

        importlib.reload(filesystemcache)

        self.assertEqual(filesystemcache.CACHE_DIR, "/tmp/flask_cache")

    def test_custom_cache_dir_constant(self):
        """Test CACHE_DIR with custom environment variable."""
        custom_dir = "/custom/cache/directory"

        with patch.dict(os.environ, {"CACHE_DIR": custom_dir}):
            import importlib

            importlib.reload(filesystemcache)

            self.assertEqual(filesystemcache.CACHE_DIR, custom_dir)

    def test_default_cache_threshold_constant(self):
        """Test CACHE_THRESHOLD with default value."""
        # Clear the environment variable to test default
        if "CACHE_THRESHOLD" in os.environ:
            del os.environ["CACHE_THRESHOLD"]

        # Reload the module to get default value
        import importlib

        importlib.reload(filesystemcache)

        self.assertEqual(filesystemcache.CACHE_THRESHOLD, 500)

    def test_custom_cache_threshold_constant(self):
        """Test CACHE_THRESHOLD with custom environment variable."""
        custom_threshold = "1000"

        with patch.dict(os.environ, {"CACHE_THRESHOLD": custom_threshold}):
            import importlib

            importlib.reload(filesystemcache)

            self.assertEqual(filesystemcache.CACHE_THRESHOLD, custom_threshold)

    def test_all_constants_with_custom_values(self):
        """Test all filesystem cache constants with custom environment variables."""
        custom_env = {"CACHE_DEFAULT_TIMEOUT": "1200", "CACHE_IGNORE_ERRORS": "false", "CACHE_DIR": "/test/cache/directory", "CACHE_THRESHOLD": "2000"}

        with patch.dict(os.environ, custom_env):
            import importlib

            importlib.reload(filesystemcache)

            # Verify all custom values are set
            self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, "1200")
            self.assertFalse(filesystemcache.CACHE_IGNORE_ERRORS)
            self.assertEqual(filesystemcache.CACHE_DIR, "/test/cache/directory")
            self.assertEqual(filesystemcache.CACHE_THRESHOLD, "2000")

    def test_environment_variable_precedence(self):
        """Test that environment variables take precedence over defaults."""
        # Set all environment variables to non-default values
        custom_env = {"CACHE_DEFAULT_TIMEOUT": "900", "CACHE_IGNORE_ERRORS": "false", "CACHE_DIR": "/priority/cache/dir", "CACHE_THRESHOLD": "1500"}

        with patch.dict(os.environ, custom_env):
            import importlib

            importlib.reload(filesystemcache)

            # Verify all custom values override defaults
            self.assertNotEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, 300)  # Not default
            self.assertFalse(filesystemcache.CACHE_IGNORE_ERRORS)  # Not default True
            self.assertNotEqual(filesystemcache.CACHE_DIR, "/tmp/flask_cache")  # Not default
            self.assertNotEqual(filesystemcache.CACHE_THRESHOLD, 500)  # Not default

            # Verify actual custom values
            self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, "900")
            self.assertFalse(filesystemcache.CACHE_IGNORE_ERRORS)
            self.assertEqual(filesystemcache.CACHE_DIR, "/priority/cache/dir")
            self.assertEqual(filesystemcache.CACHE_THRESHOLD, "1500")

    def test_empty_environment_variables(self):
        """Test handling of empty environment variables."""
        # Test with empty values (should be used as-is, not converted to defaults)
        empty_env = {"CACHE_DEFAULT_TIMEOUT": "", "CACHE_IGNORE_ERRORS": "", "CACHE_DIR": "", "CACHE_THRESHOLD": ""}

        with patch.dict(os.environ, empty_env):
            import importlib

            importlib.reload(filesystemcache)

            # Empty strings should be preserved for most values
            self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, "")
            self.assertEqual(filesystemcache.CACHE_DIR, "")
            self.assertEqual(filesystemcache.CACHE_THRESHOLD, "")

            # CACHE_IGNORE_ERRORS should be False for empty string
            self.assertFalse(filesystemcache.CACHE_IGNORE_ERRORS)

    def test_module_attributes(self):
        """Test that the module has all expected attributes."""
        expected_attributes = ["CACHE_TYPE", "CACHE_DEFAULT_TIMEOUT", "CACHE_IGNORE_ERRORS", "CACHE_DIR", "CACHE_THRESHOLD"]

        for attr in expected_attributes:
            self.assertTrue(hasattr(filesystemcache, attr), f"Module should have attribute {attr}")

    def test_cache_type_immutable(self):
        """Test that CACHE_TYPE is always 'FileSystemCache' regardless of environment."""
        # CACHE_TYPE should not be affected by environment variables
        # (it's hardcoded in the module)

        with patch.dict(os.environ, {"CACHE_TYPE": "SomeOtherCache"}):
            import importlib

            importlib.reload(filesystemcache)

            # Should still be FileSystemCache
            self.assertEqual(filesystemcache.CACHE_TYPE, "FileSystemCache")

    def test_cache_ignore_errors_boolean_conversion(self):
        """Test CACHE_IGNORE_ERRORS boolean conversion with various values."""
        # Test case-insensitive boolean conversion
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("t", True),
            ("T", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("f", False),
            ("F", False),
            ("no", False),
            ("off", False),
            ("invalid", False),  # Invalid values should be False
            ("", False),  # Empty string should be False
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"CACHE_IGNORE_ERRORS": env_value}):
                import importlib

                importlib.reload(filesystemcache)

                self.assertEqual(filesystemcache.CACHE_IGNORE_ERRORS, expected, f"Value '{env_value}' should result in {expected}")

    def test_security_configuration_scenarios(self):
        """Test security-related cache configuration scenarios."""
        # Test secure filesystem cache configuration
        secure_env = {
            "CACHE_DIR": "/secure/cache/directory",
            "CACHE_IGNORE_ERRORS": "false",  # Don't ignore errors in secure mode
            "CACHE_THRESHOLD": "100",  # Lower threshold for security
            "CACHE_DEFAULT_TIMEOUT": "1800",  # 30 minutes timeout
        }

        with patch.dict(os.environ, secure_env):
            import importlib

            importlib.reload(filesystemcache)

            # Verify secure configuration is preserved
            self.assertEqual(filesystemcache.CACHE_DIR, "/secure/cache/directory")
            self.assertFalse(filesystemcache.CACHE_IGNORE_ERRORS)
            self.assertEqual(filesystemcache.CACHE_THRESHOLD, "100")
            self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, "1800")

    def test_cache_timeout_edge_cases(self):
        """Test cache timeout configuration with edge case values."""
        edge_case_timeouts = ["0", "1", "86400", "604800", "2592000"]  # 0s, 1s, 1day, 1week, 1month

        for timeout in edge_case_timeouts:
            with patch.dict(os.environ, {"CACHE_DEFAULT_TIMEOUT": timeout}):
                import importlib

                importlib.reload(filesystemcache)

                self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, timeout)

    def test_cache_threshold_edge_cases(self):
        """Test cache threshold configuration with edge case values."""
        edge_case_thresholds = ["0", "1", "10000", "100000"]  # Various threshold sizes

        for threshold in edge_case_thresholds:
            with patch.dict(os.environ, {"CACHE_THRESHOLD": threshold}):
                import importlib

                importlib.reload(filesystemcache)

                self.assertEqual(filesystemcache.CACHE_THRESHOLD, threshold)

    def test_cache_directory_variations(self):
        """Test cache directory with various path formats."""
        directory_variations = ["/tmp/cache", "/var/cache/app", "./local_cache", "~/cache", "/opt/app/cache", "/secure/isolated/cache"]

        for cache_dir in directory_variations:
            with patch.dict(os.environ, {"CACHE_DIR": cache_dir}):
                import importlib

                importlib.reload(filesystemcache)

                self.assertEqual(filesystemcache.CACHE_DIR, cache_dir)

    def test_module_reload_behavior(self):
        """Test that module can be safely reloaded with different configurations."""
        # First configuration
        first_config = {"CACHE_DEFAULT_TIMEOUT": "300", "CACHE_DIR": "/tmp/cache1", "CACHE_THRESHOLD": "500"}

        with patch.dict(os.environ, first_config):
            import importlib

            importlib.reload(filesystemcache)

            self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, "300")
            self.assertEqual(filesystemcache.CACHE_DIR, "/tmp/cache1")
            self.assertEqual(filesystemcache.CACHE_THRESHOLD, "500")

        # Second configuration
        second_config = {"CACHE_DEFAULT_TIMEOUT": "600", "CACHE_DIR": "/tmp/cache2", "CACHE_THRESHOLD": "1000"}

        with patch.dict(os.environ, second_config):
            import importlib

            importlib.reload(filesystemcache)

            self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, "600")
            self.assertEqual(filesystemcache.CACHE_DIR, "/tmp/cache2")
            self.assertEqual(filesystemcache.CACHE_THRESHOLD, "1000")

    def test_cache_configuration_isolation(self):
        """Test that cache configuration is isolated between different environments."""
        # Test development configuration
        dev_config = {"CACHE_DIR": "/tmp/dev_cache", "CACHE_IGNORE_ERRORS": "true", "CACHE_THRESHOLD": "100"}

        with patch.dict(os.environ, dev_config):
            import importlib

            importlib.reload(filesystemcache)

            dev_dir = filesystemcache.CACHE_DIR
            dev_ignore_errors = filesystemcache.CACHE_IGNORE_ERRORS
            dev_threshold = filesystemcache.CACHE_THRESHOLD

        # Test production configuration
        prod_config = {"CACHE_DIR": "/var/cache/prod_cache", "CACHE_IGNORE_ERRORS": "false", "CACHE_THRESHOLD": "1000"}

        with patch.dict(os.environ, prod_config):
            import importlib

            importlib.reload(filesystemcache)

            # Verify production config is different from dev
            self.assertNotEqual(filesystemcache.CACHE_DIR, dev_dir)
            self.assertNotEqual(filesystemcache.CACHE_IGNORE_ERRORS, dev_ignore_errors)
            self.assertNotEqual(filesystemcache.CACHE_THRESHOLD, dev_threshold)

            # Verify production config values
            self.assertEqual(filesystemcache.CACHE_DIR, "/var/cache/prod_cache")
            self.assertFalse(filesystemcache.CACHE_IGNORE_ERRORS)
            self.assertEqual(filesystemcache.CACHE_THRESHOLD, "1000")

    def test_cache_data_integrity_configuration(self):
        """Test cache configuration that supports data integrity."""
        # Test configuration that would support data integrity features
        integrity_config = {
            "CACHE_DEFAULT_TIMEOUT": "3600",  # 1 hour timeout
            "CACHE_IGNORE_ERRORS": "false",  # Don't ignore errors for integrity
            "CACHE_DIR": "/integrity/cache",
            "CACHE_THRESHOLD": "200",  # Lower threshold for integrity checks
        }

        with patch.dict(os.environ, integrity_config):
            import importlib

            importlib.reload(filesystemcache)

            # Verify integrity-focused configuration
            self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, "3600")
            self.assertFalse(filesystemcache.CACHE_IGNORE_ERRORS)
            self.assertEqual(filesystemcache.CACHE_DIR, "/integrity/cache")
            self.assertEqual(filesystemcache.CACHE_THRESHOLD, "200")

    def test_cache_performance_configuration(self):
        """Test cache configuration optimized for performance."""
        # Test configuration that would optimize for performance
        performance_config = {
            "CACHE_DEFAULT_TIMEOUT": "60",  # Short timeout for high turnover
            "CACHE_IGNORE_ERRORS": "true",  # Ignore errors for performance
            "CACHE_DIR": "/fast/cache",
            "CACHE_THRESHOLD": "5000",  # High threshold for performance
        }

        with patch.dict(os.environ, performance_config):
            import importlib

            importlib.reload(filesystemcache)

            # Verify performance-focused configuration
            self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, "60")
            self.assertTrue(filesystemcache.CACHE_IGNORE_ERRORS)
            self.assertEqual(filesystemcache.CACHE_DIR, "/fast/cache")
            self.assertEqual(filesystemcache.CACHE_THRESHOLD, "5000")

    def test_cache_fallback_scenarios(self):
        """Test cache configuration for fallback scenarios."""
        # Test that all constants have reasonable defaults for fallback
        # Clear all cache-related environment variables
        cache_env_vars = ["CACHE_DEFAULT_TIMEOUT", "CACHE_IGNORE_ERRORS", "CACHE_DIR", "CACHE_THRESHOLD"]

        for var in cache_env_vars:
            if var in os.environ:
                del os.environ[var]

        import importlib

        importlib.reload(filesystemcache)

        # Verify all defaults are reasonable for fallback scenarios
        self.assertEqual(filesystemcache.CACHE_TYPE, "FileSystemCache")
        self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, 300)  # 5 minutes
        self.assertTrue(filesystemcache.CACHE_IGNORE_ERRORS)  # Ignore errors by default
        self.assertEqual(filesystemcache.CACHE_DIR, "/tmp/flask_cache")
        self.assertEqual(filesystemcache.CACHE_THRESHOLD, 500)  # Reasonable threshold


class TestFileSystemCacheIntegration(unittest.TestCase):
    """Test filesystem cache integration with the application configuration system."""

    def setUp(self):
        """Set up test environment."""
        self.original_env = dict(os.environ)

    def tearDown(self):
        """Clean up test environment."""
        os.environ.clear()
        os.environ.update(self.original_env)

    @patch("mlflow_oidc_auth.config.importlib.import_module")
    def test_cache_module_import_in_config(self, mock_import_module):
        """Test that filesystem cache module can be imported by the config system."""
        # Mock the filesystemcache module
        mock_filesystemcache = MagicMock()
        mock_filesystemcache.CACHE_TYPE = "FileSystemCache"
        mock_filesystemcache.CACHE_DEFAULT_TIMEOUT = "300"
        mock_filesystemcache.CACHE_IGNORE_ERRORS = True
        mock_filesystemcache.CACHE_DIR = "/tmp/flask_cache"
        mock_filesystemcache.CACHE_THRESHOLD = "500"

        mock_import_module.return_value = mock_filesystemcache

        # Test that config can import filesystemcache module
        from mlflow_oidc_auth.config import AppConfig

        with patch.dict(os.environ, {"CACHE_TYPE": "FileSystemCache"}):
            AppConfig()

            # Verify import was attempted
            mock_import_module.assert_called_with("mlflow_oidc_auth.cache.filesystemcache")

    def test_cache_constants_integration_with_config(self):
        """Test that cache constants integrate properly with AppConfig."""
        # Set filesystem cache type and custom values
        cache_env = {
            "CACHE_TYPE": "FileSystemCache",
            "CACHE_DEFAULT_TIMEOUT": "1800",
            "CACHE_IGNORE_ERRORS": "false",
            "CACHE_DIR": "/integration/test/cache",
            "CACHE_THRESHOLD": "750",
        }

        with patch.dict(os.environ, cache_env):
            # Import and reload filesystemcache to pick up environment variables
            import importlib

            importlib.reload(filesystemcache)

            # Verify constants are set correctly
            self.assertEqual(filesystemcache.CACHE_TYPE, "FileSystemCache")
            self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, "1800")
            self.assertFalse(filesystemcache.CACHE_IGNORE_ERRORS)
            self.assertEqual(filesystemcache.CACHE_DIR, "/integration/test/cache")
            self.assertEqual(filesystemcache.CACHE_THRESHOLD, "750")

    def test_cache_error_handling_scenarios(self):
        """Test error handling scenarios for cache configuration."""
        # Test with invalid environment values that might cause issues
        # (Note: filesystemcache.py only reads env vars, doesn't validate them)

        problematic_env = {
            "CACHE_DEFAULT_TIMEOUT": "not-a-number",  # Would cause issues when used
            "CACHE_THRESHOLD": "invalid-threshold",  # Would cause issues when used
            "CACHE_IGNORE_ERRORS": "invalid-boolean",  # Should default to False
        }

        with patch.dict(os.environ, problematic_env):
            import importlib

            importlib.reload(filesystemcache)

            # Module should load without errors (validation happens at usage time)
            self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, "not-a-number")
            self.assertEqual(filesystemcache.CACHE_THRESHOLD, "invalid-threshold")
            self.assertFalse(filesystemcache.CACHE_IGNORE_ERRORS)  # Invalid boolean -> False

    def test_cache_security_isolation(self):
        """Test cache security and data isolation configuration."""
        # Test configuration for security-conscious environments
        secure_env = {
            "CACHE_DIR": "/secure/tenant/cache",  # Tenant isolation
            "CACHE_IGNORE_ERRORS": "false",  # Don't ignore errors in secure mode
            "CACHE_THRESHOLD": "50",  # Low threshold for security
            "CACHE_DEFAULT_TIMEOUT": "900",  # 15 minutes timeout
        }

        with patch.dict(os.environ, secure_env):
            import importlib

            importlib.reload(filesystemcache)

            # Verify security-focused configuration
            self.assertEqual(filesystemcache.CACHE_DIR, "/secure/tenant/cache")
            self.assertFalse(filesystemcache.CACHE_IGNORE_ERRORS)
            self.assertEqual(filesystemcache.CACHE_THRESHOLD, "50")
            self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, "900")

    def test_cache_expiration_configuration(self):
        """Test cache expiration and timeout configuration."""
        # Test various timeout configurations for different use cases
        timeout_scenarios = [
            ("60", "1 minute - high turnover"),
            ("300", "5 minutes - default"),
            ("1800", "30 minutes - medium term"),
            ("3600", "1 hour - long term"),
            ("86400", "24 hours - very long term"),
        ]

        for timeout, description in timeout_scenarios:
            with patch.dict(os.environ, {"CACHE_DEFAULT_TIMEOUT": timeout}):
                import importlib

                importlib.reload(filesystemcache)

                self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, timeout, f"Failed for {description}")

    def test_cache_performance_optimization_config(self):
        """Test cache configuration for performance optimization."""
        # Test configuration optimized for different performance scenarios
        performance_configs = [
            {
                "name": "high_performance",
                "config": {
                    "CACHE_DEFAULT_TIMEOUT": "30",  # Very short timeout
                    "CACHE_IGNORE_ERRORS": "true",  # Ignore errors for speed
                    "CACHE_THRESHOLD": "10000",  # High threshold
                },
            },
            {"name": "balanced", "config": {"CACHE_DEFAULT_TIMEOUT": "300", "CACHE_IGNORE_ERRORS": "true", "CACHE_THRESHOLD": "1000"}},  # Medium timeout
            {
                "name": "conservative",
                "config": {
                    "CACHE_DEFAULT_TIMEOUT": "3600",  # Long timeout
                    "CACHE_IGNORE_ERRORS": "false",  # Don't ignore errors
                    "CACHE_THRESHOLD": "100",  # Low threshold
                },
            },
        ]

        for scenario in performance_configs:
            with patch.dict(os.environ, scenario["config"]):
                import importlib

                importlib.reload(filesystemcache)

                # Verify configuration matches scenario
                self.assertEqual(filesystemcache.CACHE_DEFAULT_TIMEOUT, scenario["config"]["CACHE_DEFAULT_TIMEOUT"])
                expected_ignore_errors = scenario["config"]["CACHE_IGNORE_ERRORS"] == "true"
                self.assertEqual(filesystemcache.CACHE_IGNORE_ERRORS, expected_ignore_errors)
                self.assertEqual(filesystemcache.CACHE_THRESHOLD, scenario["config"]["CACHE_THRESHOLD"])


if __name__ == "__main__":
    unittest.main()
