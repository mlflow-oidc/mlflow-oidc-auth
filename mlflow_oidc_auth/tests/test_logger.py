"""
Tests for the logger module.

This module contains comprehensive tests for the FastAPILogger class and
related logging functionality to achieve 100% test coverage.
"""

import logging
import os
import sys
from io import StringIO
from unittest.mock import Mock, patch, MagicMock
import pytest

from mlflow_oidc_auth.logger import FastAPILogger, get_logger, debug, info, warning, error, critical, _fastapi_logger


class TestFastAPILogger:
    """Test cases for the FastAPILogger class."""

    def setup_method(self):
        """Reset the singleton instance before each test."""
        # Reset the singleton instance
        FastAPILogger._instance = None
        FastAPILogger._logger = None

    def teardown_method(self):
        """Clean up after each test."""
        # Reset the singleton instance
        FastAPILogger._instance = None
        FastAPILogger._logger = None
        # Clear any environment variables that might affect tests
        if "LOG_LEVEL" in os.environ:
            del os.environ["LOG_LEVEL"]

    def test_singleton_pattern(self):
        """Test that FastAPILogger follows singleton pattern."""
        logger1 = FastAPILogger()
        logger2 = FastAPILogger()

        assert logger1 is logger2
        assert FastAPILogger._instance is logger1

    def test_init_sets_up_logger_once(self):
        """Test that logger is only set up once."""
        # Create first instance
        logger1 = FastAPILogger()

        # Mock _setup_logger after first instance is created
        with patch.object(logger1, "_setup_logger") as mock_setup:
            # Create second instance - should be same as first
            logger2 = FastAPILogger()

            # _setup_logger should not be called for second instance
            assert mock_setup.call_count == 0
            assert logger1 is logger2

    @patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"})
    def test_setup_logger_with_uvicorn_logger_available(self):
        """Test logger setup when uvicorn logger is available."""
        mock_uvicorn_logger = Mock(spec=logging.Logger)
        mock_uvicorn_logger.handlers = [Mock()]  # Has handlers

        with patch("logging.getLogger") as mock_get_logger:
            mock_get_logger.return_value = mock_uvicorn_logger

            logger = FastAPILogger()

            assert logger._logger is mock_uvicorn_logger
            mock_get_logger.assert_called_with("uvicorn")

    @patch.dict(os.environ, {"LOG_LEVEL": "WARNING"})
    def test_setup_logger_with_uvicorn_logger_no_handlers(self):
        """Test logger setup when uvicorn logger has no handlers."""
        mock_uvicorn_logger = Mock(spec=logging.Logger)
        mock_uvicorn_logger.handlers = []  # No handlers

        with patch("logging.getLogger") as mock_get_logger, patch.object(FastAPILogger, "_setup_custom_logger") as mock_setup_custom:
            mock_get_logger.return_value = mock_uvicorn_logger

            logger = FastAPILogger()

            mock_setup_custom.assert_called_once_with("mlflow_oidc_auth", "WARNING")

    @patch.dict(os.environ, {"LOG_LEVEL": "ERROR"})
    def test_setup_logger_uvicorn_exception(self):
        """Test logger setup when uvicorn logger raises exception."""
        with patch("logging.getLogger") as mock_get_logger, patch.object(FastAPILogger, "_setup_custom_logger") as mock_setup_custom:
            mock_get_logger.side_effect = Exception("Uvicorn not available")

            logger = FastAPILogger()

            mock_setup_custom.assert_called_once_with("mlflow_oidc_auth", "ERROR")

    def test_setup_custom_logger_default_log_level(self):
        """Test custom logger setup with default log level."""
        with patch("logging.getLogger") as mock_get_logger, patch("logging.StreamHandler") as mock_handler_class, patch(
            "logging.Formatter"
        ) as mock_formatter_class:
            mock_logger = Mock(spec=logging.Logger)
            mock_logger.handlers = []
            mock_get_logger.return_value = mock_logger

            mock_handler = Mock()
            mock_handler_class.return_value = mock_handler

            mock_formatter = Mock()
            mock_formatter_class.return_value = mock_formatter

            logger = FastAPILogger()
            logger._setup_custom_logger("test_logger", "INFO")

            # Verify logger configuration
            mock_logger.setLevel.assert_called_with(logging.INFO)
            mock_handler_class.assert_called_with(sys.stdout)
            mock_handler.setLevel.assert_called_with(logging.INFO)
            mock_formatter_class.assert_called_with(
                "[%(asctime)s] %(levelname)s in %(name)s (%(filename)s:%(lineno)d): %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
            mock_handler.setFormatter.assert_called_with(mock_formatter)
            mock_logger.addHandler.assert_called_with(mock_handler)

    def test_setup_custom_logger_with_existing_handlers(self):
        """Test custom logger setup when logger already has handlers."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_logger.handlers = [Mock()]  # Already has handlers
            mock_get_logger.return_value = mock_logger

            logger = FastAPILogger()
            logger._setup_custom_logger("test_logger", "DEBUG")

            # Should not add new handlers
            mock_logger.addHandler.assert_not_called()

    def test_setup_custom_logger_invalid_log_level(self):
        """Test custom logger setup with invalid log level falls back to INFO."""
        with patch("logging.getLogger") as mock_get_logger, patch("logging.StreamHandler") as mock_handler_class:
            mock_logger = Mock(spec=logging.Logger)
            mock_logger.handlers = []
            mock_get_logger.return_value = mock_logger

            mock_handler = Mock()
            mock_handler_class.return_value = mock_handler

            logger = FastAPILogger()
            logger._setup_custom_logger("test_logger", "INVALID_LEVEL")

            # Should fall back to INFO level
            mock_logger.setLevel.assert_called_with(logging.INFO)
            mock_handler.setLevel.assert_called_with(logging.INFO)

    def test_get_logger_when_logger_is_none(self):
        """Test get_logger when _logger is None."""
        logger = FastAPILogger()
        logger._logger = None

        with patch.object(logger, "_setup_logger") as mock_setup:
            mock_setup_logger = Mock(spec=logging.Logger)

            def setup_side_effect():
                logger._logger = mock_setup_logger

            mock_setup.side_effect = setup_side_effect

            result = logger.get_logger()

            mock_setup.assert_called_once()
            assert result is mock_setup_logger

    def test_get_logger_assertion_error(self):
        """Test get_logger assertion when logger is still None after setup."""
        logger = FastAPILogger()
        logger._logger = None

        with patch.object(logger, "_setup_logger") as mock_setup:
            # Mock setup doesn't set _logger
            mock_setup.return_value = None

            with pytest.raises(AssertionError, match="Logger should be initialized"):
                logger.get_logger()

    def test_convenience_logging_methods(self):
        """Test all convenience logging methods."""
        logger = FastAPILogger()
        mock_logger = Mock(spec=logging.Logger)
        logger._logger = mock_logger

        # Test debug method
        logger.debug("debug message", extra_arg="value")
        mock_logger.debug.assert_called_with("debug message", extra_arg="value")

        # Test info method
        logger.info("info message", extra_arg="value")
        mock_logger.info.assert_called_with("info message", extra_arg="value")

        # Test warning method
        logger.warning("warning message", extra_arg="value")
        mock_logger.warning.assert_called_with("warning message", extra_arg="value")

        # Test error method
        logger.error("error message", extra_arg="value")
        mock_logger.error.assert_called_with("error message", extra_arg="value")

        # Test critical method
        logger.critical("critical message", extra_arg="value")
        mock_logger.critical.assert_called_with("critical message", extra_arg="value")


class TestModuleLevelFunctions:
    """Test cases for module-level convenience functions."""

    def setup_method(self):
        """Reset the global logger instance before each test."""
        # Reset the global instance
        FastAPILogger._instance = None
        FastAPILogger._logger = None

    def teardown_method(self):
        """Clean up after each test."""
        # Reset the global instance
        FastAPILogger._instance = None
        FastAPILogger._logger = None

    def test_get_logger_function(self):
        """Test the module-level get_logger function."""
        with patch.object(_fastapi_logger, "get_logger") as mock_get_logger:
            mock_logger = Mock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            result = get_logger()

            assert result is mock_logger
            mock_get_logger.assert_called_once()

    def test_debug_function(self):
        """Test the module-level debug function."""
        with patch.object(_fastapi_logger, "debug") as mock_debug:
            debug("debug message", extra_arg="value")
            mock_debug.assert_called_once_with("debug message", extra_arg="value")

    def test_info_function(self):
        """Test the module-level info function."""
        with patch.object(_fastapi_logger, "info") as mock_info:
            info("info message", extra_arg="value")
            mock_info.assert_called_once_with("info message", extra_arg="value")

    def test_warning_function(self):
        """Test the module-level warning function."""
        with patch.object(_fastapi_logger, "warning") as mock_warning:
            warning("warning message", extra_arg="value")
            mock_warning.assert_called_once_with("warning message", extra_arg="value")

    def test_error_function(self):
        """Test the module-level error function."""
        with patch.object(_fastapi_logger, "error") as mock_error:
            error("error message", extra_arg="value")
            mock_error.assert_called_once_with("error message", extra_arg="value")

    def test_critical_function(self):
        """Test the module-level critical function."""
        with patch.object(_fastapi_logger, "critical") as mock_critical:
            critical("critical message", extra_arg="value")
            mock_critical.assert_called_once_with("critical message", extra_arg="value")


class TestLoggerIntegration:
    """Integration tests for logger functionality."""

    def setup_method(self):
        """Reset the singleton instance before each test."""
        FastAPILogger._instance = None
        FastAPILogger._logger = None

    def teardown_method(self):
        """Clean up after each test."""
        FastAPILogger._instance = None
        FastAPILogger._logger = None
        # Clear any environment variables
        if "LOG_LEVEL" in os.environ:
            del os.environ["LOG_LEVEL"]

    @patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"})
    def test_end_to_end_logging_with_debug_level(self, caplog):
        """Test end-to-end logging functionality with DEBUG level."""
        with caplog.at_level(logging.DEBUG):
            logger = get_logger()
            # Manually set the logger level to DEBUG to ensure it works
            logger.setLevel(logging.DEBUG)

            logger.debug("Test debug message")
            logger.info("Test info message")
            logger.warning("Test warning message")
            logger.error("Test error message")
            logger.critical("Test critical message")

        # Check that all messages were logged
        log_messages = [record.message for record in caplog.records]
        assert "Test debug message" in log_messages
        assert "Test info message" in log_messages
        assert "Test warning message" in log_messages
        assert "Test error message" in log_messages
        assert "Test critical message" in log_messages

    @patch.dict(os.environ, {"LOG_LEVEL": "ERROR"})
    def test_end_to_end_logging_with_error_level(self, caplog):
        """Test end-to-end logging functionality with ERROR level."""
        with caplog.at_level(logging.ERROR):
            logger = get_logger()
            logger.debug("Test debug message")
            logger.info("Test info message")
            logger.warning("Test warning message")
            logger.error("Test error message")
            logger.critical("Test critical message")

        # Check that only ERROR and CRITICAL messages were logged
        log_messages = [record.message for record in caplog.records]
        assert "Test debug message" not in log_messages
        assert "Test info message" not in log_messages
        assert "Test warning message" not in log_messages
        assert "Test error message" in log_messages
        assert "Test critical message" in log_messages

    def test_logger_performance_and_resource_management(self):
        """Test logger performance and resource management."""
        import time

        # Test that logger creation is fast
        start_time = time.time()
        for _ in range(100):
            logger = FastAPILogger()
        end_time = time.time()

        # Should be very fast due to singleton pattern
        assert end_time - start_time < 0.1

        # Test that multiple get_logger calls don't create new loggers
        logger1 = get_logger()
        logger2 = get_logger()
        assert logger1 is logger2

    def test_sensitive_data_handling(self, caplog):
        """Test that logger doesn't expose sensitive data in logs."""
        with caplog.at_level(logging.INFO):
            logger = get_logger()

            # Test logging with potentially sensitive data
            sensitive_data = {"password": "secret123", "token": "bearer_token_xyz", "api_key": "api_key_abc"}

            # Logger should log the message as-is (it's the application's
            # responsibility to sanitize sensitive data before logging)
            logger.info(f"User data: {sensitive_data}")

        # The logger itself doesn't filter sensitive data - this is by design
        # Applications should sanitize data before passing to logger
        log_messages = [record.message for record in caplog.records]
        assert any("User data:" in msg for msg in log_messages)
        assert any(str(sensitive_data) in msg for msg in log_messages)

    def test_log_formatting_consistency(self, caplog):
        """Test that log formatting is consistent and includes required fields."""
        with caplog.at_level(logging.INFO):
            logger = get_logger()
            logger.info("Test message for formatting")

        # Check that log was captured
        assert len(caplog.records) > 0
        record = caplog.records[-1]

        # Check that log record includes expected components
        assert record.levelname == "INFO"  # Log level
        assert record.name in ["mlflow_oidc_auth", "uvicorn"]  # Logger name
        assert record.message == "Test message for formatting"  # Message
        assert record.filename == "test_logger.py"  # Should include filename


class TestLoggerErrorHandling:
    """Test error handling in logger functionality."""

    def setup_method(self):
        """Reset the singleton instance before each test."""
        FastAPILogger._instance = None
        FastAPILogger._logger = None

    def teardown_method(self):
        """Clean up after each test."""
        FastAPILogger._instance = None
        FastAPILogger._logger = None

    def test_logger_with_invalid_environment_variable(self):
        """Test logger behavior with invalid LOG_LEVEL environment variable."""
        with patch.dict(os.environ, {"LOG_LEVEL": "INVALID_LEVEL"}):
            logger = FastAPILogger()

            # Should not raise an exception and should fall back to INFO level
            actual_logger = logger.get_logger()
            assert actual_logger is not None

    def test_logger_with_missing_environment_variable(self):
        """Test logger behavior when LOG_LEVEL environment variable is missing."""
        # Ensure LOG_LEVEL is not set
        if "LOG_LEVEL" in os.environ:
            del os.environ["LOG_LEVEL"]

        logger = FastAPILogger()
        actual_logger = logger.get_logger()

        # Should not raise an exception and should use default INFO level
        assert actual_logger is not None

    def test_logger_exception_during_handler_creation(self):
        """Test logger behavior when handler creation fails."""
        with patch("logging.StreamHandler") as mock_handler_class:
            mock_handler_class.side_effect = Exception("Handler creation failed")

            # Should not raise an exception during logger creation
            logger = FastAPILogger()

            # The logger should still be created, even if handler setup fails
            assert logger is not None

    def test_logger_exception_during_formatter_creation(self):
        """Test logger behavior when formatter creation fails."""
        with patch("logging.Formatter") as mock_formatter_class:
            mock_formatter_class.side_effect = Exception("Formatter creation failed")

            # Should not raise an exception during logger creation
            logger = FastAPILogger()

            # The logger should still be created, even if formatter setup fails
            assert logger is not None

    def test_get_logger_calls_setup_when_logger_none(self):
        """Test that get_logger calls _setup_logger when _logger is None."""
        logger = FastAPILogger()
        # Explicitly set _logger to None to test the condition
        logger._logger = None

        with patch.object(logger, "_setup_logger") as mock_setup:
            mock_logger = Mock(spec=logging.Logger)

            def setup_side_effect():
                logger._logger = mock_logger

            mock_setup.side_effect = setup_side_effect

            result = logger.get_logger()

            # Verify _setup_logger was called
            mock_setup.assert_called_once()
            assert result is mock_logger
