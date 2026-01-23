"""
MLflow server environment configuration.

This module provides utilities to configure MLflow server parameters via
the pluggable configuration provider system. It sets MLflow-specific
environment variables that the mlflow CLI reads on startup.

IMPORTANT: Due to timing, this must be called BEFORE mlflow server starts:
    - The `mlflow server` CLI parses env vars immediately on startup
    - Our plugin code runs AFTER MLflow has already parsed its config
    - Therefore, use `mlflow-oidc-server` command or call configure_mlflow_environment()
      in a custom entrypoint before starting MLflow

Usage Options:
    1. Use `mlflow-oidc-server` CLI (recommended for cloud):
       $ mlflow-oidc-server --host 0.0.0.0 --port 8080

    2. Use MLflow's --env-file for .env files (local dev):
       $ mlflow --env-file .env server --app-name oidc-auth

    3. Set env vars in container/K8s (already available before startup):
       Works automatically with standard `mlflow server`
"""

import os
from typing import Any

from mlflow_oidc_auth.config_providers import config_manager
from mlflow_oidc_auth.config_providers.base import SECRET_CLASSIFICATION, SecretLevel
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


# MLflow server parameters that can be configured via environment variables
# Maps our config key to MLflow's expected environment variable name
MLFLOW_ENV_MAPPINGS: dict[str, str] = {
    # Database/Backend Store
    "MLFLOW_BACKEND_STORE_URI": "MLFLOW_BACKEND_STORE_URI",
    "MLFLOW_REGISTRY_STORE_URI": "MLFLOW_REGISTRY_STORE_URI",
    # Artifacts
    "MLFLOW_DEFAULT_ARTIFACT_ROOT": "MLFLOW_DEFAULT_ARTIFACT_ROOT",
    "MLFLOW_ARTIFACTS_DESTINATION": "MLFLOW_ARTIFACTS_DESTINATION",
    "MLFLOW_SERVE_ARTIFACTS": "MLFLOW_SERVE_ARTIFACTS",
    "MLFLOW_ARTIFACTS_ONLY": "MLFLOW_ARTIFACTS_ONLY",
    # Server configuration
    "MLFLOW_WORKERS": "MLFLOW_WORKERS",
    "MLFLOW_GUNICORN_OPTS": "MLFLOW_GUNICORN_OPTS",
    "MLFLOW_UVICORN_OPTS": "MLFLOW_UVICORN_OPTS",
    "MLFLOW_STATIC_PREFIX": "MLFLOW_STATIC_PREFIX",
    # Flask/Session
    "MLFLOW_FLASK_SERVER_SECRET_KEY": "MLFLOW_FLASK_SERVER_SECRET_KEY",
}

# Add MLflow parameters to the secret classification
# These should be retrieved from secure providers
SECRET_CLASSIFICATION.update(
    {
        "MLFLOW_BACKEND_STORE_URI": SecretLevel.SECRET,  # Contains DB password
        "MLFLOW_REGISTRY_STORE_URI": SecretLevel.SECRET,  # May contain DB password
        "MLFLOW_FLASK_SERVER_SECRET_KEY": SecretLevel.SECRET,
    }
)


def configure_mlflow_environment(
    override_existing: bool = False,
) -> dict[str, Any]:
    """Configure MLflow environment variables from config providers.

    Loads MLflow configuration parameters from the config provider chain
    (AWS Secrets Manager, Azure Key Vault, etc.) and sets them as environment
    variables that the mlflow CLI will read.

    Parameters:
        override_existing: If True, override existing environment variables.
                          If False (default), only set if not already present.

    Returns:
        Dictionary of environment variables that were set.

    Example:
        # In your startup script or entrypoint:
        from mlflow_oidc_auth.config_providers.mlflow_env import configure_mlflow_environment

        # Load MLflow config from secure providers
        configured = configure_mlflow_environment()
        print(f"Configured MLflow vars: {list(configured.keys())}")

        # Now start mlflow server (without sensitive args on command line)
        # mlflow server --app-name oidc-auth --host 0.0.0.0 --port 8080
    """
    configured = {}

    for config_key, env_var in MLFLOW_ENV_MAPPINGS.items():
        # Skip if already set and not overriding
        if not override_existing and os.environ.get(env_var):
            logger.debug(f"Skipping {env_var}: already set in environment")
            continue

        value = config_manager.get(config_key)
        if value is not None:
            os.environ[env_var] = str(value)
            configured[env_var] = value
            # Log without showing secret values
            if SECRET_CLASSIFICATION.get(config_key) in (SecretLevel.SECRET, SecretLevel.SENSITIVE):
                logger.info(f"Configured {env_var} from provider (value hidden)")
            else:
                logger.info(f"Configured {env_var}={value}")

    return configured


def get_mlflow_config_summary() -> dict[str, str]:
    """Get a summary of MLflow configuration (with secrets masked).

    Returns:
        Dictionary mapping MLflow env vars to their values (secrets masked).
    """
    summary = {}
    for config_key, env_var in MLFLOW_ENV_MAPPINGS.items():
        value = os.environ.get(env_var)
        if value:
            if SECRET_CLASSIFICATION.get(config_key) in (SecretLevel.SECRET, SecretLevel.SENSITIVE):
                summary[env_var] = "********"
            else:
                summary[env_var] = value
    return summary
