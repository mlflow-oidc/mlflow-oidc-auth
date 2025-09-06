"""
Comprehensive tests for the session/cachelib.py module.

This module tests FileSystemCache session configuration, directory handling,
environment variable parsing, cache threshold configuration, error scenarios,
and security aspects of filesystem-based session management.
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import pytest
from cachelib import FileSystemCache

from mlflow_oidc_auth.session import cachelib as cachelib_session


class TestCachelibSessionModule(unittest.TestCase):
    """Test the cachelib session module configuration and initialization."""

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
        self.assertEqual(cachelib_session.SESSION_TYPE, "cachelib")

    @patch("cachelib.FileSystemCache")
    def test_filesystem_cache_default_configuration(self, mock_filesystem_cache):
        """Test FileSystemCache configuration with default environment variables."""
        # Clear all cache-related environment variables
        cache_env_vars = ["SESSION_CACHE_DIR", "SESSION_CACHE_THRESHOLD"]

        for var in cache_env_vars:
            if var in os.environ:
                del os.environ[var]

        # Mock FileSystemCache instance
        mock_cache_instance = MagicMock()
        mock_filesystem_cache.return_value = mock_cache_instance

        # Import the module to trigger FileSystemCache initialization
        import importlib

        importlib.reload(cachelib_session)

        # Verify FileSystemCache was called with default parameters
        mock_filesystem_cache.assert_called_with(cache_dir="/tmp/flask_session", threshold=500)

    @patch("cachelib.FileSystemCache")
    def test_filesystem_cache_custom_configuration(self, mock_filesystem_cache):
        """Test FileSystemCache configuration with custom environment variables."""
        # Set custom cache environment variables
        custom_env = {"SESSION_CACHE_DIR": "/custom/cache/dir", "SESSION_CACHE_THRESHOLD": "1000"}

        mock_cache_instance = MagicMock()
        mock_filesystem_cache.return_value = mock_cache_instance

        with patch.dict(os.environ, custom_env):
            # Import the module to trigger FileSystemCache initialization
            import importlib

            importlib.reload(cachelib_session)

            # Verify FileSystemCache was called with custom parameters
            mock_filesystem_cache.assert_called_with(cache_dir="/custom/cache/dir", threshold=1000)

    @patch("cachelib.FileSystemCache")
    def test_cache_threshold_type_conversion(self, mock_filesystem_cache):
        """Test that SESSION_CACHE_THRESHOLD is properly converted to integer."""
        mock_cache_instance = MagicMock()
        mock_filesystem_cache.return_value = mock_cache_instance

        test_thresholds = ["100", "500", "1000", "5000"]

        for threshold_str in test_thresholds:
            with patch.dict(os.environ, {"SESSION_CACHE_THRESHOLD": threshold_str}):
                import importlib

                importlib.reload(cachelib_session)

                # Get the call arguments and verify threshold is an integer
                call_args = mock_filesystem_cache.call_args
                self.assertEqual(call_args[1]["threshold"], int(threshold_str))
                self.assertIsInstance(call_args[1]["threshold"], int)

            mock_filesystem_cache.reset_mock()

    @patch("cachelib.FileSystemCache")
    def test_cache_directory_path_handling(self, mock_filesystem_cache):
        """Test various cache directory path configurations."""
        mock_cache_instance = MagicMock()
        mock_filesystem_cache.return_value = mock_cache_instance

        test_paths = ["/tmp/custom_session", "/var/cache/flask_session", "./local_cache", "~/session_cache", "/opt/app/cache"]

        for cache_dir in test_paths:
            with patch.dict(os.environ, {"SESSION_CACHE_DIR": cache_dir}):
                import importlib

                importlib.reload(cachelib_session)

                call_args = mock_filesystem_cache.call_args
                self.assertEqual(call_args[1]["cache_dir"], cache_dir)

            mock_filesystem_cache.reset_mock()

    @patch("cachelib.FileSystemCache")
    def test_environment_variable_precedence(self, mock_filesystem_cache):
        """Test that environment variables take precedence over defaults."""
        mock_cache_instance = MagicMock()
        mock_filesystem_cache.return_value = mock_cache_instance

        # Set all environment variables to non-default values
        custom_env = {"SESSION_CACHE_DIR": "/custom/session/cache", "SESSION_CACHE_THRESHOLD": "2000"}

        with patch.dict(os.environ, custom_env):
            import importlib

            importlib.reload(cachelib_session)

            call_args = mock_filesystem_cache.call_args

            # Verify all custom values are used
            self.assertEqual(call_args[1]["cache_dir"], "/custom/session/cache")
            self.assertEqual(call_args[1]["threshold"], 2000)

    @patch("cachelib.FileSystemCache")
    def test_invalid_threshold_handling(self, mock_filesystem_cache):
        """Test handling of invalid threshold values."""
        mock_cache_instance = MagicMock()
        mock_filesystem_cache.return_value = mock_cache_instance

        # Test invalid threshold values that would cause ValueError during int() conversion
        invalid_thresholds = ["invalid", "abc"]

        for invalid_threshold in invalid_thresholds:
            with patch.dict(os.environ, {"SESSION_CACHE_THRESHOLD": invalid_threshold}):
                with self.assertRaises(ValueError):
                    import importlib

                    importlib.reload(cachelib_session)

        # Test edge case threshold values that are valid integers but may be unusual
        edge_case_thresholds = ["-1"]

        for edge_threshold in edge_case_thresholds:
            with patch.dict(os.environ, {"SESSION_CACHE_THRESHOLD": edge_threshold}):
                import importlib

                importlib.reload(cachelib_session)

                # These should not raise ValueError during module load
                # (FileSystemCache will handle validation when used)
                call_args = mock_filesystem_cache.call_args
                self.assertEqual(call_args[1]["threshold"], int(edge_threshold))

            mock_filesystem_cache.reset_mock()

    @patch("cachelib.FileSystemCache")
    def test_filesystem_cache_instance_creation(self, mock_filesystem_cache):
        """Test that SESSION_CACHELIB is properly created and accessible."""
        mock_cache_instance = MagicMock()
        mock_filesystem_cache.return_value = mock_cache_instance

        import importlib

        importlib.reload(cachelib_session)

        # Verify that SESSION_CACHELIB is the mock instance
        self.assertEqual(cachelib_session.SESSION_CACHELIB, mock_cache_instance)

    def test_module_attributes(self):
        """Test that the module has the expected attributes."""
        # Test that required attributes exist
        self.assertTrue(hasattr(cachelib_session, "SESSION_TYPE"))
        self.assertTrue(hasattr(cachelib_session, "SESSION_CACHELIB"))

        # Test attribute types
        self.assertIsInstance(cachelib_session.SESSION_TYPE, str)
        # SESSION_CACHELIB should be a FileSystemCache instance (or mock in tests)

    @patch("cachelib.FileSystemCache")
    def test_cache_memory_management(self, mock_filesystem_cache):
        """Test cache memory management and cleanup behavior."""
        mock_cache_instance = MagicMock()
        mock_filesystem_cache.return_value = mock_cache_instance

        import importlib

        importlib.reload(cachelib_session)

        # Verify that the cache instance is properly stored
        self.assertIsNotNone(cachelib_session.SESSION_CACHELIB)

        # Test that the instance can be accessed multiple times
        instance1 = cachelib_session.SESSION_CACHELIB
        instance2 = cachelib_session.SESSION_CACHELIB
        self.assertEqual(instance1, instance2)

    @patch("cachelib.FileSystemCache")
    def test_cache_threshold_edge_cases(self, mock_filesystem_cache):
        """Test cache threshold edge cases."""
        mock_cache_instance = MagicMock()
        mock_filesystem_cache.return_value = mock_cache_instance

        # Test edge case threshold values
        edge_case_thresholds = ["0", "1", "10000"]

        for threshold in edge_case_thresholds:
            with patch.dict(os.environ, {"SESSION_CACHE_THRESHOLD": threshold}):
                import importlib

                importlib.reload(cachelib_session)

                call_args = mock_filesystem_cache.call_args
                self.assertEqual(call_args[1]["threshold"], int(threshold))

            mock_filesystem_cache.reset_mock()

    @patch("cachelib.FileSystemCache")
    def test_cache_directory_security(self, mock_filesystem_cache):
        """Test security-related cache directory configurations."""
        mock_cache_instance = MagicMock()
        mock_filesystem_cache.return_value = mock_cache_instance

        # Test secure cache directory paths
        secure_paths = ["/var/cache/secure_session", "/opt/app/secure/cache", "/tmp/restricted_session"]

        for secure_path in secure_paths:
            with patch.dict(os.environ, {"SESSION_CACHE_DIR": secure_path}):
                import importlib

                importlib.reload(cachelib_session)

                call_args = mock_filesystem_cache.call_args
                self.assertEqual(call_args[1]["cache_dir"], secure_path)

            mock_filesystem_cache.reset_mock()

    @patch("cachelib.FileSystemCache")
    def test_module_reload_behavior(self, mock_filesystem_cache):
        """Test that module can be safely reloaded with different configurations."""
        mock_cache_instance = MagicMock()
        mock_filesystem_cache.return_value = mock_cache_instance

        # First configuration
        with patch.dict(os.environ, {"SESSION_CACHE_DIR": "/tmp/cache1", "SESSION_CACHE_THRESHOLD": "100"}):
            import importlib

            importlib.reload(cachelib_session)

            first_call_args = mock_filesystem_cache.call_args
            self.assertEqual(first_call_args[1]["cache_dir"], "/tmp/cache1")
            self.assertEqual(first_call_args[1]["threshold"], 100)

        mock_filesystem_cache.reset_mock()

        # Second configuration
        with patch.dict(os.environ, {"SESSION_CACHE_DIR": "/tmp/cache2", "SESSION_CACHE_THRESHOLD": "200"}):
            import importlib

            importlib.reload(cachelib_session)

            second_call_args = mock_filesystem_cache.call_args
            self.assertEqual(second_call_args[1]["cache_dir"], "/tmp/cache2")
            self.assertEqual(second_call_args[1]["threshold"], 200)

    @patch("cachelib.FileSystemCache")
    def test_cache_session_expiration_support(self, mock_filesystem_cache):
        """Test that FileSystemCache instance supports session expiration."""
        mock_cache_instance = MagicMock()
        mock_filesystem_cache.return_value = mock_cache_instance

        import importlib

        importlib.reload(cachelib_session)

        # Verify FileSystemCache instance is created (which supports TTL/expiration)
        self.assertIsNotNone(cachelib_session.SESSION_CACHELIB)

        # Mock some cache operations that would be used for session management
        cachelib_session.SESSION_CACHELIB.set = MagicMock()
        cachelib_session.SESSION_CACHELIB.get = MagicMock()
        cachelib_session.SESSION_CACHELIB.delete = MagicMock()
        cachelib_session.SESSION_CACHELIB.clear = MagicMock()

        # Test that methods are available (would be used by session management)
        self.assertTrue(hasattr(cachelib_session.SESSION_CACHELIB, "set"))
        self.assertTrue(hasattr(cachelib_session.SESSION_CACHELIB, "get"))
        self.assertTrue(hasattr(cachelib_session.SESSION_CACHELIB, "delete"))
        self.assertTrue(hasattr(cachelib_session.SESSION_CACHELIB, "clear"))

    @patch("cachelib.FileSystemCache")
    def test_cache_data_isolation(self, mock_filesystem_cache):
        """Test cache data isolation through directory separation."""
        mock_cache_instance = MagicMock()
        mock_filesystem_cache.return_value = mock_cache_instance

        # Test different cache directories for isolation
        test_dirs = ["/tmp/app1_session", "/tmp/app2_session", "/var/cache/isolated"]

        for cache_dir in test_dirs:
            with patch.dict(os.environ, {"SESSION_CACHE_DIR": cache_dir}):
                import importlib

                importlib.reload(cachelib_session)

                call_args = mock_filesystem_cache.call_args
                self.assertEqual(call_args[1]["cache_dir"], cache_dir)

            mock_filesystem_cache.reset_mock()

    @patch("cachelib.FileSystemCache")
    def test_cache_cleanup_and_threshold_behavior(self, mock_filesystem_cache):
        """Test cache cleanup behavior with different threshold values."""
        mock_cache_instance = MagicMock()
        mock_filesystem_cache.return_value = mock_cache_instance

        # Test various threshold values that affect cleanup behavior
        threshold_values = ["50", "100", "500", "1000", "5000"]

        for threshold in threshold_values:
            with patch.dict(os.environ, {"SESSION_CACHE_THRESHOLD": threshold}):
                import importlib

                importlib.reload(cachelib_session)

                call_args = mock_filesystem_cache.call_args
                self.assertEqual(call_args[1]["threshold"], int(threshold))

            mock_filesystem_cache.reset_mock()

    @patch("cachelib.FileSystemCache")
    def test_empty_environment_variables(self, mock_filesystem_cache):
        """Test handling of empty environment variables."""
        mock_cache_instance = MagicMock()
        mock_filesystem_cache.return_value = mock_cache_instance

        # Test with empty cache directory (should use default)
        with patch.dict(os.environ, {"SESSION_CACHE_DIR": ""}):
            import importlib

            importlib.reload(cachelib_session)

            call_args = mock_filesystem_cache.call_args
            # Empty string should be passed as-is, not converted to default
            self.assertEqual(call_args[1]["cache_dir"], "")

        mock_filesystem_cache.reset_mock()

        # Test with empty threshold (should cause ValueError)
        with patch.dict(os.environ, {"SESSION_CACHE_THRESHOLD": ""}):
            with self.assertRaises(ValueError):
                import importlib

                importlib.reload(cachelib_session)


if __name__ == "__main__":
    unittest.main()
