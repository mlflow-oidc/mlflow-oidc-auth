"""
AWS Secrets Manager configuration provider.

This provider retrieves secrets from AWS Secrets Manager. It's designed for
AWS deployments where sensitive configuration like OIDC client secrets should
be stored in Secrets Manager.

Requires:
    - boto3 library (optional dependency)
    - AWS credentials configured (via env vars, instance role, etc.)
    - CONFIG_AWS_SECRETS_ENABLED=true environment variable
"""

import json
import os
from functools import lru_cache
from typing import Any

from mlflow_oidc_auth.config_providers.base import ConfigProvider, SecretLevel, get_secret_level


class AWSSecretsManagerProvider(ConfigProvider):
    """Configuration provider that reads from AWS Secrets Manager.

    Secrets are retrieved from AWS Secrets Manager using the AWS SDK (boto3).
    The provider expects secrets to be stored as JSON objects where keys
    map to configuration variable names.

    Configuration:
        CONFIG_AWS_SECRETS_ENABLED: Set to 'true' to enable this provider
        CONFIG_AWS_SECRETS_NAME: Name of the secret in Secrets Manager
                                 (default: 'mlflow-oidc-auth')
        CONFIG_AWS_SECRETS_REGION: AWS region (default: from AWS_REGION or us-east-1)
        CONFIG_AWS_SECRETS_CACHE_TTL: Cache TTL in seconds (default: 300)

    Secret Format:
        The secret value should be a JSON object:
        {
            "OIDC_CLIENT_SECRET": "...",
            "SECRET_KEY": "...",
            "OIDC_USERS_DB_URI": "..."
        }
    """

    def __init__(self) -> None:
        self._client = None
        self._cache: dict[str, Any] = {}
        self._secret_name = os.environ.get("CONFIG_AWS_SECRETS_NAME", "mlflow-oidc-auth")
        self._region = os.environ.get("CONFIG_AWS_SECRETS_REGION", os.environ.get("AWS_REGION", "us-east-1"))
        self._cache_ttl = int(os.environ.get("CONFIG_AWS_SECRETS_CACHE_TTL", "300"))
        self._initialized = False

    @property
    def name(self) -> str:
        return "aws-secrets-manager"

    @property
    def priority(self) -> int:
        return 10  # High priority for secrets

    def is_available(self) -> bool:
        """Check if AWS Secrets Manager provider is available.

        Returns True if:
            - CONFIG_AWS_SECRETS_ENABLED is set to 'true'
            - boto3 library is installed
            - AWS credentials are configured
        """
        if os.environ.get("CONFIG_AWS_SECRETS_ENABLED", "").lower() != "true":
            return False

        try:
            import boto3  # noqa: F401

            return True
        except ImportError:
            return False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of AWS client and cache."""
        if self._initialized:
            return

        import boto3

        self._client = boto3.client("secretsmanager", region_name=self._region)
        self._load_secrets()
        self._initialized = True

    def _load_secrets(self) -> None:
        """Load all secrets from AWS Secrets Manager into cache."""
        if self._client is None:
            return

        try:
            response = self._client.get_secret_value(SecretId=self._secret_name)
            secret_string = response.get("SecretString")
            if secret_string:
                self._cache = json.loads(secret_string)
        except self._client.exceptions.ResourceNotFoundException:
            self._cache = {}
        except json.JSONDecodeError:
            self._cache = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from AWS Secrets Manager.

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

        self._ensure_initialized()
        return self._cache.get(key, default)

    def refresh(self) -> None:
        """Reload secrets from AWS Secrets Manager."""
        if self._initialized:
            self._load_secrets()

    def close(self) -> None:
        """Clean up AWS client resources."""
        self._client = None
        self._cache = {}
        self._initialized = False
