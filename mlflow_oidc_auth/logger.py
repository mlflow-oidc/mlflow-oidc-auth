"""
Logging module for MLflow OIDC Auth Plugin.

This module provides a centralized logging solution for the FastAPI application.
It configures appropriate loggers for the FastAPI server environment.
"""

import logging
import os
import sys
from typing import Optional


class FastAPILogger:
    """
    Logger for FastAPI application.

    This class provides a consistent logging interface for the FastAPI application.
    It supports configuration through environment variables and provides proper
    formatting for the FastAPI server.
    """

    _instance: Optional["FastAPILogger"] = None
    _logger: Optional[logging.Logger] = None

    def __new__(cls) -> "FastAPILogger":
        """Singleton pattern to ensure only one logger instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the FastAPI logger."""
        if self._logger is None:
            self._setup_logger()

    def _setup_logger(self) -> None:
        """
        Set up the logger for FastAPI application.

        This method configures the appropriate logger for FastAPI:
        - Uses uvicorn logger if available
        - Falls back to custom logger with proper formatting
        """
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

        # Try to use uvicorn logger first
        try:
            self._logger = logging.getLogger("uvicorn")
            if not self._logger.handlers:
                # If uvicorn logger doesn't have handlers, set up our own
                self._setup_custom_logger("mlflow_oidc_auth", log_level)
        except Exception:
            # Fallback to custom logger if uvicorn logger is not available
            self._setup_custom_logger("mlflow_oidc_auth", log_level)

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
            logging.Logger: The configured logger instance for the FastAPI application
        """
        if self._logger is None:
            self._setup_logger()
        # Type assertion is safe here as _setup_logger always sets _logger
        assert self._logger is not None, "Logger should be initialized"
        return self._logger

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
_fastapi_logger = FastAPILogger()


# Export convenience functions for easy import and use
def get_logger() -> logging.Logger:
    """
    Get the FastAPI logger instance.

    This function provides easy access to the configured logger for the
    FastAPI application. Use this in your modules instead of creating
    separate loggers.

    Returns:
        logging.Logger: The configured logger instance

    Example:
        from mlflow_oidc_auth.logger import get_logger
        logger = get_logger()
        logger.info("This works with FastAPI")
    """
    return _fastapi_logger.get_logger()


# Export convenience logging functions
def debug(message: str, *args, **kwargs) -> None:
    """Log a debug message using the FastAPI logger."""
    _fastapi_logger.debug(message, *args, **kwargs)


def info(message: str, *args, **kwargs) -> None:
    """Log an info message using the FastAPI logger."""
    _fastapi_logger.info(message, *args, **kwargs)


def warning(message: str, *args, **kwargs) -> None:
    """Log a warning message using the FastAPI logger."""
    _fastapi_logger.warning(message, *args, **kwargs)


def error(message: str, *args, **kwargs) -> None:
    """Log an error message using the FastAPI logger."""
    _fastapi_logger.error(message, *args, **kwargs)


def critical(message: str, *args, **kwargs) -> None:
    """Log a critical message using the FastAPI logger."""
    _fastapi_logger.critical(message, *args, **kwargs)
