"""
Unified logging module for MLflow OIDC Auth Plugin.

This module provides a centralized logging solution that works consistently
across both Flask and FastAPI modes. It automatically detects the server mode
and configures appropriate loggers.
"""

import logging
import os
import sys
from typing import Optional


class UnifiedLogger:
    """
    Unified logger that works seamlessly in both Flask and FastAPI modes.

    This class automatically detects the server mode and provides a consistent
    logging interface across the application. It supports configuration through
    environment variables and provides proper formatting for different server types.
    """

    _instance: Optional["UnifiedLogger"] = None
    _logger: Optional[logging.Logger] = None
    _server_mode: Optional[str] = None

    def __new__(cls) -> "UnifiedLogger":
        """Singleton pattern to ensure only one logger instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the unified logger with automatic server mode detection."""
        if self._logger is None:
            self._detect_server_mode()
            self._setup_logger()

    def _detect_server_mode(self) -> None:
        """
        Detect the server mode (Flask or FastAPI) based on available modules.

        This method checks the current runtime environment to determine whether
        the application is running in Flask mode (MLflow server) or FastAPI mode.
        """
        try:
            # Check if we're in a FastAPI context
            import uvicorn

            if "uvicorn" in sys.modules or "fastapi" in sys.modules:
                self._server_mode = "fastapi"
            else:
                self._server_mode = "flask"
        except ImportError:
            # Fall back to Flask mode if FastAPI modules are not available
            self._server_mode = "flask"

    def _setup_logger(self) -> None:
        """
        Set up the logger based on the detected server mode.

        This method configures the appropriate logger for the current server mode:
        - Flask mode: Uses mlflow.server.app logger or creates a new one
        - FastAPI mode: Uses uvicorn logger or creates a compatible one
        """
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

        if self._server_mode == "fastapi":
            # For FastAPI mode, use uvicorn logger or create a compatible one
            try:
                self._logger = logging.getLogger("uvicorn")
                if not self._logger.handlers:
                    # If uvicorn logger doesn't have handlers, set up our own
                    self._setup_custom_logger("mlflow_oidc_auth.fastapi", log_level)
            except Exception:
                # Fallback to custom logger if uvicorn logger is not available
                self._setup_custom_logger("mlflow_oidc_auth.fastapi", log_level)
        else:
            # For Flask mode, try to use app.logger or create a custom logger
            try:
                from mlflow.server import app

                self._logger = app.logger
                # Ensure the logger level is set according to environment
                self._logger.setLevel(getattr(logging, log_level, logging.INFO))
            except (ImportError, AttributeError):
                # Fallback to custom logger if Flask app is not available
                self._setup_custom_logger("mlflow_oidc_auth.flask", log_level)

    def _setup_custom_logger(self, logger_name: str, log_level: str) -> None:
        """
        Set up a custom logger with proper formatting.

        Args:
            logger_name: Name for the logger
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self._logger = logging.getLogger(logger_name)
        self._logger.setLevel(getattr(logging, log_level, logging.INFO))

        # Only add handler if logger doesn't have any to avoid duplicates
        if not self._logger.handlers:
            # Create console handler with formatting
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(getattr(logging, log_level, logging.INFO))

            # Create formatter
            formatter = logging.Formatter("[%(asctime)s] %(levelname)s in %(name)s (%(filename)s:%(lineno)d): %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
            handler.setFormatter(formatter)

            self._logger.addHandler(handler)

    def get_logger(self) -> logging.Logger:
        """
        Get the configured logger instance.

        Returns:
            logging.Logger: The configured logger instance for the current server mode
        """
        if self._logger is None:
            self._setup_logger()
        # Type assertion is safe here as _setup_logger always sets _logger
        assert self._logger is not None, "Logger should be initialized"
        return self._logger

    def get_server_mode(self) -> str:
        """
        Get the detected server mode.

        Returns:
            str: The detected server mode ('flask' or 'fastapi')
        """
        return self._server_mode or "unknown"

    # Convenience methods for direct logging
    def debug(self, message: str, *args, **kwargs) -> None:
        """Log a debug message."""
        self.get_logger().debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs) -> None:
        """Log an info message."""
        self.get_logger().info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        """Log a warning message."""
        self.get_logger().warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        """Log an error message."""
        self.get_logger().error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs) -> None:
        """Log a critical message."""
        self.get_logger().critical(message, *args, **kwargs)


# Create the global logger instance
_unified_logger = UnifiedLogger()


# Export convenience functions for easy import and use
def get_logger() -> logging.Logger:
    """
    Get the unified logger instance.

    This function provides easy access to the configured logger that works
    in both Flask and FastAPI modes. Use this in your modules instead of
    creating separate loggers.

    Returns:
        logging.Logger: The configured logger instance

    Example:
        from mlflow_oidc_auth.logger import get_logger
        logger = get_logger()
        logger.info("This works in both Flask and FastAPI modes")
    """
    return _unified_logger.get_logger()


def get_server_mode() -> str:
    """
    Get the detected server mode.

    Returns:
        str: The detected server mode ('flask' or 'fastapi')
    """
    return _unified_logger.get_server_mode()


# Export convenience logging functions
def debug(message: str, *args, **kwargs) -> None:
    """Log a debug message using the unified logger."""
    _unified_logger.debug(message, *args, **kwargs)


def info(message: str, *args, **kwargs) -> None:
    """Log an info message using the unified logger."""
    _unified_logger.info(message, *args, **kwargs)


def warning(message: str, *args, **kwargs) -> None:
    """Log a warning message using the unified logger."""
    _unified_logger.warning(message, *args, **kwargs)


def error(message: str, *args, **kwargs) -> None:
    """Log an error message using the unified logger."""
    _unified_logger.error(message, *args, **kwargs)


def critical(message: str, *args, **kwargs) -> None:
    """Log a critical message using the unified logger."""
    _unified_logger.critical(message, *args, **kwargs)
