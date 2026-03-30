from flask import request
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import BAD_REQUEST, INVALID_PARAMETER_VALUE
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.logger import get_logger

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
            f"Error looking up experiment '{experiment_name}'",
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


def _extract_param_from_all_sources(param: str) -> str | None:
    """Extract a parameter value from view_args, query args, and JSON body.

    Searches in the following order:
    1. URL path parameters (view_args)
    2. Query string parameters (request.args)
    3. JSON request body (request.json / request.get_json)

    Args:
        param: The parameter name to extract.

    Returns:
        The parameter value if found, None otherwise.
    """
    # Fastest: check view_args first
    if request.view_args and param in request.view_args:
        return request.view_args[param]
    # Next: check args (GET)
    if request.args and param in request.args:
        return request.args[param]
    # Last: check json (POST, PATCH, DELETE) — try request.json first (for mocking compatibility)
    try:
        if hasattr(request, "json") and request.json and param in request.json:
            return request.json[param]
    except Exception:
        pass
    # Fallback to get_json method
    try:
        json_data = request.get_json(silent=True)
        if json_data and param in json_data:
            return json_data[param]
    except Exception:
        pass
    return None


def get_experiment_id() -> str:
    """
    Helper function to get the experiment ID from the request.
    Checks view_args, query args, and JSON data in that order.
    Raises an exception if the experiment ID is not found.
    """
    experiment_id = _extract_param_from_all_sources("experiment_id")
    if experiment_id is not None:
        return experiment_id

    experiment_name = _extract_param_from_all_sources("experiment_name")
    if experiment_name is not None:
        return _experiment_id_from_name(experiment_name)

    raise MlflowException(
        "Either 'experiment_id' or 'experiment_name' must be provided in the request data.",
        INVALID_PARAMETER_VALUE,
    )


def get_model_id() -> str:
    """
    Helper function to get the model ID from the request.
    Raises an exception if the model ID is not found.
    """
    model_id = _extract_param_from_all_sources("model_id")
    if model_id is not None:
        return model_id
    raise MlflowException(
        "Model ID must be provided in the request data.",
        INVALID_PARAMETER_VALUE,
    )


def get_model_name() -> str:
    """
    Helper function to get the model name from the request.
    Raises an exception if the model name is not found.
    """
    name = _extract_param_from_all_sources("name")
    if name is not None:
        return name
    raise MlflowException(
        "Model name must be provided in the request data.",
        INVALID_PARAMETER_VALUE,
    )
