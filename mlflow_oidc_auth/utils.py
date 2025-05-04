from functools import wraps
from typing import Callable, NamedTuple

from flask import request, session
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import BAD_REQUEST, INVALID_PARAMETER_VALUE, RESOURCE_DOES_NOT_EXIST, ErrorCode
from mlflow.server import app
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.auth import validate_token
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.permissions import Permission, get_permission
from mlflow_oidc_auth.responses.client_error import make_forbidden_response
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

    if not args or param not in args:
        # Special handling for run_id
        if param == "run_id":
            return get_request_param("run_uuid")
        raise MlflowException(
            f"Missing value for required parameter '{param}'. "
            "See the API docs for more information about request parameters.",
            INVALID_PARAMETER_VALUE,
        )
    return args[param]


def get_optional_request_param(param: str) -> str | None:
    if request.method == "GET":
        args = request.args
    elif request.method in ("POST", "PATCH", "DELETE"):
        args = request.json
    else:
        raise MlflowException(
            f"Unsupported HTTP method '{request.method}'",
            BAD_REQUEST,
        )

    if not args or param not in args:
        app.logger.debug(f"Optional parameter '{param}' not found in request data.")
        return None
    return args[param]


def get_username() -> str:
    username = session.get("username")
    if username:
        app.logger.debug(f"Username from session: {username}")
        return username
    elif request.authorization is not None:
        if request.authorization.type == "basic":
            app.logger.debug(f"Username from basic auth: {request.authorization.username}")
            if request.authorization.username is not None:
                return request.authorization.username
            raise MlflowException("Username not found in basic auth.")
        if request.authorization.type == "bearer":
            username = validate_token(request.authorization.token).get("email")
            app.logger.debug(f"Username from bearer token: {username}")
            return username
    raise MlflowException("Authentication required. Please see documentation for details: ")


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
    if args and "experiment_id" in args:
        return args["experiment_id"]
    elif args and "experiment_name" in args:
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


def can_manage_experiment(experiment_id: str, user: str) -> bool:
    permission = get_permission_from_store_or_default(
        lambda: store.get_experiment_permission(experiment_id, user).permission,
        lambda: store.get_user_groups_experiment_permission(experiment_id, user).permission,
    ).permission
    return permission.can_manage


def can_manage_registered_model(model_name: str, user: str) -> bool:
    permission = get_permission_from_store_or_default(
        lambda: store.get_registered_model_permission(model_name, user).permission,
        lambda: store.get_user_groups_registered_model_permission(model_name, user).permission,
    ).permission
    return permission.can_manage


def check_experiment_permission(f) -> Callable:
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = store.get_user(get_username())
        if not get_is_admin():
            app.logger.debug(f"Not Admin. Checking permission for {current_user.username}")
            experiment_id = get_experiment_id()
            if not can_manage_experiment(experiment_id, current_user.username):
                app.logger.warning(f"Change permission denied for {current_user.username} on experiment {experiment_id}")
                return make_forbidden_response()
        app.logger.debug(f"Change permission granted for {current_user.username}")
        return f(*args, **kwargs)

    return decorated_function


def check_registered_model_permission(f) -> Callable:
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = store.get_user(get_username())
        if not get_is_admin():
            app.logger.debug(f"Not Admin. Checking permission for {current_user.username}")
            model_name = get_request_param("name")
            if not can_manage_registered_model(model_name, current_user.username):
                app.logger.warning(f"Change permission denied for {current_user.username} on model {model_name}")
                return make_forbidden_response()
        app.logger.debug(f"Permission granted for {current_user.username}")
        return f(*args, **kwargs)

    return decorated_function


def check_prompt_permission(f) -> Callable:
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = store.get_user(get_username())
        if not get_is_admin():
            app.logger.debug(f"Not Admin. Checking permission for {current_user.username}")
            prompt_name = get_request_param("name")
            if not can_manage_registered_model(prompt_name, current_user.username):
                app.logger.warning(f"Change permission denied for {current_user.username} on prompt {prompt_name}")
                return make_forbidden_response()
        app.logger.debug(f"Permission granted for {current_user.username}")
        return f(*args, **kwargs)

    return decorated_function


def check_admin_permission(f) -> Callable:
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = store.get_user(get_username())
        if not get_is_admin():
            app.logger.warning(f"Admin permission denied for {current_user.username}")
            return make_forbidden_response()
        app.logger.debug(f"Admin permission granted for {current_user.username}")
        return f(*args, **kwargs)

    return decorated_function
