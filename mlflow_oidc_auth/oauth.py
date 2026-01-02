"""OAuth configuration for the FastAPI application.

Unit tests expect the module attribute `oauth` to be an instance of
`authlib.integrations.starlette_client.OAuth`.

We keep OIDC client registration lazy so importing this module does not require
OIDC configuration to be present (and does not perform network calls).
"""

from __future__ import annotations

from authlib.integrations.starlette_client import OAuth

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

oauth: OAuth = OAuth()
_oidc_client_registered: bool = False


def get_oauth() -> OAuth:
    """Return the module-level OAuth instance."""

    return oauth


def _has_required_config() -> bool:
    return bool(config.OIDC_CLIENT_ID and config.OIDC_CLIENT_SECRET and config.OIDC_DISCOVERY_URL)


def ensure_oidc_client_registered() -> bool:
    """Ensure the 'oidc' client is registered.

    Returns False if config is incomplete or registration fails.
    """

    global _oidc_client_registered

    if _oidc_client_registered:
        return True

    if not _has_required_config():
        return False

    try:
        oauth.register(
            name="oidc",
            client_id=config.OIDC_CLIENT_ID,
            client_secret=config.OIDC_CLIENT_SECRET,
            server_metadata_url=config.OIDC_DISCOVERY_URL,
            client_kwargs={"scope": config.OIDC_SCOPE},
        )
        _oidc_client_registered = True
        return True
    except Exception as exc:
        logger.warning(f"Failed to register OIDC client: {exc}")
        return False


def is_oidc_configured() -> bool:
    """Return True if OIDC config is present and the client is registered."""

    return ensure_oidc_client_registered()


def reset_oauth() -> None:
    """Reset the OAuth instance and registration state (primarily for tests)."""

    global oauth, _oidc_client_registered
    oauth = OAuth()
    _oidc_client_registered = False
