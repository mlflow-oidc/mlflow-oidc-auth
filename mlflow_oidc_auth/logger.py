"""
Logging module for MLflow OIDC Auth Plugin.

This module provides a centralized logging solution for the FastAPI application.
It configures appropriate loggers for the FastAPI server environment.
"""

import logging
import os
from typing import Optional

# Global logger instance
_logger: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    """
    Get the configured logger instance.

    This function ensures the logger is configured only once and reused across
    all modules. It uses the uvicorn logger by default for FastAPI compatibility.

    Returns:
        logging.Logger: The configured logger instance
    """
    global _logger

    if _logger is None:
        # Get logger name from environment or default to uvicorn
        logger_name = os.environ.get("LOGGING_LOGGER_NAME", "uvicorn")
        _logger = logging.getLogger(logger_name)

        # Set level from environment
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        _logger.setLevel(getattr(logging, log_level, logging.INFO))

        # Ensure propagation is enabled for testing frameworks
        _logger.propagate = True

    return _logger
