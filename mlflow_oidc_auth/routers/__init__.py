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


# Every ``add_api_route`` keyword that describes the route itself rather than
# where it is mounted. A twin must carry all of them, or it silently behaves
# differently from its "/api" original - ``response_model_exclude_none``, for
# one, changes the JSON the UI receives. The remaining keywords are supplied
# explicitly by ``ajax_alias_router`` (see ``_MOUNT_ROUTE_FIELDS`` in the tests,
# which asserts the two sets together still cover the whole signature).
_COPIED_ROUTE_FIELDS = (
    "response_model",
    "status_code",
    "tags",
    "dependencies",
    "summary",
    "description",
    "response_description",
    "responses",
    "deprecated",
    "operation_id",
    "response_model_include",
    "response_model_exclude",
    "response_model_by_alias",
    "response_model_exclude_unset",
    "response_model_exclude_defaults",
    "response_model_exclude_none",
    "response_class",
    "callbacks",
    "openapi_extra",
    "generate_unique_id_function",
    "strict_content_type",
)

# Suffix appended to a twin's route name so ``url_path_for()`` stays unambiguous.
AJAX_ROUTE_NAME_SUFFIX = "_ajax"


def _copied_route_kwargs(route: APIRoute) -> dict:
    """Collect the route-describing keywords to carry over to a twin.

    Fields absent from the installed FastAPI version are skipped, so this keeps
    working across versions that add or drop route options.
    """
    kwargs = {}
    for field in _COPIED_ROUTE_FIELDS:
        if not hasattr(route, field):
            continue
        value = getattr(route, field)
        # Copy the mutable containers so the twin can never mutate the original.
        if isinstance(value, list):
            value = list(value)
        elif isinstance(value, dict):
            value = dict(value)
        kwargs[field] = value
    return kwargs


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
            # Preserve a custom route class (request/response handling lives
            # there) instead of falling back to the plain APIRoute.
            route_class_override=type(route),
            # The canonical "/api" paths are the documented ones; keeping the
            # twins out of the schema avoids listing every endpoint twice. The
            # distinct name keeps url_path_for() unambiguous.
            name=f"{route.name}{AJAX_ROUTE_NAME_SUFFIX}",
            include_in_schema=False,
            **_copied_route_kwargs(route),
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
