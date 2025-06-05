import re
from functools import wraps
from typing import Callable, Dict, List, NamedTuple, Optional
from flask import request, session
from sqlalchemy.exc import NoResultFound
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import BAD_REQUEST, INVALID_PARAMETER_VALUE, RESOURCE_DOES_NOT_EXIST, ErrorCode
from mlflow.server import app
from mlflow.server.handlers import _get_tracking_store, _get_model_registry_store
from mlflow.entities.model_registry import RegisteredModel
from mlflow.entities import Experiment
from mlflow.store.entities.paged_list import PagedList

from mlflow_oidc_auth.auth import validate_token
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.entities import (
    ExperimentGroupRegexPermission,
    ExperimentRegexPermission,
    RegisteredModelGroupRegexPermission,
    RegisteredModelRegexPermission,
)
from mlflow_oidc_auth.permissions import Permission, get_permission
from mlflow_oidc_auth.responses.client_error import make_forbidden_response
from mlflow_oidc_auth.store import store


def fetch_all_registered_models(
    filter_string: Optional[str] = None, order_by: Optional[List[str]] = None, max_results_per_page: int = 1000
) -> List[RegisteredModel]:
    """
    Fetch ALL registered models from the MLflow model registry using pagination.
    This ensures we get all models, not just the first page.

    Args:
        filter_string: Filter string for the search
        order_by: List of order by clauses
        max_results_per_page: Maximum number of results to fetch per page (default: 1000)

    Returns:
        List of ALL RegisteredModel objects
    """
    all_models = []
    page_token = None

    while True:
        result = _get_model_registry_store().search_registered_models(
            filter_string=filter_string, max_results=max_results_per_page, order_by=order_by, page_token=page_token
        )

        all_models.extend(result)

        # Check if there are more pages
        if hasattr(result, "token") and result.token:
            page_token = result.token
        else:
            break

    return all_models


def fetch_all_prompts(max_results_per_page: int = 1000) -> List[RegisteredModel]:
    """
    Fetch ALL registered models that are marked as prompts using pagination.
    This ensures we get all prompts, not just the first page.

    Args:
        max_results_per_page: Maximum number of results to fetch per page (default: 1000)

    Returns:
        List of ALL RegisteredModel objects that are prompts
    """
    filter_string = "tags.`mlflow.prompt.is_prompt` = 'true'"
    return fetch_all_registered_models(filter_string=filter_string, max_results_per_page=max_results_per_page)


def fetch_registered_models_paginated(
    filter_string: Optional[str] = None, max_results: int = 1000, order_by: Optional[List[str]] = None, page_token=None
) -> PagedList[RegisteredModel]:
    """
    Fetch registered models with pagination support.

    Args:
        filter_string: Filter string for the search
        max_results: Maximum number of results to return
        order_by: List of order by clauses
        page_token: Token for pagination

    Returns:
        PagedList of RegisteredModel objects
    """
    return _get_model_registry_store().search_registered_models(
        filter_string=filter_string,
        max_results=max_results,
        order_by=order_by,
        page_token=page_token,
    )


def _get_registered_model_permission_from_regex(regexes: List[RegisteredModelRegexPermission], model_name: str) -> str:
    for regex in regexes:
        if re.match(regex.regex, model_name):
            app.logger.debug(f"Regex permission found for model name {model_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}")
            return regex.permission
    raise MlflowException(
        f"model name {model_name}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def _get_experiment_permission_from_regex(regexes: List[ExperimentRegexPermission], experiment_id: str) -> str:
    experiment_name = _get_tracking_store().get_experiment(experiment_id).name
    for regex in regexes:
        if re.match(regex.regex, experiment_name):
            app.logger.debug(
                f"Regex permission found for experiment id {experiment_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}"
            )
            return regex.permission
    raise MlflowException(
        f"experiment id {experiment_id}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def _get_registered_model_group_permission_from_regex(regexes: List[RegisteredModelGroupRegexPermission], model_name: str) -> str:
    for regex in regexes:
        if re.match(regex.regex, model_name):
            app.logger.debug(
                f"Regex group permission found for model name {model_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}"
            )
            return regex.permission
    raise MlflowException(
        f"model name {model_name}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def _get_experiment_group_permission_from_regex(regexes: List[ExperimentGroupRegexPermission], experiment_id: str) -> str:
    experiment_name = _get_tracking_store().get_experiment(experiment_id).name
    for regex in regexes:
        if re.match(regex.regex, experiment_name):
            app.logger.debug(
                f"Regex group permission found for experiment id {experiment_name}: {regex.permission} with regex {regex.regex} and priority {regex.priority}"
            )
            return regex.permission
    raise MlflowException(
        f"experiment id {experiment_id}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def _permission_prompt_sources_config(model_name: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda model_name=model_name, user=username: store.get_registered_model_permission(model_name, user).permission,
        "group": lambda model_name=model_name, user=username: store.get_user_groups_registered_model_permission(model_name, user).permission,
        "regex": lambda model_name=model_name, user=username: _get_registered_model_permission_from_regex(
            store.list_prompt_regex_permissions(user), model_name
        ),
        "group-regex": lambda model_name=model_name, user=username: _get_registered_model_group_permission_from_regex(
            store.list_group_prompt_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)), model_name
        ),
    }


def _permission_experiment_sources_config(experiment_id: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda experiment_id=experiment_id, user=username: store.get_experiment_permission(experiment_id, user).permission,
        "group": lambda experiment_id=experiment_id, user=username: store.get_user_groups_experiment_permission(experiment_id, user).permission,
        "regex": lambda experiment_id=experiment_id, user=username: _get_experiment_permission_from_regex(
            store.list_experiment_regex_permissions(user), experiment_id
        ),
        "group-regex": lambda experiment_id=experiment_id, user=username: _get_experiment_group_permission_from_regex(
            store.list_group_experiment_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)), experiment_id
        ),
    }


def _permission_registered_model_sources_config(model_name: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda model_name=model_name, user=username: store.get_registered_model_permission(model_name, user).permission,
        "group": lambda model_name=model_name, user=username: store.get_user_groups_registered_model_permission(model_name, user).permission,
        "regex": lambda model_name=model_name, user=username: _get_registered_model_permission_from_regex(
            store.list_registered_model_regex_permissions(user), model_name
        ),
        "group-regex": lambda model_name=model_name, user=username: _get_registered_model_group_permission_from_regex(
            store.list_group_registered_model_regex_permissions_for_groups_ids(store.get_groups_ids_for_user(user)), model_name
        ),
    }


def get_url_param(param: str) -> str:
    """Extract a URL path parameter from Flask's request.view_args.

    Args:
        param: The name of the URL parameter to extract

    Returns:
        The parameter value

    Raises:
        MlflowException: If the parameter is not found in the URL path
    """
    view_args = request.view_args
    if not view_args or param not in view_args:
        raise MlflowException(
            f"Missing value for required URL parameter '{param}'. " "The parameter should be part of the URL path.",
            INVALID_PARAMETER_VALUE,
        )
    return view_args[param]


def get_optional_url_param(param: str) -> str | None:
    """Extract an optional URL path parameter from Flask's request.view_args.

    Args:
        param: The name of the URL parameter to extract

    Returns:
        The parameter value or None if not found
    """
    view_args = request.view_args
    if not view_args or param not in view_args:
        app.logger.debug(f"Optional URL parameter '{param}' not found in request path.")
        return None
    return view_args[param]


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
            f"Missing value for required parameter '{param}'. " "See the API docs for more information about request parameters.",
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


def get_user_groups(username: Optional[str] = None) -> list[str]:
    """
    Retrieve the groups associated with a user.

    This function is designed to obtain the list of groups a user belongs to,
    which can be used for permission and access control within the application.
    It tries different approaches in order: session data, bearer token
    authentication, and store query to determine the user's group memberships.

    Parameters
    ----------
    username : str, optional
        The username of the user whose groups are being queried.

    Returns
    -------
    list of str
        A list of strings representing the user's groups. Returns an empty list
        if no groups are found.
    """
    user_groups = session.get(config.OIDC_GROUPS_ATTRIBUTE)
    if user_groups:
        app.logger.debug(f"Groups from session: {user_groups}")
        return user_groups

    if request.authorization and request.authorization.type == "bearer":
        if config.OIDC_GROUP_DETECTION_PLUGIN:
            import importlib
            groups_plugin = importlib.import_module(
                config.OIDC_GROUP_DETECTION_PLUGIN
                )
            user_groups = groups_plugin.get_user_groups(
                request.authorization.token
                )
            app.logger.debug(f"Groups from plugin: {user_groups}")
        else:
            user_groups = validate_token(request.authorization.token).get(
                config.OIDC_GROUPS_ATTRIBUTE
                )
            app.logger.debug(f"Groups from bearer token: {user_groups}")
        return filter_groups(user_groups)

    if username:
        try:
            user_groups = store.get_groups_for_user(username)
            app.logger.debug(f"Groups from store: {user_groups}")
            return user_groups
        except NoResultFound:
            pass
    return []


def filter_groups(user_groups: list[str]) -> list[str]:
    """
    Filters the user groups to only include those that are allowed by the
    application cofiguration.

    Parameters
    ----------
    user_groups : list of str
        A list of user group names to be filtered.

    Returns
    -------
    list of str
        A list containing only the user groups that are available.
    """
    available_groups = config.OIDC_GROUP_NAME + [config.OIDC_ADMIN_GROUP_NAME]
    filtered_user_groups = list(filter(lambda x: x in available_groups,
                                       user_groups))
    return filtered_user_groups


def get_is_admin() -> bool:
    return bool(store.get_user(get_username()).is_admin)


def _experiment_id_from_name(experiment_name: str) -> str:
    """
    Helper function to get the experiment ID from the experiment name.
    Raises an exception if the experiment does not exist.
    """
    experiment = _get_tracking_store().get_experiment_by_name(experiment_name)
    if experiment is None:
        raise MlflowException(
            f"Experiment with name '{experiment_name}' not found.",
            INVALID_PARAMETER_VALUE,
        )
    return experiment.experiment_id


def get_experiment_id() -> str:
    # Fastest: check view_args first
    if request.view_args:
        if "experiment_id" in request.view_args:
            return request.view_args["experiment_id"]
        elif "experiment_name" in request.view_args:
            return _experiment_id_from_name(request.view_args["experiment_name"])
    # Next: check args (GET)
    if request.args:
        if "experiment_id" in request.args:
            return request.args["experiment_id"]
        elif "experiment_name" in request.args:
            return _experiment_id_from_name(request.args["experiment_name"])
    # Last: check json (POST, PATCH, DELETE)
    if request.json:
        if "experiment_id" in request.json:
            return request.json["experiment_id"]
        elif "experiment_name" in request.json:
            return _experiment_id_from_name(request.json["experiment_name"])
    raise MlflowException(
        "Either 'experiment_id' or 'experiment_name' must be provided in the request data.",
        INVALID_PARAMETER_VALUE,
    )


def get_model_name() -> str:
    """
    Helper function to get the model name from the request.
    Raises an exception if the model name is not found.
    """
    if request.view_args and "name" in request.view_args:
        return request.view_args["name"]
    if request.args and "name" in request.args:
        return request.args["name"]
    if request.json and "name" in request.json:
        return request.json["name"]
    raise MlflowException(
        "Model name must be provided in the request data.",
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


def effective_prompt_permission(prompt_name: str, user: str) -> PermissionResult:
    """
    Attempts to get permission from store based on configured sources,
    and returns default permission if no record is found.
    Permissions are checked in the order defined in PERMISSION_SOURCE_ORDER.
    """
    return get_permission_from_store_or_default(_permission_prompt_sources_config(prompt_name, user))


def can_read_experiment(experiment_id: str, user: str) -> bool:
    permission = effective_experiment_permission(experiment_id, user).permission
    return permission.can_read


def can_read_registered_model(model_name: str, user: str) -> bool:
    permission = effective_registered_model_permission(model_name, user).permission
    return permission.can_read


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
            model_name = get_model_name()
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
            prompt_name = get_model_name()
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


def fetch_all_experiments(
    view_type: int = 1, max_results_per_page: int = 1000, order_by: Optional[List[str]] = None, filter_string: Optional[str] = None  # ACTIVE_ONLY
) -> List[Experiment]:
    """
    Fetch ALL experiments from the MLflow tracking store using pagination.
    This ensures we get all experiments, not just the first page.

    Args:
        view_type: ViewType for experiments (1=ACTIVE_ONLY, 2=DELETED_ONLY, 3=ALL)
        max_results_per_page: Maximum number of results to fetch per page (default: 1000)
        order_by: List of order by clauses
        filter_string: Filter string for the search

    Returns:
        List of ALL Experiment objects
    """
    all_experiments = []
    page_token = None

    while True:
        result = _get_tracking_store().search_experiments(
            view_type=view_type,
            max_results=max_results_per_page,
            order_by=order_by,
            filter_string=filter_string,
            page_token=page_token,
        )

        all_experiments.extend(result)

        # Check if there are more pages
        if hasattr(result, "token") and result.token:
            page_token = result.token
        else:
            break

    return all_experiments


def fetch_experiments_paginated(
    view_type: int = 1,
    max_results: int = 1000,
    order_by: Optional[List[str]] = None,
    filter_string: Optional[str] = None,
    page_token=None,  # ACTIVE_ONLY
) -> PagedList[Experiment]:
    """
    Fetch experiments with pagination support.

    Args:
        view_type: ViewType for experiments (1=ACTIVE_ONLY, 2=DELETED_ONLY, 3=ALL)
        max_results: Maximum number of results to return
        order_by: List of order by clauses
        filter_string: Filter string for the search
        page_token: Token for pagination

    Returns:
        PagedList of Experiment objects
    """
    return _get_tracking_store().search_experiments(
        view_type=view_type,
        max_results=max_results,
        order_by=order_by,
        filter_string=filter_string,
        page_token=page_token,
    )


def fetch_readable_experiments(
    view_type: int = 1,
    max_results_per_page: int = 1000,
    order_by: Optional[List[str]] = None,
    filter_string: Optional[str] = None,
    username: Optional[str] = None,  # ACTIVE_ONLY
) -> List[Experiment]:
    """
    Fetch ALL experiments that the user can read from the MLflow tracking store using pagination.
    This ensures we get all readable experiments, not just the first page.

    Args:
        view_type: ViewType for experiments (1=ACTIVE_ONLY, 2=DELETED_ONLY, 3=ALL)
        max_results_per_page: Maximum number of results to fetch per page (default: 1000)
        order_by: List of order by clauses
        filter_string: Filter string for the search
        username: Username to check permissions for (defaults to current user)

    Returns:
        List of Experiment objects that the user can read
    """
    if username is None:
        username = get_username()

    # Get all experiments matching the filter
    all_experiments = fetch_all_experiments(view_type=view_type, max_results_per_page=max_results_per_page, order_by=order_by, filter_string=filter_string)

    # Filter by permissions
    readable_experiments = [experiment for experiment in all_experiments if can_read_experiment(experiment.experiment_id, username)]

    return readable_experiments


def fetch_readable_registered_models(
    filter_string: Optional[str] = None, order_by: Optional[List[str]] = None, max_results_per_page: int = 1000, username: Optional[str] = None
) -> List[RegisteredModel]:
    """
    Fetch ALL registered models that the user can read from the MLflow model registry using pagination.
    This ensures we get all readable models, not just the first page.

    Args:
        filter_string: Filter string for the search
        order_by: List of order by clauses
        max_results_per_page: Maximum number of results to fetch per page (default: 1000)
        username: Username to check permissions for (defaults to current user)

    Returns:
        List of RegisteredModel objects that the user can read
    """
    if username is None:
        username = get_username()

    # Get all models matching the filter
    all_models = fetch_all_registered_models(filter_string=filter_string, order_by=order_by, max_results_per_page=max_results_per_page)

    # Filter by permissions
    readable_models = [model for model in all_models if can_read_registered_model(model.name, username)]

    return readable_models
