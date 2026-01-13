"""
Pluggable configuration provider system for MLflow OIDC Auth Plugin.

This module provides a chain-of-responsibility pattern for loading configuration
from multiple sources (AWS Secrets Manager, Azure Key Vault, environment variables, etc.)
based on deployment environment.

Usage:
    from mlflow_oidc_auth.config_providers import config_manager

    # Get a config value (tries providers in order)
    value = config_manager.get("OIDC_CLIENT_SECRET")

    # Get with type conversion
    enabled = config_manager.get_bool("AUTOMATIC_LOGIN_REDIRECT", default=False)
"""

from mlflow_oidc_auth.config_providers.base import ConfigProvider, SecretLevel
from mlflow_oidc_auth.config_providers.manager import ConfigManager, config_manager

__all__ = [
    "ConfigProvider",
    "SecretLevel",
    "ConfigManager",
    "config_manager",
]
