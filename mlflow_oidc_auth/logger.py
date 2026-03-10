"""
Logging module for MLflow OIDC Auth Plugin.

This module provides a centralized logging solution for the FastAPI application.
It configures appropriate loggers for the FastAPI server environment.
"""

import logging
import os
from typing import Optional

VALID_LEVELS = {
    "DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING,
    "WARN": logging.WARNING, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL
}

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

        if not _logger.handlers:  # type: ignore[attr-defined]
            handler = logging.StreamHandler()
            # use a minimal default formatter similar to uvicorn's default
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
            )
            handler.setLevel(logging.INFO)  # Match default; override via env
            _logger.addHandler(handler)

        # Set level from environment
        log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
        log_level = VALID_LEVELS.get(log_level_str, logging.INFO)
        _logger.setLevel(log_level)

        # Ensure propagation is enabled for testing frameworks
        _logger.propagate = True

    return _logger
