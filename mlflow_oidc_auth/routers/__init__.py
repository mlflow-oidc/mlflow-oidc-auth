"""
Router package for the FastAPI application.

This module exports all routers that are used in the FastAPI application.
Each router is responsible for a specific set of endpoints.
"""

from typing import List

from fastapi import APIRouter

from mlflow_oidc_auth.routers.auth import auth_router
from mlflow_oidc_auth.routers.experiment_permissions import experiment_permissions_router
from mlflow_oidc_auth.routers.group_permissions import group_permissions_router
from mlflow_oidc_auth.routers.prompt_permissions import prompt_permissions_router
from mlflow_oidc_auth.routers.registered_model_permissions import registered_model_permissions_router
from mlflow_oidc_auth.routers.health import health_check_router
from mlflow_oidc_auth.routers.trash import trash_router
from mlflow_oidc_auth.routers.ui import ui_router
from mlflow_oidc_auth.routers.user_permissions import user_permissions_router
from mlflow_oidc_auth.routers.users import users_router
from mlflow_oidc_auth.routers.webhook import webhook_router

__all__ = [
    "auth_router",
    "experiment_permissions_router",
    "group_permissions_router",
    "prompt_permissions_router",
    "registered_model_permissions_router",
    "health_check_router",
    "trash_router",
    "ui_router",
    "user_permissions_router",
    "users_router",
    "webhook_router",
]


def get_all_routers() -> List[APIRouter]:
    """
    Get all routers for registration in the FastAPI application.

    Returns:
        List[APIRouter]: List of all router instances to be included in the FastAPI app.
    """
    return [
        auth_router,
        experiment_permissions_router,
        group_permissions_router,
        prompt_permissions_router,
        registered_model_permissions_router,
        health_check_router,
        trash_router,
        ui_router,
        user_permissions_router,
        users_router,
        webhook_router,
    ]
