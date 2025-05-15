from functools import wraps
from typing import Callable, Dict, NamedTuple

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


def _permission_prompt_sources_config(model_name: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda model_name=model_name, user=username: store.get_registered_model_permission(model_name, user).permission,
        "group": lambda model_name=model_name, user=username: store.get_user_groups_registered_model_permission(
            model_name, user
        ).permission,
    }


def _permission_experiment_sources_config(experiment_id: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda experiment_id=experiment_id, user=username: store.get_experiment_permission(
            experiment_id, user
        ).permission,
        "group": lambda experiment_id=experiment_id, user=username: store.get_user_groups_experiment_permission(
            experiment_id, user
        ).permission,
    }


def _permission_registered_model_sources_config(model_name: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda model_name=model_name, user=username: store.get_registered_model_permission(model_name, user).permission,
        "group": lambda model_name=model_name, user=username: store.get_user_groups_registered_model_permission(
            model_name, user
        ).permission,
    }


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


# TODO: check fi str can be replaced by Permission in function signature
def get_permission_from_store_or_default(PERMISSION_SOURCES_CONFIG: Dict[str, Callable[[], str]]) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    for source_name in config.PERMISSION_SOURCE_ORDER:
        if source_name in PERMISSION_SOURCES_CONFIG:
            try:
                # Get the permission retrieval function from the configuration
                permission_func = PERMISSION_SOURCES_CONFIG[source_name]
                # Call the function to get the permission
                perm = permission_func()
                app.logger.debug(f"Permission found using source: {source_name}")
                return PermissionResult(get_permission(perm), source_name)
            except MlflowException as e:
                if e.error_code != ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
                    raise  # Re-raise exceptions other than RESOURCE_DOES_NOT_EXIST
                app.logger.debug(f"Permission not found using source {source_name}: {e}")
        else:
            app.logger.warning(f"Invalid permission source configured: {source_name}")

    # If no permission is found, use the default
    perm = config.DEFAULT_MLFLOW_PERMISSION
    app.logger.debug("Default permission used")
    return PermissionResult(get_permission(perm), "fallback")


def effective_experiment_permission(experiment_id: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return get_permission_from_store_or_default(_permission_experiment_sources_config(experiment_id, user))


def effective_registered_model_permission(model_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return get_permission_from_store_or_default(_permission_registered_model_sources_config(model_name, user))


def effective_prompt_permission(model_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return get_permission_from_store_or_default(_permission_prompt_sources_config(model_name, user))


def can_manage_experiment(experiment_id: str, user: str) -> bool:
    permission = effective_experiment_permission(experiment_id, user).permission
    return permission.can_manage


def can_manage_registered_model(model_name: str, user: str) -> bool:
    permission = effective_registered_model_permission(model_name, user).permission
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
