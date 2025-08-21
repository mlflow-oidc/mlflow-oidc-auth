from flask import request, session
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import BAD_REQUEST, INTERNAL_ERROR, INVALID_PARAMETER_VALUE
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.auth import validate_token
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.store import store

logger = get_logger()


def _experiment_id_from_name(experiment_name: str) -> str:
    """
    Helper function to get the experiment ID from the experiment name.
    Raises an exception if the experiment does not exist.
    """
    try:
        experiment = _get_tracking_store().get_experiment_by_name(experiment_name)
        if experiment is None:
            raise MlflowException(
                f"Experiment with name '{experiment_name}' not found.",
                INVALID_PARAMETER_VALUE,
            )
        return experiment.experiment_id
    except MlflowException as e:
        # Re-raise MLflow exceptions with their original error codes
        raise e
    except Exception as e:
        # Convert other exceptions to MLflow exceptions
        raise MlflowException(
            f"Error looking up experiment '{experiment_name}': {str(e)}",
            INVALID_PARAMETER_VALUE,
        )


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
        logger.debug(f"Optional URL parameter '{param}' not found in request path.")
        return None
    return view_args[param]


def get_request_param(param: str) -> str:
    """Extract a request parameter from query args, JSON data, or form data.

    Args:
        param: The name of the parameter to extract

    Returns:
        The parameter value

    Raises:
        MlflowException: If the parameter is not found or is empty
    """
    if request.method == "GET":
        args = request.args
    elif request.method in ("POST", "PATCH", "DELETE"):
        # Try JSON first, then fall back to form data
        if request.is_json:
            args = request.json
        else:
            args = request.form
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

    value = args[param]
    # Check for empty values
    if not value or (isinstance(value, str) and not value.strip()):
        raise MlflowException(
            f"Empty value for required parameter '{param}'. " "See the API docs for more information about request parameters.",
            INVALID_PARAMETER_VALUE,
        )

    return value


def get_optional_request_param(param: str) -> str | None:
    """Extract an optional request parameter from query args, JSON data, or form data.

    Args:
        param: The name of the parameter to extract

    Returns:
        The parameter value or None if not found
    """
    if request.method == "GET":
        args = request.args
    elif request.method in ("POST", "PATCH", "DELETE"):
        # Try JSON first, then fall back to form data
        if request.is_json:
            args = request.json
        else:
            args = request.form
    else:
        raise MlflowException(
            f"Unsupported HTTP method '{request.method}'",
            BAD_REQUEST,
        )

    if not args or param not in args:
        logger.debug(f"Optional parameter '{param}' not found in request data.")
        return None
    return args[param]


def get_username() -> str:
    """Extract username from session or authentication headers.

    Returns:
        str: The authenticated username

    Raises:
        MlflowException: If authentication is required but not provided
    """
    try:
        username = session.get("username")
        if username:
            logger.debug(f"Username from session: {username}")
            return username
        elif request.authorization is not None:
            if request.authorization.type == "basic":
                logger.debug(f"Username from basic auth: {request.authorization.username}")
                if request.authorization.username is not None:
                    username = store.get_user(request.authorization.username).username
                    return username
                raise MlflowException("Username not found in basic auth.", INVALID_PARAMETER_VALUE)
            if request.authorization.type == "bearer":
                token_data = validate_token(request.authorization.token)
                username = token_data.get("email")
                logger.debug(f"Username from bearer token: {username}")
                if username is not None:
                    return username
                raise MlflowException("Email claim is missing in bearer token.", INVALID_PARAMETER_VALUE)
            raise MlflowException(f"Unsupported authorization type: {request.authorization.type}", INVALID_PARAMETER_VALUE)
        logger.debug("No username found in session or authorization headers.")
        raise MlflowException("Authentication required. Please see documentation for details.", INVALID_PARAMETER_VALUE)
    except Exception as e:
        if isinstance(e, MlflowException):
            raise
        # Handle unexpected errors
        logger.error(f"Error getting username: {e}")
        raise MlflowException("Authentication required. Please see documentation for details.", INTERNAL_ERROR)


def get_is_admin() -> bool:
    return bool(store.get_user(get_username()).is_admin)


def get_experiment_id() -> str:
    """
    Helper function to get the experiment ID from the request.
    Checks view_args, query args, and JSON data in that order.
    Raises an exception if the experiment ID is not found.
    """
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
    # Last: check json (POST, PATCH, DELETE) - try request.json first (for mocking compatibility)
    try:
        if hasattr(request, "json") and request.json:
            if "experiment_id" in request.json:
                return request.json["experiment_id"]
            elif "experiment_name" in request.json:
                return _experiment_id_from_name(request.json["experiment_name"])
    except Exception:
        pass
    # Fallback to get_json method
    try:
        json_data = request.get_json(silent=True)
        if json_data:
            if "experiment_id" in json_data:
                return json_data["experiment_id"]
            elif "experiment_name" in json_data:
                return _experiment_id_from_name(json_data["experiment_name"])
    except Exception:
        # If JSON parsing fails, just continue to the error
        pass
    raise MlflowException(
        "Either 'experiment_id' or 'experiment_name' must be provided in the request data.",
        INVALID_PARAMETER_VALUE,
    )


# TODO: refactor to avoid code duplication
def get_model_id() -> str:
    """
    Helper function to get the model ID from the request.
    Raises an exception if the model ID is not found.
    """
    if request.view_args and "model_id" in request.view_args:
        return request.view_args["model_id"]
    if request.args and "model_id" in request.args:
        return request.args["model_id"]
    # Check for JSON content - try request.json first (for mocking compatibility)
    try:
        if hasattr(request, "json") and request.json and "model_id" in request.json:
            return request.json["model_id"]
    except Exception:
        pass
    # Fallback to get_json method
    try:
        json_data = request.get_json(silent=True)
        if json_data and "model_id" in json_data:
            return json_data["model_id"]
    except Exception:
        # If JSON parsing fails, just continue to the error
        pass
    raise MlflowException(
        "Model ID must be provided in the request data.",
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
    # Check for JSON content - try request.json first (for mocking compatibility)
    try:
        if hasattr(request, "json") and request.json and "name" in request.json:
            return request.json["name"]
    except Exception:
        pass
    # Fallback to get_json method
    try:
        json_data = request.get_json(silent=True)
        if json_data and "name" in json_data:
            return json_data["name"]
    except Exception:
        # If JSON parsing fails, just continue to the error
        pass
    raise MlflowException(
        "Model name must be provided in the request data.",
        INVALID_PARAMETER_VALUE,
    )
