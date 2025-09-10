"""
Comprehensive tests for the cache/rediscache.py module.

This module tests Redis cache configuration constants, environment variable parsing,
default value handling, security configurations, error scenarios, and integration
with the application's caching system.
"""

import os
import unittest
from unittest.mock import patch, MagicMock


from mlflow_oidc_auth.cache import rediscache


class TestRedisCacheModule(unittest.TestCase):
    """Test the Redis cache module configuration constants and initialization."""

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
        self.assertEqual(rediscache.CACHE_TYPE, "RedisCache")

    def test_default_cache_timeout_constant(self):
        """Test CACHE_DEFAULT_TIMEOUT with default value."""
        # Clear the environment variable to test default
        if "CACHE_DEFAULT_TIMEOUT" in os.environ:
            del os.environ["CACHE_DEFAULT_TIMEOUT"]

        # Reload the module to get default value
        import importlib

        importlib.reload(rediscache)

        self.assertEqual(rediscache.CACHE_DEFAULT_TIMEOUT, 300)

    def test_custom_cache_timeout_constant(self):
        """Test CACHE_DEFAULT_TIMEOUT with custom environment variable."""
        custom_timeout = "600"

        with patch.dict(os.environ, {"CACHE_DEFAULT_TIMEOUT": custom_timeout}):
            import importlib

            importlib.reload(rediscache)

            self.assertEqual(rediscache.CACHE_DEFAULT_TIMEOUT, custom_timeout)

    def test_default_cache_key_prefix_constant(self):
        """Test CACHE_KEY_PREFIX with default value."""
        # Clear the environment variable to test default
        if "CACHE_KEY_PREFIX" in os.environ:
            del os.environ["CACHE_KEY_PREFIX"]

        # Reload the module to get default value
        import importlib

        importlib.reload(rediscache)

        self.assertEqual(rediscache.CACHE_KEY_PREFIX, "mlflow_oidc:")

    def test_custom_cache_key_prefix_constant(self):
        """Test CACHE_KEY_PREFIX with custom environment variable."""
        custom_prefix = "custom_app:"

        with patch.dict(os.environ, {"CACHE_KEY_PREFIX": custom_prefix}):
            import importlib

            importlib.reload(rediscache)

            self.assertEqual(rediscache.CACHE_KEY_PREFIX, custom_prefix)

    def test_default_redis_host_constant(self):
        """Test CACHE_REDIS_HOST with default value."""
        # Clear the environment variable to test default
        if "CACHE_REDIS_HOST" in os.environ:
            del os.environ["CACHE_REDIS_HOST"]

        # Reload the module to get default value
        import importlib

        importlib.reload(rediscache)

        self.assertEqual(rediscache.CACHE_REDIS_HOST, "localhost")

    def test_custom_redis_host_constant(self):
        """Test CACHE_REDIS_HOST with custom environment variable."""
        custom_host = "redis.example.com"

        with patch.dict(os.environ, {"CACHE_REDIS_HOST": custom_host}):
            import importlib

            importlib.reload(rediscache)

            self.assertEqual(rediscache.CACHE_REDIS_HOST, custom_host)

    def test_default_redis_port_constant(self):
        """Test CACHE_REDIS_PORT with default value."""
        # Clear the environment variable to test default
        if "CACHE_REDIS_PORT" in os.environ:
            del os.environ["CACHE_REDIS_PORT"]

        # Reload the module to get default value
        import importlib

        importlib.reload(rediscache)

        self.assertEqual(rediscache.CACHE_REDIS_PORT, 6379)

    def test_custom_redis_port_constant(self):
        """Test CACHE_REDIS_PORT with custom environment variable."""
        custom_port = "6380"

        with patch.dict(os.environ, {"CACHE_REDIS_PORT": custom_port}):
            import importlib

            importlib.reload(rediscache)

            self.assertEqual(rediscache.CACHE_REDIS_PORT, custom_port)

    def test_default_redis_password_constant(self):
        """Test CACHE_REDIS_PASSWORD with default value (None)."""
        # Clear the environment variable to test default
        if "CACHE_REDIS_PASSWORD" in os.environ:
            del os.environ["CACHE_REDIS_PASSWORD"]

        # Reload the module to get default value
        import importlib

        importlib.reload(rediscache)

        self.assertIsNone(rediscache.CACHE_REDIS_PASSWORD)

    def test_custom_redis_password_constant(self):
        """Test CACHE_REDIS_PASSWORD with custom environment variable."""
        custom_password = "secure-redis-password"

        with patch.dict(os.environ, {"CACHE_REDIS_PASSWORD": custom_password}):
            import importlib

            importlib.reload(rediscache)

            self.assertEqual(rediscache.CACHE_REDIS_PASSWORD, custom_password)

    def test_default_redis_db_constant(self):
        """Test CACHE_REDIS_DB with default value."""
        # Clear the environment variable to test default
        if "CACHE_REDIS_DB" in os.environ:
            del os.environ["CACHE_REDIS_DB"]

        # Reload the module to get default value
        import importlib

        importlib.reload(rediscache)

        self.assertEqual(rediscache.CACHE_REDIS_DB, 4)

    def test_custom_redis_db_constant(self):
        """Test CACHE_REDIS_DB with custom environment variable."""
        custom_db = "2"

        with patch.dict(os.environ, {"CACHE_REDIS_DB": custom_db}):
            import importlib

            importlib.reload(rediscache)

            self.assertEqual(rediscache.CACHE_REDIS_DB, custom_db)

    def test_all_constants_with_custom_values(self):
        """Test all Redis cache constants with custom environment variables."""
        custom_env = {
            "CACHE_DEFAULT_TIMEOUT": "1200",
            "CACHE_KEY_PREFIX": "test_app:",
            "CACHE_REDIS_HOST": "test-redis.example.com",
            "CACHE_REDIS_PORT": "6381",
            "CACHE_REDIS_PASSWORD": "test-password-123",
            "CACHE_REDIS_DB": "5",
        }

        with patch.dict(os.environ, custom_env):
            import importlib

            importlib.reload(rediscache)

            # Verify all custom values are set
            self.assertEqual(rediscache.CACHE_DEFAULT_TIMEOUT, "1200")
            self.assertEqual(rediscache.CACHE_KEY_PREFIX, "test_app:")
            self.assertEqual(rediscache.CACHE_REDIS_HOST, "test-redis.example.com")
            self.assertEqual(rediscache.CACHE_REDIS_PORT, "6381")
            self.assertEqual(rediscache.CACHE_REDIS_PASSWORD, "test-password-123")
            self.assertEqual(rediscache.CACHE_REDIS_DB, "5")

    def test_environment_variable_precedence(self):
        """Test that environment variables take precedence over defaults."""
        # Set all environment variables to non-default values
        custom_env = {
            "CACHE_DEFAULT_TIMEOUT": "900",
            "CACHE_KEY_PREFIX": "priority_app:",
            "CACHE_REDIS_HOST": "priority-redis.example.com",
            "CACHE_REDIS_PORT": "6382",
            "CACHE_REDIS_PASSWORD": "priority-password",
            "CACHE_REDIS_DB": "8",
        }

        with patch.dict(os.environ, custom_env):
            import importlib

            importlib.reload(rediscache)

            # Verify all custom values override defaults
            self.assertNotEqual(rediscache.CACHE_DEFAULT_TIMEOUT, 300)  # Not default
            self.assertNotEqual(rediscache.CACHE_KEY_PREFIX, "mlflow_oidc:")  # Not default
            self.assertNotEqual(rediscache.CACHE_REDIS_HOST, "localhost")  # Not default
            self.assertNotEqual(rediscache.CACHE_REDIS_PORT, 6379)  # Not default
            self.assertIsNotNone(rediscache.CACHE_REDIS_PASSWORD)  # Not default None
            self.assertNotEqual(rediscache.CACHE_REDIS_DB, 4)  # Not default

            # Verify actual custom values
            self.assertEqual(rediscache.CACHE_DEFAULT_TIMEOUT, "900")
            self.assertEqual(rediscache.CACHE_KEY_PREFIX, "priority_app:")
            self.assertEqual(rediscache.CACHE_REDIS_HOST, "priority-redis.example.com")
            self.assertEqual(rediscache.CACHE_REDIS_PORT, "6382")
            self.assertEqual(rediscache.CACHE_REDIS_PASSWORD, "priority-password")
            self.assertEqual(rediscache.CACHE_REDIS_DB, "8")

    def test_empty_environment_variables(self):
        """Test handling of empty environment variables."""
        # Test with empty values (should be used as-is, not converted to defaults)
        empty_env = {
            "CACHE_DEFAULT_TIMEOUT": "",
            "CACHE_KEY_PREFIX": "",
            "CACHE_REDIS_HOST": "",
            "CACHE_REDIS_PORT": "",
            "CACHE_REDIS_PASSWORD": "",
            "CACHE_REDIS_DB": "",
        }

        with patch.dict(os.environ, empty_env):
            import importlib

            importlib.reload(rediscache)

            # Empty strings should be preserved, not converted to defaults
            self.assertEqual(rediscache.CACHE_DEFAULT_TIMEOUT, "")
            self.assertEqual(rediscache.CACHE_KEY_PREFIX, "")
            self.assertEqual(rediscache.CACHE_REDIS_HOST, "")
            self.assertEqual(rediscache.CACHE_REDIS_PORT, "")
            self.assertEqual(rediscache.CACHE_REDIS_PASSWORD, "")
            self.assertEqual(rediscache.CACHE_REDIS_DB, "")

    def test_module_attributes(self):
        """Test that the module has all expected attributes."""
        expected_attributes = [
            "CACHE_TYPE",
            "CACHE_DEFAULT_TIMEOUT",
            "CACHE_KEY_PREFIX",
            "CACHE_REDIS_HOST",
            "CACHE_REDIS_PORT",
            "CACHE_REDIS_PASSWORD",
            "CACHE_REDIS_DB",
        ]

        for attr in expected_attributes:
            self.assertTrue(hasattr(rediscache, attr), f"Module should have attribute {attr}")

    def test_cache_type_immutable(self):
        """Test that CACHE_TYPE is always 'RedisCache' regardless of environment."""
        # CACHE_TYPE should not be affected by environment variables
        # (it's hardcoded in the module)

        with patch.dict(os.environ, {"CACHE_TYPE": "SomeOtherCache"}):
            import importlib

            importlib.reload(rediscache)

            # Should still be RedisCache
            self.assertEqual(rediscache.CACHE_TYPE, "RedisCache")

    def test_security_configuration_scenarios(self):
        """Test security-related cache configuration scenarios."""
        # Test secure Redis configuration
        secure_env = {
            "CACHE_REDIS_HOST": "secure-redis.internal.com",
            "CACHE_REDIS_PORT": "6380",  # Non-default port
            "CACHE_REDIS_PASSWORD": "very-secure-password-with-special-chars!@#$%",
            "CACHE_REDIS_DB": "1",  # Isolated database
            "CACHE_KEY_PREFIX": "secure_app_v2:",
        }

        with patch.dict(os.environ, secure_env):
            import importlib

            importlib.reload(rediscache)

            # Verify secure configuration is preserved
            self.assertEqual(rediscache.CACHE_REDIS_HOST, "secure-redis.internal.com")
            self.assertEqual(rediscache.CACHE_REDIS_PORT, "6380")
            self.assertEqual(rediscache.CACHE_REDIS_PASSWORD, "very-secure-password-with-special-chars!@#$%")
            self.assertEqual(rediscache.CACHE_REDIS_DB, "1")
            self.assertEqual(rediscache.CACHE_KEY_PREFIX, "secure_app_v2:")

    def test_cache_timeout_edge_cases(self):
        """Test cache timeout configuration with edge case values."""
        edge_case_timeouts = ["0", "1", "86400", "604800", "2592000"]  # 0s, 1s, 1day, 1week, 1month

        for timeout in edge_case_timeouts:
            with patch.dict(os.environ, {"CACHE_DEFAULT_TIMEOUT": timeout}):
                import importlib

                importlib.reload(rediscache)

                self.assertEqual(rediscache.CACHE_DEFAULT_TIMEOUT, timeout)

    def test_redis_port_edge_cases(self):
        """Test Redis port configuration with edge case values."""
        edge_case_ports = ["1", "1024", "65535"]  # Min, common, max valid ports

        for port in edge_case_ports:
            with patch.dict(os.environ, {"CACHE_REDIS_PORT": port}):
                import importlib

                importlib.reload(rediscache)

                self.assertEqual(rediscache.CACHE_REDIS_PORT, port)

    def test_redis_db_edge_cases(self):
        """Test Redis database configuration with edge case values."""
        edge_case_dbs = ["0", "1", "15"]  # Common Redis DB range

        for db in edge_case_dbs:
            with patch.dict(os.environ, {"CACHE_REDIS_DB": db}):
                import importlib

                importlib.reload(rediscache)

                self.assertEqual(rediscache.CACHE_REDIS_DB, db)

    def test_cache_key_prefix_variations(self):
        """Test cache key prefix with various formats."""
        prefix_variations = ["app:", "mlflow_prod:", "cache_v1_", "test-env:", "namespace.app:", "app_cache_2024:"]

        for prefix in prefix_variations:
            with patch.dict(os.environ, {"CACHE_KEY_PREFIX": prefix}):
                import importlib

                importlib.reload(rediscache)

                self.assertEqual(rediscache.CACHE_KEY_PREFIX, prefix)

    def test_redis_host_variations(self):
        """Test Redis host configuration with various formats."""
        host_variations = ["localhost", "127.0.0.1", "redis.example.com", "redis-cluster.internal", "10.0.0.100", "redis-master.k8s.local"]

        for host in host_variations:
            with patch.dict(os.environ, {"CACHE_REDIS_HOST": host}):
                import importlib

                importlib.reload(rediscache)

                self.assertEqual(rediscache.CACHE_REDIS_HOST, host)

    def test_redis_password_security(self):
        """Test Redis password handling for security scenarios."""
        password_scenarios = [
            "simple-password",
            "complex-P@ssw0rd!2024",
            "very-long-password-with-many-characters-and-symbols-!@#$%^&*()",
            "password with spaces",
            "пароль-unicode-密码",  # Unicode characters
            "base64-like-password+/=",
        ]

        for password in password_scenarios:
            with patch.dict(os.environ, {"CACHE_REDIS_PASSWORD": password}):
                import importlib

                importlib.reload(rediscache)

                self.assertEqual(rediscache.CACHE_REDIS_PASSWORD, password)

    def test_module_reload_behavior(self):
        """Test that module can be safely reloaded with different configurations."""
        # First configuration
        first_config = {"CACHE_DEFAULT_TIMEOUT": "300", "CACHE_REDIS_HOST": "redis1.example.com", "CACHE_REDIS_PORT": "6379"}

        with patch.dict(os.environ, first_config):
            import importlib

            importlib.reload(rediscache)

            self.assertEqual(rediscache.CACHE_DEFAULT_TIMEOUT, "300")
            self.assertEqual(rediscache.CACHE_REDIS_HOST, "redis1.example.com")
            self.assertEqual(rediscache.CACHE_REDIS_PORT, "6379")

        # Second configuration
        second_config = {"CACHE_DEFAULT_TIMEOUT": "600", "CACHE_REDIS_HOST": "redis2.example.com", "CACHE_REDIS_PORT": "6380"}

        with patch.dict(os.environ, second_config):
            import importlib

            importlib.reload(rediscache)

            self.assertEqual(rediscache.CACHE_DEFAULT_TIMEOUT, "600")
            self.assertEqual(rediscache.CACHE_REDIS_HOST, "redis2.example.com")
            self.assertEqual(rediscache.CACHE_REDIS_PORT, "6380")

    def test_cache_configuration_isolation(self):
        """Test that cache configuration is isolated between different environments."""
        # Test development configuration
        dev_config = {"CACHE_REDIS_HOST": "localhost", "CACHE_REDIS_PORT": "6379", "CACHE_REDIS_DB": "0", "CACHE_KEY_PREFIX": "dev:"}

        with patch.dict(os.environ, dev_config):
            import importlib

            importlib.reload(rediscache)

            dev_host = rediscache.CACHE_REDIS_HOST
            dev_port = rediscache.CACHE_REDIS_PORT
            dev_db = rediscache.CACHE_REDIS_DB
            dev_prefix = rediscache.CACHE_KEY_PREFIX

        # Test production configuration
        prod_config = {"CACHE_REDIS_HOST": "redis-prod.example.com", "CACHE_REDIS_PORT": "6380", "CACHE_REDIS_DB": "1", "CACHE_KEY_PREFIX": "prod:"}

        with patch.dict(os.environ, prod_config):
            import importlib

            importlib.reload(rediscache)

            # Verify production config is different from dev
            self.assertNotEqual(rediscache.CACHE_REDIS_HOST, dev_host)
            self.assertNotEqual(rediscache.CACHE_REDIS_PORT, dev_port)
            self.assertNotEqual(rediscache.CACHE_REDIS_DB, dev_db)
            self.assertNotEqual(rediscache.CACHE_KEY_PREFIX, dev_prefix)

            # Verify production config values
            self.assertEqual(rediscache.CACHE_REDIS_HOST, "redis-prod.example.com")
            self.assertEqual(rediscache.CACHE_REDIS_PORT, "6380")
            self.assertEqual(rediscache.CACHE_REDIS_DB, "1")
            self.assertEqual(rediscache.CACHE_KEY_PREFIX, "prod:")

    def test_cache_data_integrity_configuration(self):
        """Test cache configuration that supports data integrity."""
        # Test configuration that would support data integrity features
        integrity_config = {
            "CACHE_DEFAULT_TIMEOUT": "3600",  # 1 hour timeout
            "CACHE_KEY_PREFIX": "integrity_check:",
            "CACHE_REDIS_DB": "2",  # Dedicated DB for integrity
            "CACHE_REDIS_PASSWORD": "integrity-password",
        }

        with patch.dict(os.environ, integrity_config):
            import importlib

            importlib.reload(rediscache)

            # Verify integrity-focused configuration
            self.assertEqual(rediscache.CACHE_DEFAULT_TIMEOUT, "3600")
            self.assertEqual(rediscache.CACHE_KEY_PREFIX, "integrity_check:")
            self.assertEqual(rediscache.CACHE_REDIS_DB, "2")
            self.assertEqual(rediscache.CACHE_REDIS_PASSWORD, "integrity-password")

    def test_cache_performance_configuration(self):
        """Test cache configuration optimized for performance."""
        # Test configuration that would optimize for performance
        performance_config = {
            "CACHE_DEFAULT_TIMEOUT": "60",  # Short timeout for high turnover
            "CACHE_KEY_PREFIX": "perf:",  # Short prefix
            "CACHE_REDIS_DB": "0",  # Default DB for best performance
            "CACHE_REDIS_HOST": "redis-performance.local",
        }

        with patch.dict(os.environ, performance_config):
            import importlib

            importlib.reload(rediscache)

            # Verify performance-focused configuration
            self.assertEqual(rediscache.CACHE_DEFAULT_TIMEOUT, "60")
            self.assertEqual(rediscache.CACHE_KEY_PREFIX, "perf:")
            self.assertEqual(rediscache.CACHE_REDIS_DB, "0")
            self.assertEqual(rediscache.CACHE_REDIS_HOST, "redis-performance.local")

    def test_cache_fallback_scenarios(self):
        """Test cache configuration for fallback scenarios."""
        # Test that all constants have reasonable defaults for fallback
        # Clear all cache-related environment variables
        cache_env_vars = ["CACHE_DEFAULT_TIMEOUT", "CACHE_KEY_PREFIX", "CACHE_REDIS_HOST", "CACHE_REDIS_PORT", "CACHE_REDIS_PASSWORD", "CACHE_REDIS_DB"]

        for var in cache_env_vars:
            if var in os.environ:
                del os.environ[var]

        import importlib

        importlib.reload(rediscache)

        # Verify all defaults are reasonable for fallback scenarios
        self.assertEqual(rediscache.CACHE_TYPE, "RedisCache")
        self.assertEqual(rediscache.CACHE_DEFAULT_TIMEOUT, 300)  # 5 minutes
        self.assertEqual(rediscache.CACHE_KEY_PREFIX, "mlflow_oidc:")
        self.assertEqual(rediscache.CACHE_REDIS_HOST, "localhost")
        self.assertEqual(rediscache.CACHE_REDIS_PORT, 6379)
        self.assertIsNone(rediscache.CACHE_REDIS_PASSWORD)  # No auth by default
        self.assertEqual(rediscache.CACHE_REDIS_DB, 4)  # Non-default DB to avoid conflicts


class TestRedisCacheIntegration(unittest.TestCase):
    """Test Redis cache integration with the application configuration system."""

    def setUp(self):
        """Set up test environment."""
        self.original_env = dict(os.environ)

    def tearDown(self):
        """Clean up test environment."""
        os.environ.clear()
        os.environ.update(self.original_env)

    @patch("mlflow_oidc_auth.config.importlib.import_module")
    def test_cache_module_import_in_config(self, mock_import_module):
        """Test that Redis cache module can be imported by the config system."""
        # Mock the rediscache module
        mock_rediscache = MagicMock()
        mock_rediscache.CACHE_TYPE = "RedisCache"
        mock_rediscache.CACHE_DEFAULT_TIMEOUT = "300"
        mock_rediscache.CACHE_KEY_PREFIX = "mlflow_oidc:"
        mock_rediscache.CACHE_REDIS_HOST = "localhost"
        mock_rediscache.CACHE_REDIS_PORT = "6379"
        mock_rediscache.CACHE_REDIS_PASSWORD = None
        mock_rediscache.CACHE_REDIS_DB = "4"

        mock_import_module.return_value = mock_rediscache

        # Test that config can import rediscache module
        from mlflow_oidc_auth.config import AppConfig

        with patch.dict(os.environ, {"CACHE_TYPE": "RedisCache"}):
            AppConfig()

            # Verify import was attempted
            mock_import_module.assert_called_with("mlflow_oidc_auth.cache.rediscache")

    def test_cache_constants_integration_with_config(self):
        """Test that cache constants integrate properly with AppConfig."""
        # Set Redis cache type and custom values
        cache_env = {
            "CACHE_TYPE": "RedisCache",
            "CACHE_DEFAULT_TIMEOUT": "1800",
            "CACHE_KEY_PREFIX": "integration_test:",
            "CACHE_REDIS_HOST": "integration-redis.test",
            "CACHE_REDIS_PORT": "6381",
            "CACHE_REDIS_PASSWORD": "integration-password",
            "CACHE_REDIS_DB": "3",
        }

        with patch.dict(os.environ, cache_env):
            # Import and reload rediscache to pick up environment variables
            import importlib

            importlib.reload(rediscache)

            # Verify constants are set correctly
            self.assertEqual(rediscache.CACHE_TYPE, "RedisCache")
            self.assertEqual(rediscache.CACHE_DEFAULT_TIMEOUT, "1800")
            self.assertEqual(rediscache.CACHE_KEY_PREFIX, "integration_test:")
            self.assertEqual(rediscache.CACHE_REDIS_HOST, "integration-redis.test")
            self.assertEqual(rediscache.CACHE_REDIS_PORT, "6381")
            self.assertEqual(rediscache.CACHE_REDIS_PASSWORD, "integration-password")
            self.assertEqual(rediscache.CACHE_REDIS_DB, "3")

    def test_cache_error_handling_scenarios(self):
        """Test error handling scenarios for cache configuration."""
        # Test with invalid environment values that might cause issues
        # (Note: rediscache.py only reads env vars, doesn't validate them)

        problematic_env = {
            "CACHE_DEFAULT_TIMEOUT": "not-a-number",  # Would cause issues when used
            "CACHE_REDIS_PORT": "invalid-port",  # Would cause issues when used
            "CACHE_REDIS_DB": "invalid-db",  # Would cause issues when used
        }

        with patch.dict(os.environ, problematic_env):
            import importlib

            importlib.reload(rediscache)

            # Module should load without errors (validation happens at usage time)
            self.assertEqual(rediscache.CACHE_DEFAULT_TIMEOUT, "not-a-number")
            self.assertEqual(rediscache.CACHE_REDIS_PORT, "invalid-port")
            self.assertEqual(rediscache.CACHE_REDIS_DB, "invalid-db")

    def test_cache_security_isolation(self):
        """Test cache security and data isolation configuration."""
        # Test configuration for security-conscious environments
        secure_env = {
            "CACHE_KEY_PREFIX": "secure_tenant_123:",  # Tenant isolation
            "CACHE_REDIS_DB": "5",  # Isolated database
            "CACHE_REDIS_PASSWORD": "secure-tenant-password",
            "CACHE_REDIS_HOST": "secure-redis.internal.local",
        }

        with patch.dict(os.environ, secure_env):
            import importlib

            importlib.reload(rediscache)

            # Verify security-focused configuration
            self.assertEqual(rediscache.CACHE_KEY_PREFIX, "secure_tenant_123:")
            self.assertEqual(rediscache.CACHE_REDIS_DB, "5")
            self.assertEqual(rediscache.CACHE_REDIS_PASSWORD, "secure-tenant-password")
            self.assertEqual(rediscache.CACHE_REDIS_HOST, "secure-redis.internal.local")

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

                importlib.reload(rediscache)

                self.assertEqual(rediscache.CACHE_DEFAULT_TIMEOUT, timeout, f"Failed for {description}")

    def test_cache_performance_optimization_config(self):
        """Test cache configuration for performance optimization."""
        # Test configuration optimized for different performance scenarios
        performance_configs = [
            {
                "name": "high_performance",
                "config": {"CACHE_DEFAULT_TIMEOUT": "30", "CACHE_KEY_PREFIX": "hp:", "CACHE_REDIS_DB": "0"},  # Very short timeout  # Short prefix  # Default DB
            },
            {"name": "balanced", "config": {"CACHE_DEFAULT_TIMEOUT": "300", "CACHE_KEY_PREFIX": "balanced:", "CACHE_REDIS_DB": "1"}},  # Medium timeout
            {"name": "long_term", "config": {"CACHE_DEFAULT_TIMEOUT": "3600", "CACHE_KEY_PREFIX": "longterm:", "CACHE_REDIS_DB": "2"}},  # Long timeout
        ]

        for scenario in performance_configs:
            with patch.dict(os.environ, scenario["config"]):
                import importlib

                importlib.reload(rediscache)

                # Verify configuration matches scenario
                self.assertEqual(rediscache.CACHE_DEFAULT_TIMEOUT, scenario["config"]["CACHE_DEFAULT_TIMEOUT"])
                self.assertEqual(rediscache.CACHE_KEY_PREFIX, scenario["config"]["CACHE_KEY_PREFIX"])
                self.assertEqual(rediscache.CACHE_REDIS_DB, scenario["config"]["CACHE_REDIS_DB"])


if __name__ == "__main__":
    unittest.main()
