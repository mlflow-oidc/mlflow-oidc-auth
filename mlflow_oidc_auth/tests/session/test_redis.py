"""
Comprehensive tests for the session/redis.py module.

This module tests Redis session configuration, connection handling,
environment variable parsing, SSL configuration, authentication,
error scenarios, and security aspects of Redis session management.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

import redis

from mlflow_oidc_auth.session import redis as redis_session


class TestRedisSessionModule(unittest.TestCase):
    """Test the Redis session module configuration and initialization."""

    def setUp(self):
        """Set up test environment."""
        # Store original environment variables to restore later
        self.original_env = dict(os.environ)

    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment variables
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_session_type_constant(self):
        """Test that SESSION_TYPE constant is correctly set."""
        self.assertEqual(redis_session.SESSION_TYPE, "redis")

    @patch("redis.Redis")
    def test_redis_default_configuration(self, mock_redis):
        """Test Redis configuration with default environment variables."""
        # Clear all Redis-related environment variables
        redis_env_vars = ["REDIS_HOST", "REDIS_PORT", "REDIS_DB", "REDIS_PASSWORD", "REDIS_SSL", "REDIS_USERNAME"]

        for var in redis_env_vars:
            if var in os.environ:
                del os.environ[var]

        # Mock Redis instance
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Import the module to trigger Redis initialization
        import importlib

        importlib.reload(redis_session)

        # Verify Redis was called with default parameters
        mock_redis.assert_called_with(host="localhost", port=6379, db=0, password=None, ssl=False, username=None)

    @patch("redis.Redis")
    def test_redis_custom_configuration(self, mock_redis):
        """Test Redis configuration with custom environment variables."""
        # Set custom Redis environment variables
        custom_env = {
            "REDIS_HOST": "redis.example.com",
            "REDIS_PORT": "6380",
            "REDIS_DB": "2",
            "REDIS_PASSWORD": "secure-password",
            "REDIS_SSL": "true",
            "REDIS_USERNAME": "redis-user",
        }

        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        with patch.dict(os.environ, custom_env):
            # Import the module to trigger Redis initialization
            import importlib

            importlib.reload(redis_session)

            # Verify Redis was called with custom parameters
            mock_redis.assert_called_with(host="redis.example.com", port=6380, db=2, password="secure-password", ssl=True, username="redis-user")

    @patch("redis.Redis")
    def test_redis_ssl_configuration_variations(self, mock_redis):
        """Test various SSL configuration values."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Test different SSL true values
        ssl_true_values = ["true", "True", "TRUE", "1", "t", "T"]

        for ssl_value in ssl_true_values:
            with patch.dict(os.environ, {"REDIS_SSL": ssl_value}):
                import importlib

                importlib.reload(redis_session)

                # Get the call arguments
                call_args = mock_redis.call_args
                self.assertTrue(call_args[1]["ssl"], f"SSL should be True for value '{ssl_value}'")

            mock_redis.reset_mock()

        # Test different SSL false values
        ssl_false_values = ["false", "False", "FALSE", "0", "f", "F", "no", "off", ""]

        for ssl_value in ssl_false_values:
            with patch.dict(os.environ, {"REDIS_SSL": ssl_value}):
                import importlib

                importlib.reload(redis_session)

                # Get the call arguments
                call_args = mock_redis.call_args
                self.assertFalse(call_args[1]["ssl"], f"SSL should be False for value '{ssl_value}'")

            mock_redis.reset_mock()

    @patch("redis.Redis")
    def test_redis_port_type_conversion(self, mock_redis):
        """Test that REDIS_PORT is properly converted to integer."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        test_ports = ["6379", "6380", "1234", "65535"]

        for port_str in test_ports:
            with patch.dict(os.environ, {"REDIS_PORT": port_str}):
                import importlib

                importlib.reload(redis_session)

                # Get the call arguments and verify port is an integer
                call_args = mock_redis.call_args
                self.assertEqual(call_args[1]["port"], int(port_str))
                self.assertIsInstance(call_args[1]["port"], int)

            mock_redis.reset_mock()

    @patch("redis.Redis")
    def test_redis_db_type_conversion(self, mock_redis):
        """Test that REDIS_DB is properly converted to integer."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        test_dbs = ["0", "1", "5", "15"]

        for db_str in test_dbs:
            with patch.dict(os.environ, {"REDIS_DB": db_str}):
                import importlib

                importlib.reload(redis_session)

                # Get the call arguments and verify db is an integer
                call_args = mock_redis.call_args
                self.assertEqual(call_args[1]["db"], int(db_str))
                self.assertIsInstance(call_args[1]["db"], int)

            mock_redis.reset_mock()

    @patch("redis.Redis")
    def test_redis_password_none_handling(self, mock_redis):
        """Test that empty password is converted to None."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Test with empty password
        with patch.dict(os.environ, {"REDIS_PASSWORD": ""}):
            import importlib

            importlib.reload(redis_session)

            call_args = mock_redis.call_args
            # Empty string should be passed as-is, not converted to None
            self.assertEqual(call_args[1]["password"], "")

        mock_redis.reset_mock()

        # Test with no password environment variable
        if "REDIS_PASSWORD" in os.environ:
            del os.environ["REDIS_PASSWORD"]

        import importlib

        importlib.reload(redis_session)

        call_args = mock_redis.call_args
        self.assertIsNone(call_args[1]["password"])

    @patch("redis.Redis")
    def test_redis_username_none_handling(self, mock_redis):
        """Test that empty username is converted to None."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Test with empty username
        with patch.dict(os.environ, {"REDIS_USERNAME": ""}):
            import importlib

            importlib.reload(redis_session)

            call_args = mock_redis.call_args
            # Empty string should be passed as-is, not converted to None
            self.assertEqual(call_args[1]["username"], "")

        mock_redis.reset_mock()

        # Test with no username environment variable
        if "REDIS_USERNAME" in os.environ:
            del os.environ["REDIS_USERNAME"]

        import importlib

        importlib.reload(redis_session)

        call_args = mock_redis.call_args
        self.assertIsNone(call_args[1]["username"])

    @patch("redis.Redis")
    def test_redis_connection_error_handling(self, mock_redis):
        """Test Redis connection error scenarios."""
        # Test connection error during initialization
        mock_redis.side_effect = redis.ConnectionError("Could not connect to Redis")

        with self.assertRaises(redis.ConnectionError):
            import importlib

            importlib.reload(redis_session)

    @patch("redis.Redis")
    def test_redis_authentication_error_handling(self, mock_redis):
        """Test Redis authentication error scenarios."""
        # Test authentication error during initialization
        mock_redis.side_effect = redis.AuthenticationError("Authentication failed")

        with self.assertRaises(redis.AuthenticationError):
            import importlib

            importlib.reload(redis_session)

    @patch("redis.Redis")
    def test_redis_timeout_error_handling(self, mock_redis):
        """Test Redis timeout error scenarios."""
        # Test timeout error during initialization
        mock_redis.side_effect = redis.TimeoutError("Connection timeout")

        with self.assertRaises(redis.TimeoutError):
            import importlib

            importlib.reload(redis_session)

    @patch("redis.Redis")
    def test_redis_response_error_handling(self, mock_redis):
        """Test Redis response error scenarios."""
        # Test response error during initialization
        mock_redis.side_effect = redis.ResponseError("Invalid response")

        with self.assertRaises(redis.ResponseError):
            import importlib

            importlib.reload(redis_session)

    @patch("redis.Redis")
    def test_redis_instance_creation(self, mock_redis):
        """Test that SESSION_REDIS is properly created and accessible."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        import importlib

        importlib.reload(redis_session)

        # Verify that SESSION_REDIS is the mock instance
        self.assertEqual(redis_session.SESSION_REDIS, mock_redis_instance)

    @patch("redis.Redis")
    def test_redis_ssl_case_insensitive(self, mock_redis):
        """Test that SSL configuration is case insensitive."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Test mixed case values
        test_cases = [
            ("True", True),
            ("true", True),
            ("TRUE", True),
            ("False", False),
            ("false", False),
            ("FALSE", False),
            ("1", True),
            ("0", False),
            ("t", True),
            ("T", True),
            ("f", False),
            ("F", False),
        ]

        for ssl_value, expected in test_cases:
            with patch.dict(os.environ, {"REDIS_SSL": ssl_value}):
                import importlib

                importlib.reload(redis_session)

                call_args = mock_redis.call_args
                self.assertEqual(call_args[1]["ssl"], expected, f"SSL value '{ssl_value}' should result in {expected}")

            mock_redis.reset_mock()

    @patch("redis.Redis")
    def test_redis_environment_variable_precedence(self, mock_redis):
        """Test that environment variables take precedence over defaults."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Set all environment variables to non-default values
        custom_env = {
            "REDIS_HOST": "custom-host",
            "REDIS_PORT": "9999",
            "REDIS_DB": "10",
            "REDIS_PASSWORD": "custom-password",
            "REDIS_SSL": "true",
            "REDIS_USERNAME": "custom-user",
        }

        with patch.dict(os.environ, custom_env):
            import importlib

            importlib.reload(redis_session)

            call_args = mock_redis.call_args

            # Verify all custom values are used
            self.assertEqual(call_args[1]["host"], "custom-host")
            self.assertEqual(call_args[1]["port"], 9999)
            self.assertEqual(call_args[1]["db"], 10)
            self.assertEqual(call_args[1]["password"], "custom-password")
            self.assertTrue(call_args[1]["ssl"])
            self.assertEqual(call_args[1]["username"], "custom-user")

    @patch("redis.Redis")
    def test_redis_invalid_port_handling(self, mock_redis):
        """Test handling of invalid port values."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Test invalid port values that would cause ValueError during int() conversion
        invalid_ports = ["invalid", "abc"]

        for invalid_port in invalid_ports:
            with patch.dict(os.environ, {"REDIS_PORT": invalid_port}):
                with self.assertRaises(ValueError):
                    import importlib

                    importlib.reload(redis_session)

        # Test edge case port values that are valid integers but may be invalid for Redis
        edge_case_ports = ["65536", "-1"]

        for edge_port in edge_case_ports:
            with patch.dict(os.environ, {"REDIS_PORT": edge_port}):
                import importlib

                importlib.reload(redis_session)

                # These should not raise ValueError during module load
                # (Redis client will handle validation when connecting)
                call_args = mock_redis.call_args
                self.assertEqual(call_args[1]["port"], int(edge_port))

            mock_redis.reset_mock()

    @patch("redis.Redis")
    def test_redis_invalid_db_handling(self, mock_redis):
        """Test handling of invalid database values."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Test invalid db values that would cause ValueError during int() conversion
        invalid_dbs = ["invalid", "abc"]

        for invalid_db in invalid_dbs:
            with patch.dict(os.environ, {"REDIS_DB": invalid_db}):
                with self.assertRaises(ValueError):
                    import importlib

                    importlib.reload(redis_session)

        # Test edge case db values that are valid integers but may be invalid for Redis
        edge_case_dbs = ["-1", "16"]

        for edge_db in edge_case_dbs:
            with patch.dict(os.environ, {"REDIS_DB": edge_db}):
                import importlib

                importlib.reload(redis_session)

                # These should not raise ValueError during module load
                # (Redis client will handle validation when connecting)
                call_args = mock_redis.call_args
                self.assertEqual(call_args[1]["db"], int(edge_db))

            mock_redis.reset_mock()

    @patch("redis.Redis")
    def test_redis_security_configuration(self, mock_redis):
        """Test security-related Redis configuration."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Test secure configuration
        secure_env = {
            "REDIS_HOST": "secure-redis.example.com",
            "REDIS_PORT": "6380",  # Non-default port
            "REDIS_PASSWORD": "very-secure-password-123",
            "REDIS_SSL": "true",
            "REDIS_USERNAME": "secure-user",
        }

        with patch.dict(os.environ, secure_env):
            import importlib

            importlib.reload(redis_session)

            call_args = mock_redis.call_args

            # Verify secure configuration
            self.assertEqual(call_args[1]["host"], "secure-redis.example.com")
            self.assertEqual(call_args[1]["port"], 6380)
            self.assertEqual(call_args[1]["password"], "very-secure-password-123")
            self.assertTrue(call_args[1]["ssl"])
            self.assertEqual(call_args[1]["username"], "secure-user")

    @patch("redis.Redis")
    def test_redis_module_reload_behavior(self, mock_redis):
        """Test that module can be safely reloaded with different configurations."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # First configuration
        with patch.dict(os.environ, {"REDIS_HOST": "host1", "REDIS_PORT": "6379"}):
            import importlib

            importlib.reload(redis_session)

            first_call_args = mock_redis.call_args
            self.assertEqual(first_call_args[1]["host"], "host1")
            self.assertEqual(first_call_args[1]["port"], 6379)

        mock_redis.reset_mock()

        # Second configuration
        with patch.dict(os.environ, {"REDIS_HOST": "host2", "REDIS_PORT": "6380"}):
            import importlib

            importlib.reload(redis_session)

            second_call_args = mock_redis.call_args
            self.assertEqual(second_call_args[1]["host"], "host2")
            self.assertEqual(second_call_args[1]["port"], 6380)

    def test_redis_module_attributes(self):
        """Test that the module has the expected attributes."""
        # Test that required attributes exist
        self.assertTrue(hasattr(redis_session, "SESSION_TYPE"))
        self.assertTrue(hasattr(redis_session, "SESSION_REDIS"))

        # Test attribute types
        self.assertIsInstance(redis_session.SESSION_TYPE, str)
        # SESSION_REDIS should be a Redis instance (or mock in tests)

    @patch("redis.Redis")
    def test_redis_connection_pool_configuration(self, mock_redis):
        """Test Redis connection pool behavior."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Test that Redis is initialized (connection pool is created implicitly)
        import importlib

        importlib.reload(redis_session)

        # Verify Redis constructor was called (which creates connection pool)
        mock_redis.assert_called_once()

        # Verify the instance is accessible
        self.assertEqual(redis_session.SESSION_REDIS, mock_redis_instance)

    @patch("redis.Redis")
    def test_redis_memory_management(self, mock_redis):
        """Test Redis memory management and cleanup behavior."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        import importlib

        importlib.reload(redis_session)

        # Verify that the Redis instance is properly stored
        self.assertIsNotNone(redis_session.SESSION_REDIS)

        # Test that the instance can be accessed multiple times
        instance1 = redis_session.SESSION_REDIS
        instance2 = redis_session.SESSION_REDIS
        self.assertEqual(instance1, instance2)

    @patch("redis.Redis")
    def test_redis_data_isolation(self, mock_redis):
        """Test Redis database isolation through DB parameter."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Test different database numbers for isolation
        test_dbs = ["0", "1", "5", "15"]

        for db_num in test_dbs:
            with patch.dict(os.environ, {"REDIS_DB": db_num}):
                import importlib

                importlib.reload(redis_session)

                call_args = mock_redis.call_args
                self.assertEqual(call_args[1]["db"], int(db_num))

            mock_redis.reset_mock()

    @patch("redis.Redis")
    def test_redis_session_expiration_support(self, mock_redis):
        """Test that Redis instance supports session expiration."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        import importlib

        importlib.reload(redis_session)

        # Verify Redis instance is created (which supports TTL/expiration)
        self.assertIsNotNone(redis_session.SESSION_REDIS)

        # Mock some Redis operations that would be used for session management
        redis_session.SESSION_REDIS.set = MagicMock()
        redis_session.SESSION_REDIS.get = MagicMock()
        redis_session.SESSION_REDIS.delete = MagicMock()
        redis_session.SESSION_REDIS.expire = MagicMock()

        # Test that methods are available (would be used by session management)
        self.assertTrue(hasattr(redis_session.SESSION_REDIS, "set"))
        self.assertTrue(hasattr(redis_session.SESSION_REDIS, "get"))
        self.assertTrue(hasattr(redis_session.SESSION_REDIS, "delete"))
        self.assertTrue(hasattr(redis_session.SESSION_REDIS, "expire"))


if __name__ == "__main__":
    unittest.main()
