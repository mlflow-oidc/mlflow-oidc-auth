"""
Kubernetes Secrets configuration provider.

This provider reads secrets from Kubernetes Secrets mounted as files.
In Kubernetes, secrets can be mounted as files in a pod's filesystem,
and this provider reads from those files.

Requires:
    - Secrets mounted as files in a known directory
    - CONFIG_K8S_SECRETS_ENABLED=true environment variable
"""

import os
from pathlib import Path
from typing import Any

from mlflow_oidc_auth.config_providers.base import ConfigProvider, SecretLevel, get_secret_level


class KubernetesSecretsProvider(ConfigProvider):
    """Configuration provider that reads from Kubernetes Secrets mounted as files.

    In Kubernetes, secrets can be mounted as files where each key becomes a file
    with the secret value as its content. This provider reads from those files.

    Configuration:
        CONFIG_K8S_SECRETS_ENABLED: Set to 'true' to enable this provider
        CONFIG_K8S_SECRETS_PATH: Path where secrets are mounted
                                 (default: '/var/run/secrets/mlflow-oidc-auth')

    Example Kubernetes Secret Mount:
        volumeMounts:
          - name: mlflow-secrets
            mountPath: /var/run/secrets/mlflow-oidc-auth
            readOnly: true
        volumes:
          - name: mlflow-secrets
            secret:
              secretName: mlflow-oidc-auth-secrets

    The secret would contain keys like 'OIDC_CLIENT_SECRET' which become files
    at '/var/run/secrets/mlflow-oidc-auth/OIDC_CLIENT_SECRET'.
    """

    def __init__(self) -> None:
        self._secrets_path = Path(os.environ.get("CONFIG_K8S_SECRETS_PATH", "/var/run/secrets/mlflow-oidc-auth"))
        self._cache: dict[str, Any] = {}
        self._initialized = False

    @property
    def name(self) -> str:
        return "kubernetes-secrets"

    @property
    def priority(self) -> int:
        return 20  # High priority, but after cloud providers

    def is_available(self) -> bool:
        """Check if Kubernetes Secrets provider is available.

        Returns True if:
            - CONFIG_K8S_SECRETS_ENABLED is set to 'true'
            - The secrets directory exists
        """
        if os.environ.get("CONFIG_K8S_SECRETS_ENABLED", "").lower() != "true":
            return False

        return self._secrets_path.is_dir()

    def _ensure_initialized(self) -> None:
        """Load all secrets from mounted files into cache."""
        if self._initialized:
            return

        self._load_secrets()
        self._initialized = True

    def _load_secrets(self) -> None:
        """Load all secret files into cache."""
        self._cache = {}

        if not self._secrets_path.is_dir():
            return

        for secret_file in self._secrets_path.iterdir():
            if secret_file.is_file() and not secret_file.name.startswith("."):
                try:
                    # Read secret value, strip trailing newlines (common in K8s secrets)
                    value = secret_file.read_text().rstrip("\n\r")
                    self._cache[secret_file.name] = value
                except Exception:
                    # Skip files that can't be read
                    pass

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from Kubernetes mounted secrets.

        Only retrieves values classified as SECRET or SENSITIVE.

        Parameters:
            key: The configuration key (matches the filename in secrets mount).
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
        """Reload secrets from mounted files."""
        self._cache = {}
        self._load_secrets()

    def close(self) -> None:
        """Clean up resources."""
        self._cache = {}
        self._initialized = False
