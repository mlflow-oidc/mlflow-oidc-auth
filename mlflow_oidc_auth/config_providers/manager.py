"""
Configuration manager that orchestrates multiple configuration providers.

The ConfigManager implements a chain-of-responsibility pattern where configuration
values are retrieved from multiple sources in priority order. This enables
flexible deployment across different environments (AWS, Azure, Kubernetes, local).
"""

import os
import sys
from importlib.metadata import entry_points
from typing import Any

from mlflow_oidc_auth.config_providers.base import ConfigProvider
from mlflow_oidc_auth.config_providers.env_provider import EnvProvider
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


class ConfigManager:
    """Manages configuration retrieval from multiple providers.

    The ConfigManager maintains a list of configuration providers ordered by priority.
    When a configuration value is requested, it tries each provider in order until
    one returns a non-None value.

    Built-in Providers (in priority order):
        1. AWS Secrets Manager (priority 10) - for secrets
        2. Azure Key Vault (priority 10) - for secrets
        3. HashiCorp Vault (priority 10) - for secrets
        4. Kubernetes Secrets (priority 20) - mounted secret files
        5. AWS Parameter Store (priority 50) - for config values
        6. Environment Variables (priority 1000) - fallback

    Custom Providers:
        Additional providers can be registered via Python entry points
        in the 'mlflow_oidc_auth.config_providers' group.

    Configuration:
        CONFIG_PROVIDERS: Comma-separated list of providers to enable
                          (e.g., 'aws-secrets-manager,aws-parameter-store,env')
                          If not set, all available providers are used.

    Usage:
        from mlflow_oidc_auth.config_providers import config_manager

        # Get a value
        secret = config_manager.get("OIDC_CLIENT_SECRET")

        # Get with type conversion
        enabled = config_manager.get_bool("AUTOMATIC_LOGIN_REDIRECT", default=False)

        # Get list value
        groups = config_manager.get_list("OIDC_GROUP_NAME", separator=",")
    """

    def __init__(self, auto_discover: bool = True) -> None:
        """Initialize the ConfigManager.

        Parameters:
            auto_discover: If True, automatically discover and register
                           available providers. Set to False for testing.
        """
        self._providers: list[ConfigProvider] = []
        self._initialized = False

        if auto_discover:
            self._discover_providers()

    def _discover_providers(self) -> None:
        """Discover and register available configuration providers.

        This method:
            1. Loads built-in providers
            2. Loads providers from entry points
            3. Filters by CONFIG_PROVIDERS if set
            4. Sorts by priority
        """
        # Collect all potential providers
        all_providers: list[ConfigProvider] = []

        # Built-in providers
        all_providers.extend(self._load_builtin_providers())

        # Entry point providers
        all_providers.extend(self._load_entry_point_providers())

        # Filter by CONFIG_PROVIDERS if specified
        enabled_names = os.environ.get("CONFIG_PROVIDERS")
        if enabled_names:
            enabled_set = {name.strip() for name in enabled_names.split(",")}
            all_providers = [p for p in all_providers if p.name in enabled_set]

        # Filter to only available providers
        available_providers = [p for p in all_providers if p.is_available()]

        # Sort by priority (lower = higher priority)
        self._providers = sorted(available_providers, key=lambda p: p.priority)

        # Log active providers
        if self._providers:
            provider_names = [p.name for p in self._providers]
            logger.info(f"Config providers initialized: {', '.join(provider_names)}")
        else:
            logger.warning("No config providers available, using environment variables only")
            self._providers = [EnvProvider()]

        self._initialized = True

    def _load_builtin_providers(self) -> list[ConfigProvider]:
        """Load built-in configuration providers.

        Returns:
            List of instantiated provider objects.
        """
        providers: list[ConfigProvider] = []

        # AWS Secrets Manager
        try:
            from mlflow_oidc_auth.config_providers.aws_secrets_provider import AWSSecretsManagerProvider

            providers.append(AWSSecretsManagerProvider())
        except ImportError:
            pass

        # AWS Parameter Store
        try:
            from mlflow_oidc_auth.config_providers.aws_parameter_store_provider import AWSParameterStoreProvider

            providers.append(AWSParameterStoreProvider())
        except ImportError:
            pass

        # Azure Key Vault
        try:
            from mlflow_oidc_auth.config_providers.azure_keyvault_provider import AzureKeyVaultProvider

            providers.append(AzureKeyVaultProvider())
        except ImportError:
            pass

        # HashiCorp Vault
        try:
            from mlflow_oidc_auth.config_providers.vault_provider import HashiCorpVaultProvider

            providers.append(HashiCorpVaultProvider())
        except ImportError:
            pass

        # Kubernetes Secrets
        try:
            from mlflow_oidc_auth.config_providers.kubernetes_provider import KubernetesSecretsProvider

            providers.append(KubernetesSecretsProvider())
        except ImportError:
            pass

        # Environment variables (always included as fallback)
        providers.append(EnvProvider())

        return providers

    def _load_entry_point_providers(self) -> list[ConfigProvider]:
        """Load configuration providers from entry points.

        This allows third-party packages to register custom providers by
        defining an entry point in the 'mlflow_oidc_auth.config_providers' group.

        Example pyproject.toml:
            [project.entry-points."mlflow_oidc_auth.config_providers"]
            my-provider = "mypackage.provider:MyConfigProvider"

        Returns:
            List of instantiated provider objects from entry points.
        """
        providers: list[ConfigProvider] = []

        try:
            if sys.version_info >= (3, 10):
                eps = entry_points(group="mlflow_oidc_auth.config_providers")
            else:
                eps = entry_points().get("mlflow_oidc_auth.config_providers", [])

            for ep in eps:
                try:
                    provider_class = ep.load()
                    provider = provider_class()
                    if isinstance(provider, ConfigProvider):
                        providers.append(provider)
                        logger.debug(f"Loaded config provider from entry point: {ep.name}")
                except Exception as e:
                    logger.warning(f"Failed to load config provider {ep.name}: {e}")
        except Exception as e:
            logger.debug(f"Error loading entry point providers: {e}")

        return providers

    def register_provider(self, provider: ConfigProvider) -> None:
        """Register a configuration provider.

        The provider is inserted into the chain based on its priority.

        Parameters:
            provider: The provider to register.
        """
        self._providers.append(provider)
        self._providers.sort(key=lambda p: p.priority)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from the provider chain.

        Tries each provider in priority order until one returns a non-None value.

        Parameters:
            key: The configuration key to retrieve.
            default: Value to return if no provider has the key.

        Returns:
            The configuration value, or default if not found.
        """
        for provider in self._providers:
            value = provider.get(key)
            if value is not None:
                return value
        return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean configuration value.

        Recognizes 'true', '1', 't' (case-insensitive) as True.

        Parameters:
            key: The configuration key.
            default: Value to return if not found.

        Returns:
            The boolean value.
        """
        value = self.get(key)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "t")

    def get_int(self, key: str, default: int = 0) -> int:
        """Get an integer configuration value.

        Parameters:
            key: The configuration key.
            default: Value to return if not found or not an integer.

        Returns:
            The integer value.
        """
        value = self.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def get_list(self, key: str, default: list | None = None, separator: str = ",") -> list[str]:
        """Get a list configuration value.

        Splits a string value by separator and strips whitespace.

        Parameters:
            key: The configuration key.
            default: Value to return if not found.
            separator: String to split on.

        Returns:
            List of string values.
        """
        value = self.get(key)
        if value is None:
            return default if default is not None else []
        if isinstance(value, list):
            return value
        return [item.strip() for item in str(value).split(separator)]

    def refresh(self) -> None:
        """Refresh cached values from all providers.

        Call this when configuration needs to be reloaded, e.g., after
        a secret rotation.
        """
        for provider in self._providers:
            try:
                provider.refresh()
            except Exception as e:
                logger.warning(f"Error refreshing provider {provider.name}: {e}")

    def close(self) -> None:
        """Clean up all provider resources.

        Call this during application shutdown.
        """
        for provider in self._providers:
            try:
                provider.close()
            except Exception as e:
                logger.debug(f"Error closing provider {provider.name}: {e}")

    @property
    def providers(self) -> list[ConfigProvider]:
        """Get the list of active providers.

        Returns:
            List of providers in priority order.
        """
        return list(self._providers)

    def __repr__(self) -> str:
        provider_names = [p.name for p in self._providers]
        return f"<ConfigManager(providers={provider_names})>"


# Global singleton instance
config_manager = ConfigManager()
