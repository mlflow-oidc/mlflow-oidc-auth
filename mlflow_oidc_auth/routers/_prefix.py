from mlflow.server.handlers import _get_rest_path

"""
Router prefix constants for the FastAPI application.

This module defines all router prefixes used throughout the application
to ensure consistency and easy maintenance of URL structures.
"""

EXPERIMENT_PERMISSIONS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/experiments")
GROUP_PERMISSIONS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/groups")
PROMPT_PERMISSIONS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/prompts")
REGISTERED_MODEL_PERMISSIONS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/registered-models")
USER_PERMISSIONS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/users")
SCORERS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/scorers", version=3)
USERS_ROUTER_PREFIX = _get_rest_path("/mlflow/users")
HEALTH_CHECK_ROUTER_PREFIX = "/health"
UI_ROUTER_PREFIX = "/oidc/ui"
TRASH_ROUTER_PREFIX = "/oidc/trash"
WEBHOOK_ROUTER_PREFIX = "/oidc/webhook"
