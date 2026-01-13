"""
Base classes and protocols for configuration providers.

This module defines the abstract base class that all configuration providers must implement,
along with utility enums and helper functions for config value classification.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


class SecretLevel(Enum):
    """Classification of configuration values by sensitivity level.

    Used to determine which provider should handle a given config key,
    and how values should be logged/cached.
    """

    PUBLIC = "public"  # Non-sensitive, can be logged
    SENSITIVE = "sensitive"  # Should not be logged, but can be in config files
    SECRET = "secret"  # Must come from secure storage (Secrets Manager, Key Vault, etc.)


# Mapping of known config keys to their sensitivity levels
SECRET_CLASSIFICATION: dict[str, SecretLevel] = {
    # Secrets - must be stored securely
    "SECRET_KEY": SecretLevel.SECRET,
    "OIDC_CLIENT_SECRET": SecretLevel.SECRET,
    # Sensitive - should not be logged
    "OIDC_USERS_DB_URI": SecretLevel.SENSITIVE,
    "OIDC_CLIENT_ID": SecretLevel.SENSITIVE,
    # Everything else is public by default
}


def get_secret_level(key: str) -> SecretLevel:
    """Get the sensitivity level for a configuration key.

    Parameters:
        key: The configuration key name.

    Returns:
        The SecretLevel for this key, defaulting to PUBLIC if not classified.
    """
    return SECRET_CLASSIFICATION.get(key, SecretLevel.PUBLIC)


class ConfigProvider(ABC):
    """Abstract base class for configuration providers.

    Configuration providers implement a chain-of-responsibility pattern.
    Each provider attempts to resolve a config key; if it cannot, the next
    provider in the chain is tried.

    Subclasses must implement:
        - name: A unique identifier for the provider
        - is_available(): Check if the provider can be used in current environment
        - get(): Retrieve a configuration value by key
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this provider.

        Returns:
            A string name like 'aws-secrets-manager', 'azure-keyvault', 'env'.
        """
        ...

    @property
    def priority(self) -> int:
        """Priority for this provider (lower = higher priority).

        Returns:
            An integer priority. Default is 100.
        """
        return 100

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available in the current environment.

        This is called once during initialization to determine if the provider
        should be included in the chain. Implementations should check for
        required SDKs, credentials, or environment markers.

        Returns:
            True if the provider can be used, False otherwise.
        """
        ...

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a configuration value by key.

        Parameters:
            key: The configuration key to retrieve (e.g., 'OIDC_CLIENT_SECRET').
            default: Value to return if key is not found in this provider.

        Returns:
            The configuration value, or default if not found.
        """
        ...

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Retrieve multiple configuration values at once.

        Default implementation calls get() for each key. Providers that support
        batch operations (like AWS Parameter Store) should override this.

        Parameters:
            keys: List of configuration keys to retrieve.

        Returns:
            Dictionary mapping keys to their values. Missing keys are omitted.
        """
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result

    def refresh(self) -> None:
        """Refresh cached values from the provider.

        Called when configuration needs to be reloaded. Default is no-op.
        Providers with caching should override this.
        """
        pass

    def close(self) -> None:
        """Clean up provider resources.

        Called during application shutdown. Default is no-op.
        Providers with connections should override this.
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name}, priority={self.priority})>"
