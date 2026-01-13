"""
HashiCorp Vault configuration provider.

This provider retrieves secrets from HashiCorp Vault. It's ideal for
multi-cloud or on-premise deployments using Vault for secrets management.

Requires:
    - hvac library (optional dependency)
    - Vault address and authentication configured
    - CONFIG_VAULT_ENABLED=true environment variable
"""

import os
from typing import Any

from mlflow_oidc_auth.config_providers.base import ConfigProvider, SecretLevel, get_secret_level


class HashiCorpVaultProvider(ConfigProvider):
    """Configuration provider that reads from HashiCorp Vault.

    Secrets are retrieved from a configurable path in Vault's KV secrets engine.
    Supports both KV v1 and v2 (default).

    Configuration:
        CONFIG_VAULT_ENABLED: Set to 'true' to enable this provider
        CONFIG_VAULT_ADDR: Vault server address (default: http://localhost:8200)
        CONFIG_VAULT_TOKEN: Vault authentication token (for token auth)
        CONFIG_VAULT_ROLE_ID: Vault AppRole role ID (for AppRole auth)
        CONFIG_VAULT_SECRET_ID: Vault AppRole secret ID (for AppRole auth)
        CONFIG_VAULT_PATH: Path to secrets (default: 'secret/data/mlflow-oidc-auth')
        CONFIG_VAULT_NAMESPACE: Vault namespace (optional, for enterprise)
        CONFIG_VAULT_KV_VERSION: KV engine version, 1 or 2 (default: 2)

    Authentication:
        Supports token authentication and AppRole authentication.
        Token auth is used if CONFIG_VAULT_TOKEN is set.
        AppRole auth is used if CONFIG_VAULT_ROLE_ID and CONFIG_VAULT_SECRET_ID are set.
    """

    def __init__(self) -> None:
        self._client = None
        self._cache: dict[str, Any] = {}
        self._addr = os.environ.get("CONFIG_VAULT_ADDR", "http://localhost:8200")
        self._token = os.environ.get("CONFIG_VAULT_TOKEN")
        self._role_id = os.environ.get("CONFIG_VAULT_ROLE_ID")
        self._secret_id = os.environ.get("CONFIG_VAULT_SECRET_ID")
        self._path = os.environ.get("CONFIG_VAULT_PATH", "secret/data/mlflow-oidc-auth")
        self._namespace = os.environ.get("CONFIG_VAULT_NAMESPACE")
        self._kv_version = int(os.environ.get("CONFIG_VAULT_KV_VERSION", "2"))
        self._initialized = False

    @property
    def name(self) -> str:
        return "hashicorp-vault"

    @property
    def priority(self) -> int:
        return 10  # High priority for secrets

    def is_available(self) -> bool:
        """Check if HashiCorp Vault provider is available.

        Returns True if:
            - CONFIG_VAULT_ENABLED is set to 'true'
            - hvac library is installed
            - Either token or AppRole credentials are configured
        """
        if os.environ.get("CONFIG_VAULT_ENABLED", "").lower() != "true":
            return False

        # Need either token or AppRole credentials
        has_auth = bool(self._token) or (bool(self._role_id) and bool(self._secret_id))
        if not has_auth:
            return False

        try:
            import hvac  # noqa: F401

            return True
        except ImportError:
            return False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of Vault client and secrets cache."""
        if self._initialized:
            return

        import hvac

        self._client = hvac.Client(url=self._addr, namespace=self._namespace)

        # Authenticate
        if self._token:
            self._client.token = self._token
        elif self._role_id and self._secret_id:
            self._client.auth.approle.login(role_id=self._role_id, secret_id=self._secret_id)

        self._load_secrets()
        self._initialized = True

    def _load_secrets(self) -> None:
        """Load all secrets from Vault path into cache."""
        if self._client is None:
            return

        try:
            if self._kv_version == 2:
                # KV v2 returns data under 'data' -> 'data'
                response = self._client.secrets.kv.v2.read_secret_version(path=self._path.split("/")[-1], mount_point=self._path.rsplit("/", 1)[0] if "/" in self._path else "secret")
                self._cache = response.get("data", {}).get("data", {})
            else:
                # KV v1 returns data directly under 'data'
                response = self._client.secrets.kv.v1.read_secret(path=self._path)
                self._cache = response.get("data", {})
        except Exception:
            self._cache = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from HashiCorp Vault.

        Only retrieves values classified as SECRET or SENSITIVE.

        Parameters:
            key: The configuration key.
            default: Value to return if not found.

        Returns:
            The secret value, or default if not found.
        """
        level = get_secret_level(key)
        if level == SecretLevel.PUBLIC:
            return default

        self._ensure_initialized()
        return self._cache.get(key, default)

    def refresh(self) -> None:
        """Reload secrets from Vault."""
        if self._initialized:
            self._load_secrets()

    def close(self) -> None:
        """Clean up Vault client resources."""
        self._client = None
        self._cache = {}
        self._initialized = False
