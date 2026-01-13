"""
Azure Key Vault configuration provider.

This provider retrieves secrets from Azure Key Vault. It's designed for
Azure deployments (including Azure Marketplace) where sensitive configuration
should be stored in Key Vault.

Requires:
    - azure-identity and azure-keyvault-secrets libraries (optional dependencies)
    - Azure credentials configured (via env vars, managed identity, etc.)
    - CONFIG_AZURE_KEYVAULT_ENABLED=true environment variable
"""

import os
from typing import Any

from mlflow_oidc_auth.config_providers.base import ConfigProvider, SecretLevel, get_secret_level


class AzureKeyVaultProvider(ConfigProvider):
    """Configuration provider that reads from Azure Key Vault.

    Secrets are retrieved from Azure Key Vault. Secret names in Key Vault
    should use hyphens instead of underscores (Azure naming convention),
    so 'OIDC_CLIENT_SECRET' becomes 'OIDC-CLIENT-SECRET'.

    Configuration:
        CONFIG_AZURE_KEYVAULT_ENABLED: Set to 'true' to enable this provider
        CONFIG_AZURE_KEYVAULT_NAME: Name of the Key Vault (required)
        CONFIG_AZURE_KEYVAULT_CACHE_TTL: Cache TTL in seconds (default: 300)

    Authentication:
        Uses DefaultAzureCredential which supports:
        - Managed Identity (recommended for Azure deployments)
        - Environment variables (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)
        - Azure CLI credentials (for local development)
    """

    def __init__(self) -> None:
        self._client = None
        self._cache: dict[str, Any] = {}
        self._vault_name = os.environ.get("CONFIG_AZURE_KEYVAULT_NAME", "")
        self._initialized = False

    @property
    def name(self) -> str:
        return "azure-keyvault"

    @property
    def priority(self) -> int:
        return 10  # High priority for secrets

    def is_available(self) -> bool:
        """Check if Azure Key Vault provider is available.

        Returns True if:
            - CONFIG_AZURE_KEYVAULT_ENABLED is set to 'true'
            - CONFIG_AZURE_KEYVAULT_NAME is set
            - azure-identity and azure-keyvault-secrets libraries are installed
        """
        if os.environ.get("CONFIG_AZURE_KEYVAULT_ENABLED", "").lower() != "true":
            return False

        if not self._vault_name:
            return False

        try:
            from azure.identity import DefaultAzureCredential  # noqa: F401
            from azure.keyvault.secrets import SecretClient  # noqa: F401

            return True
        except ImportError:
            return False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of Azure Key Vault client."""
        if self._initialized:
            return

        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        vault_url = f"https://{self._vault_name}.vault.azure.net"
        credential = DefaultAzureCredential()
        self._client = SecretClient(vault_url=vault_url, credential=credential)
        self._initialized = True

    def _key_to_secret_name(self, key: str) -> str:
        """Convert config key to Azure Key Vault secret name.

        Azure Key Vault doesn't allow underscores in secret names,
        so we convert underscores to hyphens.

        Parameters:
            key: The configuration key (e.g., 'OIDC_CLIENT_SECRET').

        Returns:
            The Key Vault secret name (e.g., 'OIDC-CLIENT-SECRET').
        """
        return key.replace("_", "-")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from Azure Key Vault.

        Only retrieves values classified as SECRET or SENSITIVE.
        For PUBLIC values, returns default to let other providers handle them.

        Parameters:
            key: The configuration key.
            default: Value to return if not found.

        Returns:
            The secret value, or default if not found.
        """
        # Only handle secrets and sensitive values
        level = get_secret_level(key)
        if level == SecretLevel.PUBLIC:
            return default

        # Check cache first
        if key in self._cache:
            return self._cache[key]

        self._ensure_initialized()

        try:
            secret_name = self._key_to_secret_name(key)
            secret = self._client.get_secret(secret_name)
            value = secret.value
            self._cache[key] = value
            return value
        except Exception:
            # Secret not found or access denied
            return default

    def refresh(self) -> None:
        """Clear cache to force reload from Key Vault."""
        self._cache = {}

    def close(self) -> None:
        """Clean up Azure client resources."""
        if self._client:
            self._client.close()
        self._client = None
        self._cache = {}
        self._initialized = False
