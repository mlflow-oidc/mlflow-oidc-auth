"""
OAuth configuration for FastAPI application.

This module provides lazy-initialized OAuth client configuration to avoid
startup issues with OIDC discovery URL connections.
"""

import time
from typing import Optional

from authlib.integrations.starlette_client import OAuth

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

_oauth_instance: Optional[OAuth] = None
_oidc_client_registered: bool = False


def get_oauth() -> OAuth:
    """
    Get the OAuth instance, initializing it if necessary.

    Returns:
        OAuth instance with OIDC client registered
    """
    global _oauth_instance, _oidc_client_registered

    if _oauth_instance is None:
        _oauth_instance = OAuth()
        logger.debug("OAuth instance created")

    if not _oidc_client_registered:
        _register_oidc_client()

    return _oauth_instance


def _register_oidc_client() -> None:
    """
    Register the OIDC client with the OAuth instance.

    This function handles retries and proper error handling for OIDC discovery.
    """
    global _oidc_client_registered

    # Validate required configuration
    if not config.OIDC_CLIENT_ID:
        logger.error("OIDC_CLIENT_ID is not configured")
        raise ValueError("OIDC_CLIENT_ID is required for OIDC authentication")

    if not config.OIDC_CLIENT_SECRET:
        logger.error("OIDC_CLIENT_SECRET is not configured")
        raise ValueError("OIDC_CLIENT_SECRET is required for OIDC authentication")

    if not config.OIDC_DISCOVERY_URL:
        logger.error("OIDC_DISCOVERY_URL is not configured")
        raise ValueError("OIDC_DISCOVERY_URL is required for OIDC authentication")

    max_retries = 3
    retry_delay = 1  # seconds

    for attempt in range(max_retries):
        try:
            logger.debug(f"Registering OIDC client (attempt {attempt + 1}/{max_retries})")

            _oauth_instance.register(
                name="oidc",
                client_id=config.OIDC_CLIENT_ID,
                client_secret=config.OIDC_CLIENT_SECRET,
                server_metadata_url=config.OIDC_DISCOVERY_URL,
                client_kwargs={"scope": config.OIDC_SCOPE},
            )

            _oidc_client_registered = True
            logger.info("OIDC client registered successfully")
            return

        except Exception as e:
            logger.warning(f"Failed to register OIDC client (attempt {attempt + 1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                logger.debug(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Failed to register OIDC client after all retries")
                raise


def is_oidc_configured() -> bool:
    """
    Check if OIDC is properly configured and the client is registered.

    Returns:
        True if OIDC is configured and client is registered, False otherwise
    """
    try:
        oauth_instance = get_oauth()
        return hasattr(oauth_instance, "oidc") and _oidc_client_registered
    except Exception as e:
        logger.debug(f"OIDC configuration check failed: {e}")
        return False


def reset_oauth() -> None:
    """Reset OAuth instance and registration state for testing or reinitialization."""
    global _oauth_instance, _oidc_client_registered
    _oauth_instance = None
    _oidc_client_registered = False
    logger.debug("OAuth instance reset")


# Create lazy-loaded oauth instance for backward compatibility
class LazyOAuth:
    """Lazy-loading OAuth wrapper for backward compatibility."""

    @property
    def oidc(self):
        """Get the OIDC client."""
        oauth_instance = get_oauth()
        return oauth_instance.oidc


oauth = LazyOAuth()
