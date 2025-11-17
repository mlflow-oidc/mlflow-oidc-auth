"""
Application configuration for MLflow OIDC Auth Plugin.

This module provides configuration management with support for multiple
configuration sources (environment variables, AWS Secrets Manager, Azure Key Vault,
Kubernetes Secrets, etc.) through the pluggable provider system.

Environment Variables for Provider Configuration:
    CONFIG_AWS_SECRETS_ENABLED: Enable AWS Secrets Manager provider
    CONFIG_AWS_PARAMETER_STORE_ENABLED: Enable AWS Parameter Store provider
    CONFIG_AZURE_KEYVAULT_ENABLED: Enable Azure Key Vault provider
    CONFIG_VAULT_ENABLED: Enable HashiCorp Vault provider
    CONFIG_K8S_SECRETS_ENABLED: Enable Kubernetes Secrets provider
    CONFIG_PROVIDERS: Comma-separated list of providers to use (optional filter)

See config_providers/ for detailed configuration of each provider.
"""

import secrets

from dotenv import load_dotenv

from mlflow_oidc_auth.config_providers import config_manager
from mlflow_oidc_auth.logger import get_logger

load_dotenv()  # take environment variables from .env.
logger = get_logger()


def get_bool_env_variable(variable: str, default_value: bool) -> bool:
    """Get a boolean value from configuration.

    Parameters:
        variable: The configuration key name.
        default_value: Default value if not found.

    Returns:
        Boolean value parsed from configuration.
    """
    return config_manager.get_bool(variable, default=default_value)


class AppConfig:
    """Application configuration container.

    This class loads configuration from the pluggable provider system,
    which supports multiple sources in priority order:
        1. Cloud providers (AWS Secrets Manager, Azure Key Vault, etc.)
        2. Kubernetes Secrets (mounted as files)
        3. Environment variables (fallback)

    Attributes:
        DEFAULT_MLFLOW_PERMISSION: Default permission level for new resources.
        SECRET_KEY: Secret key for session management.
        OIDC_USERS_DB_URI: Database URI for user/permission storage.
        OIDC_CLIENT_ID: OAuth client ID.
        OIDC_CLIENT_SECRET: OAuth client secret (sensitive).
        ... and more (see source for full list)
    """

    def __init__(self) -> None:
        """Initialize configuration from the provider chain."""
        # Permission settings
        self.DEFAULT_MLFLOW_PERMISSION = config_manager.get("DEFAULT_MLFLOW_PERMISSION", "MANAGE")
        self.PERMISSION_SOURCE_ORDER = config_manager.get_list("PERMISSION_SOURCE_ORDER", default=["user", "group", "regex", "group-regex"])

        # Security settings (secrets - may come from Secrets Manager/Key Vault)
        self.SECRET_KEY = config_manager.get("SECRET_KEY") or secrets.token_hex(16)
        self.OIDC_CLIENT_SECRET = config_manager.get("OIDC_CLIENT_SECRET")

        # Database settings (sensitive)
        self.OIDC_USERS_DB_URI = config_manager.get("OIDC_USERS_DB_URI", "sqlite:///auth.db")

        # OIDC provider settings
        self.OIDC_DISCOVERY_URL = config_manager.get("OIDC_DISCOVERY_URL")
        self.OIDC_CLIENT_ID = config_manager.get("OIDC_CLIENT_ID")
        # OIDC_REDIRECT_URI: If not set, will be calculated dynamically based on request headers
        # This enables automatic proxy path detection for OIDC callbacks
        self.OIDC_REDIRECT_URI = config_manager.get("OIDC_REDIRECT_URI")
        self.OIDC_SCOPE = config_manager.get("OIDC_SCOPE", "openid,email,profile")
        self.OIDC_PROVIDER_DISPLAY_NAME = config_manager.get("OIDC_PROVIDER_DISPLAY_NAME", "Login with OIDC")
        self.OIDC_GROUPS_ATTRIBUTE = config_manager.get("OIDC_GROUPS_ATTRIBUTE", "groups")

        # Group settings
        # OIDC_GROUP_NAME_DELIMITER allows custom delimiter for group names (default: comma)
        # This is useful when group names contain commas, e.g., "CN=mygroup,OU=Groups,..."
        self.OIDC_GROUP_NAME_DELIMITER = config_manager.get("OIDC_GROUP_NAME_DELIMITER", ",")
        self.OIDC_GROUP_NAME = config_manager.get_list("OIDC_GROUP_NAME", default=["mlflow"], separator=self.OIDC_GROUP_NAME_DELIMITER)
        self.OIDC_ADMIN_GROUP_NAME = config_manager.get_list("OIDC_ADMIN_GROUP_NAME", default=["mlflow-admin"], separator=self.OIDC_GROUP_NAME_DELIMITER)
        self.OIDC_GROUP_DETECTION_PLUGIN = config_manager.get("OIDC_GROUP_DETECTION_PLUGIN")

        # Database migration settings
        self.OIDC_ALEMBIC_VERSION_TABLE = config_manager.get("OIDC_ALEMBIC_VERSION_TABLE", "alembic_version")

        # UI settings
        self.EXTEND_MLFLOW_MENU = config_manager.get_bool("EXTEND_MLFLOW_MENU", default=True)
        self.DEFAULT_LANDING_PAGE_IS_PERMISSIONS = config_manager.get_bool("DEFAULT_LANDING_PAGE_IS_PERMISSIONS", default=True)
        self.AUTOMATIC_LOGIN_REDIRECT = config_manager.get_bool("AUTOMATIC_LOGIN_REDIRECT", default=False)

    def refresh(self) -> None:
        """Reload configuration from all providers.

        Call this method to reload configuration after secret rotation
        or configuration changes.
        """
        config_manager.refresh()
        self.__init__()


config = AppConfig()
