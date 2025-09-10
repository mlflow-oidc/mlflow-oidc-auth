"""
Tests for the logger module.

This module contains comprehensive tests for the get_logger function
to achieve 100% test coverage.
"""

import logging
import os
from unittest.mock import Mock, patch
import pytest

from mlflow_oidc_auth.logger import get_logger


class TestGetLogger:
    """Test cases for the get_logger function."""

    def setup_method(self):
        """Reset the global logger instance before each test."""
        from mlflow_oidc_auth.logger import _logger

        # Reset the global _logger to None
        import mlflow_oidc_auth.logger

        mlflow_oidc_auth.logger._logger = None

    def teardown_method(self):
        """Clean up after each test."""
        # Reset the global _logger
        import mlflow_oidc_auth.logger

        mlflow_oidc_auth.logger._logger = None
        # Clear environment variables
        for key in ["LOGGING_LOGGER_NAME", "LOG_LEVEL"]:
            if key in os.environ:
                del os.environ[key]

    def test_get_logger_first_call_sets_up_logger(self):
        """Test that first call to get_logger sets up the logger."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            result = get_logger()

            # Should call getLogger with default name
            mock_get_logger.assert_called_once_with("uvicorn")
            # Should set level to INFO
            mock_logger.setLevel.assert_called_once_with(logging.INFO)
            # Should set propagate to True
            assert mock_logger.propagate == True
            # Should return the logger
            assert result is mock_logger

    def test_get_logger_subsequent_calls_return_same_logger(self):
        """Test that subsequent calls return the same logger instance."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            result1 = get_logger()
            result2 = get_logger()

            # getLogger should only be called once
            mock_get_logger.assert_called_once_with("uvicorn")
            # Both results should be the same
            assert result1 is result2
            assert result1 is mock_logger

    @patch.dict(os.environ, {"LOGGING_LOGGER_NAME": "custom_logger"})
    def test_get_logger_with_custom_logger_name(self):
        """Test get_logger with custom LOGGING_LOGGER_NAME."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            result = get_logger()

            mock_get_logger.assert_called_once_with("custom_logger")
            assert result is mock_logger

    @patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"})
    def test_get_logger_with_debug_level(self):
        """Test get_logger with LOG_LEVEL set to DEBUG."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            get_logger()

            mock_logger.setLevel.assert_called_once_with(logging.DEBUG)

    @patch.dict(os.environ, {"LOG_LEVEL": "WARNING"})
    def test_get_logger_with_warning_level(self):
        """Test get_logger with LOG_LEVEL set to WARNING."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            get_logger()

            mock_logger.setLevel.assert_called_once_with(logging.WARNING)

    @patch.dict(os.environ, {"LOG_LEVEL": "ERROR"})
    def test_get_logger_with_error_level(self):
        """Test get_logger with LOG_LEVEL set to ERROR."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            get_logger()

            mock_logger.setLevel.assert_called_once_with(logging.ERROR)

    @patch.dict(os.environ, {"LOG_LEVEL": "CRITICAL"})
    def test_get_logger_with_critical_level(self):
        """Test get_logger with LOG_LEVEL set to CRITICAL."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            get_logger()

            mock_logger.setLevel.assert_called_once_with(logging.CRITICAL)

    @patch.dict(os.environ, {"LOG_LEVEL": "INVALID"})
    def test_get_logger_with_invalid_log_level_defaults_to_info(self):
        """Test get_logger with invalid LOG_LEVEL defaults to INFO."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            get_logger()

            # Should default to INFO for invalid level
            mock_logger.setLevel.assert_called_once_with(logging.INFO)

    def test_get_logger_propagate_set_to_true(self):
        """Test that propagate is set to True."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            get_logger()

            assert mock_logger.propagate == True

    @patch.dict(os.environ, {"LOGGING_LOGGER_NAME": "test_name", "LOG_LEVEL": "DEBUG"})
    def test_get_logger_with_both_env_vars(self):
        """Test get_logger with both LOGGING_LOGGER_NAME and LOG_LEVEL set."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            result = get_logger()

            mock_get_logger.assert_called_once_with("test_name")
            mock_logger.setLevel.assert_called_once_with(logging.DEBUG)
            assert mock_logger.propagate == True
            assert result is mock_logger

    def test_get_logger_logger_name_default(self):
        """Test that default logger name is 'uvicorn'."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            get_logger()

            mock_get_logger.assert_called_once_with("uvicorn")

    def test_get_logger_log_level_default(self):
        """Test that default log level is INFO."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            get_logger()

            mock_logger.setLevel.assert_called_once_with(logging.INFO)
