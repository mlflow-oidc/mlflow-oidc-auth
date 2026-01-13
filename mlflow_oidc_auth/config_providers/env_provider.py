"""
Environment variables configuration provider.

This is the default/fallback provider that reads configuration from environment
variables. It's always available and typically has the lowest priority.
"""

import os
from typing import Any

from mlflow_oidc_auth.config_providers.base import ConfigProvider


class EnvProvider(ConfigProvider):
    """Configuration provider that reads from environment variables.

    This provider is always available and serves as the default fallback
    in the provider chain. It reads values from os.environ.

    Supports:
        - Reading from .env files (via python-dotenv, loaded separately)
        - Standard environment variable access
    """

    @property
    def name(self) -> str:
        return "env"

    @property
    def priority(self) -> int:
        return 1000  # Lowest priority - fallback

    def is_available(self) -> bool:
        """Environment variables are always available."""
        return True

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from environment variables.

        Parameters:
            key: The environment variable name.
            default: Value to return if not found.

        Returns:
            The environment variable value, or default if not set.
        """
        return os.environ.get(key, default)

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple environment variables at once.

        Parameters:
            keys: List of environment variable names.

        Returns:
            Dictionary of found key-value pairs.
        """
        return {key: value for key in keys if (value := os.environ.get(key)) is not None}
