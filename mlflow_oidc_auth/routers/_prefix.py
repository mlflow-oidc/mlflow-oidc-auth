"""
Router prefix constants for the FastAPI application.

This module defines all router prefixes used throughout the application
to ensure consistency and easy maintenance of URL structures.
"""

from typing import Optional

from mlflow.server.handlers import _get_ajax_path, _get_rest_path

# MLflow serves every REST handler under two prefixes: "/api/..." for API clients
# and "/ajax-api/..." for its own web UI. Derive both leading segments from
# MLflow instead of hardcoding them, so an upstream rename cannot silently
# desynchronise this plugin's routes from the paths the UI calls.
_REST_SEGMENT = _get_rest_path("/probe").split("/")[1]
_AJAX_SEGMENT = _get_ajax_path("/probe").split("/")[1]

# Leading path segments of the two prefixes, e.g. "/api" and "/ajax-api".
REST_PATH_PREFIX = f"/{_REST_SEGMENT}"
AJAX_PATH_PREFIX = f"/{_AJAX_SEGMENT}"

# Both prefixes carry programmatic (XHR / API-client) traffic, so a failed
# request under either must surface as an HTTP error rather than a redirect.
API_PATH_PREFIXES = (REST_PATH_PREFIX, AJAX_PATH_PREFIX)


def to_ajax_path(path: str) -> Optional[str]:
    """Return the "/ajax-api" twin of an "/api" path.

    Args:
        path: A route path, e.g. "/api/2.0/mlflow/users/current".

    Returns:
        The equivalent "/ajax-api" path, or None when `path` is not under the
        REST prefix at all (health checks and the "/oidc/*" routes), since those
        have no UI-facing twin.
    """
    rest_prefix = f"{REST_PATH_PREFIX}/"
    if not path.startswith(rest_prefix):
        return None
    return f"{AJAX_PATH_PREFIX}/{path[len(rest_prefix):]}"


EXPERIMENT_PERMISSIONS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/experiments")
GROUP_PERMISSIONS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/groups")
PROMPT_PERMISSIONS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/prompts")
REGISTERED_MODEL_PERMISSIONS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/registered-models")
GATEWAY_PERMISSIONS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/gateways")
USER_PERMISSIONS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/users")
SCORERS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/scorers", version=3)
USERS_ROUTER_PREFIX = _get_rest_path("/mlflow/users")
HEALTH_CHECK_ROUTER_PREFIX = "/health"
UI_ROUTER_PREFIX = "/oidc/ui"
TRASH_ROUTER_PREFIX = "/oidc/trash"
WEBHOOK_ROUTER_PREFIX = "/oidc/webhook"
WORKSPACE_PERMISSIONS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/workspaces", version=3)
WORKSPACE_REGEX_PERMISSIONS_ROUTER_PREFIX = _get_rest_path("/mlflow/permissions/workspaces/regex", version=3)
