"""
AWS Systems Manager Parameter Store configuration provider.

This provider retrieves configuration from AWS SSM Parameter Store. It's ideal for
non-secret configuration values that need to be managed centrally in AWS.

Requires:
    - boto3 library (optional dependency)
    - AWS credentials configured (via env vars, instance role, etc.)
    - CONFIG_AWS_PARAMETER_STORE_ENABLED=true environment variable
"""

import os
from typing import Any

from mlflow_oidc_auth.config_providers.base import ConfigProvider, SecretLevel, get_secret_level


class AWSParameterStoreProvider(ConfigProvider):
    """Configuration provider that reads from AWS SSM Parameter Store.

    Parameters are retrieved using a configurable prefix. For example, with
    prefix '/mlflow-oidc-auth/', the key 'OIDC_DISCOVERY_URL' would be
    retrieved from '/mlflow-oidc-auth/OIDC_DISCOVERY_URL'.

    Configuration:
        CONFIG_AWS_PARAMETER_STORE_ENABLED: Set to 'true' to enable
        CONFIG_AWS_PARAMETER_STORE_PREFIX: Parameter path prefix
                                           (default: '/mlflow-oidc-auth/')
        CONFIG_AWS_PARAMETER_STORE_REGION: AWS region
        CONFIG_AWS_PARAMETER_STORE_CACHE_TTL: Cache TTL in seconds (default: 300)

    Note:
        This provider is intended for non-secret configuration. For secrets,
        use AWSSecretsManagerProvider instead.
    """

    def __init__(self) -> None:
        self._client = None
        self._cache: dict[str, Any] = {}
        self._prefix = os.environ.get("CONFIG_AWS_PARAMETER_STORE_PREFIX", "/mlflow-oidc-auth/")
        self._region = os.environ.get("CONFIG_AWS_PARAMETER_STORE_REGION", os.environ.get("AWS_REGION", "us-east-1"))
        self._initialized = False

    @property
    def name(self) -> str:
        return "aws-parameter-store"

    @property
    def priority(self) -> int:
        return 50  # Medium priority for config values

    def is_available(self) -> bool:
        """Check if AWS Parameter Store provider is available.

        Returns True if:
            - CONFIG_AWS_PARAMETER_STORE_ENABLED is set to 'true'
            - boto3 library is installed
        """
        if os.environ.get("CONFIG_AWS_PARAMETER_STORE_ENABLED", "").lower() != "true":
            return False

        try:
            import boto3  # noqa: F401

            return True
        except ImportError:
            return False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of AWS SSM client."""
        if self._initialized:
            return

        import boto3

        self._client = boto3.client("ssm", region_name=self._region)
        self._load_parameters()
        self._initialized = True

    def _load_parameters(self) -> None:
        """Load all parameters with the configured prefix into cache."""
        if self._client is None:
            return

        try:
            paginator = self._client.get_paginator("get_parameters_by_path")
            for page in paginator.paginate(Path=self._prefix, Recursive=True, WithDecryption=True):
                for param in page.get("Parameters", []):
                    # Extract key name from full path
                    key = param["Name"].replace(self._prefix, "")
                    self._cache[key] = param["Value"]
        except Exception:
            # Log error but don't fail - allow fallback to other providers
            self._cache = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from AWS Parameter Store.

        Only retrieves values classified as PUBLIC or SENSITIVE (not SECRET).
        Secrets should come from Secrets Manager.

        Parameters:
            key: The configuration key.
            default: Value to return if not found.

        Returns:
            The parameter value, or default if not found.
        """
        # Don't handle secrets - those should come from Secrets Manager
        level = get_secret_level(key)
        if level == SecretLevel.SECRET:
            return default

        self._ensure_initialized()
        return self._cache.get(key, default)

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple parameters at once.

        Parameters:
            keys: List of parameter names (without prefix).

        Returns:
            Dictionary of found key-value pairs.
        """
        self._ensure_initialized()
        return {key: self._cache[key] for key in keys if key in self._cache}

    def refresh(self) -> None:
        """Reload parameters from AWS Parameter Store."""
        if self._initialized:
            self._cache = {}
            self._load_parameters()

    def close(self) -> None:
        """Clean up AWS client resources."""
        self._client = None
        self._cache = {}
        self._initialized = False
