"""
Router prefix constants for the FastAPI application.

This module defines all router prefixes used throughout the application
to ensure consistency and easy maintenance of URL structures.
"""

EXPERIMENT_PERMISSIONS_ROUTER_PREFIX = "/api/2.0/mlflow/permissions/experiments"
GROUP_PERMISSIONS_ROUTER_PREFIX = "/api/2.0/mlflow/permissions/groups"
HEALTH_CHECK_ROUTER_PREFIX = "/health"
PROMPT_PERMISSIONS_ROUTER_PREFIX = "/api/2.0/mlflow/permissions/prompts"
REGISTERED_MODEL_PERMISSIONS_ROUTER_PREFIX = "/api/2.0/mlflow/permissions/registered-models"
UI_ROUTER_PREFIX = "/oidc/ui"
USER_PERMISSIONS_ROUTER_PREFIX = "/api/2.0/mlflow/permissions/users"
USERS_ROUTER_PREFIX = "/api/2.0/mlflow/users"
