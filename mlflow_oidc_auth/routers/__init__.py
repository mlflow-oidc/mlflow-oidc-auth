"""
Router package for the FastAPI application.

This module exports all routers that are used in the FastAPI application.
Each router is responsible for a specific set of endpoints.
"""

from typing import List

from fastapi import APIRouter
from fastapi.routing import APIRoute

from mlflow_oidc_auth.routers._prefix import to_ajax_path
from mlflow_oidc_auth.routers.auth import auth_router
from mlflow_oidc_auth.routers.experiment_permissions import (
    experiment_permissions_router,
)
from mlflow_oidc_auth.routers.group_permissions import group_permissions_router
from mlflow_oidc_auth.routers.prompt_permissions import prompt_permissions_router
from mlflow_oidc_auth.routers.registered_model_permissions import (
    registered_model_permissions_router,
)
from mlflow_oidc_auth.routers.scorers_permissions import scorers_permissions_router
from mlflow_oidc_auth.routers.gateway_endpoint_permissions import (
    gateway_endpoint_permissions_router,
)
from mlflow_oidc_auth.routers.gateway_secret_permissions import (
    gateway_secret_permissions_router,
)
from mlflow_oidc_auth.routers.gateway_model_definition_permissions import (
    gateway_model_definition_permissions_router,
)
from mlflow_oidc_auth.routers.health import health_check_router
from mlflow_oidc_auth.routers.trash import trash_router
from mlflow_oidc_auth.routers.ui import ui_router
from mlflow_oidc_auth.routers.user_permissions import user_permissions_router
from mlflow_oidc_auth.routers.users import users_router
from mlflow_oidc_auth.routers.webhook import webhook_router
from mlflow_oidc_auth.routers.workspace_permissions import workspace_permissions_router
from mlflow_oidc_auth.routers.workspace_regex_permissions import (
    workspace_regex_permissions_router,
)

__all__ = [
    "ajax_alias_router",
    "auth_router",
    "experiment_permissions_router",
    "group_permissions_router",
    "prompt_permissions_router",
    "registered_model_permissions_router",
    "scorers_permissions_router",
    "gateway_endpoint_permissions_router",
    "gateway_secret_permissions_router",
    "gateway_model_definition_permissions_router",
    "health_check_router",
    "trash_router",
    "ui_router",
    "user_permissions_router",
    "users_router",
    "webhook_router",
    "workspace_permissions_router",
    "workspace_regex_permissions_router",
]


def ajax_alias_router(router: APIRouter) -> APIRouter:
    """Mirror a router's "/api" routes onto MLflow's "/ajax-api" prefix.

    MLflow registers every one of its own REST handlers under both "/api/..."
    and "/ajax-api/...", and its web UI calls the "/ajax-api" variants. This
    plugin's routers were registered under "/api" only, so UI calls such as
    ``GET /ajax-api/2.0/mlflow/users/current`` matched no FastAPI route, fell
    through to the mounted Flask app and returned 404. The UI reads that failure
    as "not authenticated" (its current-user query runs with ``retry: false``,
    after which ``is_admin`` is false and ``username`` empty), so it hides the
    edit affordances even for admins.

    Routes outside the REST prefix - health checks and the "/oidc/*" routes -
    have no UI-facing twin and are left alone.

    Args:
        router: The router whose API routes should be mirrored.

    Returns:
        APIRouter: A router holding the "/ajax-api" twins. Empty when `router`
        exposes no routes under the REST prefix.
    """
    alias = APIRouter()
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        ajax_path = to_ajax_path(route.path)
        if ajax_path is None:
            continue
        alias.add_api_route(
            ajax_path,
            route.endpoint,
            methods=sorted(route.methods),
            response_model=route.response_model,
            status_code=route.status_code,
            dependencies=list(route.dependencies),
            summary=route.summary,
            description=route.description,
            tags=list(route.tags),
            response_class=route.response_class,
            # The canonical "/api" paths are the documented ones; keeping the
            # twins out of the schema avoids listing every endpoint twice. The
            # distinct name keeps url_path_for() unambiguous.
            name=f"{route.name}_ajax",
            include_in_schema=False,
        )
    return alias


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
        scorers_permissions_router,
        gateway_endpoint_permissions_router,
        gateway_secret_permissions_router,
        gateway_model_definition_permissions_router,
        health_check_router,
        trash_router,
        ui_router,
        user_permissions_router,
        users_router,
        webhook_router,
    ]
