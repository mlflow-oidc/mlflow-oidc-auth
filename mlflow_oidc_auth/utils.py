from typing import Callable, NamedTuple

from flask import request, session
from mlflow.exceptions import ErrorCode, MlflowException
from mlflow.protos.databricks_pb2 import BAD_REQUEST, INVALID_PARAMETER_VALUE, RESOURCE_DOES_NOT_EXIST
from mlflow.server import app
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.app import app
from mlflow_oidc_auth.auth import validate_token
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.permissions import Permission, get_permission
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


def get_username() -> str | None:
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


def get_user_groups() -> list[str] | None:
    user_groups = session.get("group")
    if user_groups:
        app.logger.debug(f"Groups from session: {user_groups}")
        return user_groups
    else:
        app.logger.debug("Groups not found in session.")
        app.logger.debug("Trying to get groups now from the token.")
        app.logger.debug(f"Token: {request.authorization}")
    if request.authorization and request.authorization.type == "bearer":
        token = validate_token(request.authorization.token)
        if config.OIDC_GROUP_DETECTION_PLUGIN:
            import importlib

            user_groups = importlib.import_module(config.OIDC_GROUP_DETECTION_PLUGIN).get_user_groups(token["access_token"])
        else:
            user_groups = token["access_token"].get(config.OIDC_GROUPS_ATTRIBUTE)
        app.logger.debug(f"Groups from bearer token: {user_groups}")
        return user_groups
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
    """
    Attempts to get permission from store,
    and returns default permission if no record is found.
    user permission takes precedence over group permission
    """
    try:
        perm = store_permission_user_func()
        app.logger.debug("User permission found")
        perm_type = "user"
    except MlflowException as e:
        if e.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
            try:
                perm = store_permission_group_func()
                app.logger.debug("Group permission found")
                perm_type = "group"
            except MlflowException as e:
                if e.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
                    perm = config.DEFAULT_MLFLOW_PERMISSION
                    app.logger.debug("Default permission used")
                    perm_type = "fallback"
    return PermissionResult(get_permission(perm), perm_type)
