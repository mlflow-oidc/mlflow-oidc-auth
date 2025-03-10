from typing import Callable, NamedTuple

from flask import request, session
from mlflow.exceptions import ErrorCode, MlflowException
from mlflow.protos.databricks_pb2 import BAD_REQUEST, INVALID_PARAMETER_VALUE, RESOURCE_DOES_NOT_EXIST
from mlflow.server import app
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.app import app
from mlflow_oidc_auth.auth import validate_token
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.permissions import Permission, compare_permissions, get_permission
from mlflow_oidc_auth.store import store


def get_request_param(param: str) -> str:
    if request.method == "GET":
        args = request.args
    elif request.method in ("POST", "PATCH", "DELETE"):
        args = request.json
    else:
        raise MlflowException(
            f"Unsupported HTTP method '{request.method}'",
            BAD_REQUEST,
        )

    if param not in args:
        # Special handling for run_id
        if param == "run_id":
            return get_request_param("run_uuid")
        raise MlflowException(
            f"Missing value for required parameter '{param}'. "
            "See the API docs for more information about request parameters.",
            INVALID_PARAMETER_VALUE,
        )
    return args[param]


def get_username():
    username = session.get("username")
    if username:
        app.logger.debug(f"Username from session: {username}")
        return username
    elif request.authorization is not None:
        if request.authorization.type == "basic":
            app.logger.debug(f"Username from basic auth: {request.authorization.username}")
            return request.authorization.username
        if request.authorization.type == "bearer":
            username = validate_token(request.authorization.token).get("email")
            app.logger.debug(f"Username from bearer token: {username}")
            return username
    return None


def get_is_admin() -> bool:
    return bool(store.get_user(get_username()).is_admin)


def get_experiment_id() -> str:
    if request.method == "GET":
        args = request.args
    elif request.method in ("POST", "PATCH", "DELETE"):
        args = request.json
    else:
        raise MlflowException(
            f"Unsupported HTTP method '{request.method}'",
            BAD_REQUEST,
        )
    if "experiment_id" in args:
        return args["experiment_id"]
    elif "experiment_name" in args:
        return _get_tracking_store().get_experiment_by_name(args["experiment_name"]).experiment_id
    raise MlflowException(
        "Either 'experiment_id' or 'experiment_name' must be provided in the request data.",
        INVALID_PARAMETER_VALUE,
    )


class PermissionResult(NamedTuple):
    permission: Permission
    type: str


def get_permission_from_store_or_default(
    store_permission_user_func: Callable[[], str], store_permission_group_func: Callable[[], str]
) -> PermissionResult:
    """Calculate the permissions based on the two functions with arguments provided and the default permission.

    The function will return the highest permission as well as the type (user/group/fallback) that lead to this
    permission. This is done by starting out with the default permission and checking if the user permission
    is strictly better. After that, we check for each of the group-permissions if they are strictly better

    Args:
        store_permission_user_func: function that will give us the permissions based on the current user
        store_permission_group_func: function that will give us the permissions based on the groups of user

    Returns:
        PermissionResult holding both the permission as well as the type of the highest permission (i.e.
        whether it was fallback/user/group)
    """

    # Start out with the default mlflow permission and type fallback
    perm = config.DEFAULT_MLFLOW_PERMISSION
    perm_type = "fallback"

    try:
        perm_user = store_permission_user_func()

        # Do a strict comparison, only if user permission is higher do we consider it
        if compare_permissions(perm, perm_user, True):
            app.logger.debug("User permission found with better priority")
            perm = perm_user
            perm_type = "user"
        else:
            app.logger.debug("User permission found, but with lower or equal priority")
    except MlflowException as e:
        if e.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
            app.logger.debug("No user permission found")

    try:
        perm_group = store_permission_group_func()

        # Do a strict comparison, only if the group permission is higher do we consider it
        if compare_permissions(perm, perm_group, True):
            app.logger.debug("Group permission found with better priority")
            perm = perm_group
            perm_type = "group"
        else:
            app.logger.debug("Group permission found, but with lower or equal priority")

    except MlflowException as e:
        if e.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
            app.logger.debug("No group permission found")

    return PermissionResult(get_permission(perm), perm_type)
