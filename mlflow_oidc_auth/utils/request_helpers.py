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
    # HEAD is folded onto GET (issue #286). werkzeug dispatches HEAD to the GET view,
    # and _find_validator now folds it too, so a HEAD reaches these validators for the
    # first time. Without the same fold here, the "unsupported method" branch fired and
    # every HEAD on a gated route was refused with 400 — including for the rightful
    # owner, and including routes MLflow serves happily (/get-artifact is registered
    # GET+HEAD and its handler reads request.args with no method check). Closing the
    # HEAD hole must make HEAD reach the SAME decision as its GET twin, not deny it.
    if request.method in ("GET", "HEAD"):
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
    # HEAD folds onto GET for the same reason as get_request_param (issue #286).
    if request.method in ("GET", "HEAD"):
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
    """Extract a parameter value from the source MLflow itself will read.

    Order:
    1. A path parameter that disagrees with the proto body is rejected outright — see
       the ambiguity check below.
    2. URL path parameters (view_args), which most MLflow handlers read directly.
    3. On a proto route, whichever single source MLflow will proto-parse: the query
       string for a GET with a non-empty one, the request body for everything else.
    4. On a non-proto route, fall back to scanning query args then the JSON body.

    Step 2 exists because MLflow **ignores the query string entirely** on every
    non-GET route. Preferring query args there authorized one resource while MLflow
    mutated another — a cross-tenant rename/delete needing nothing but a query
    parameter (issue #285). Deliberately there is no cross-source fallback on a proto
    route: if the value is absent from the source MLflow reads, then MLflow does not
    see it either, and guessing from a source it ignores is exactly the divergence
    this closes.

    Args:
        param: The parameter name to extract.

    Returns:
        The parameter value if found, None otherwise.
    """
    # Imported lazily: mlflow_oidc_auth.hooks.__init__ imports before_request, which
    # imports the validators that import this module, so a module-level import would
    # be circular. Module objects are cached in sys.modules, making this a dict lookup.
    from mlflow_oidc_auth.hooks.dual_spelling_guard import proto_request_value

    is_proto_route, proto_value = proto_request_value(request, param)
    path_value = request.view_args.get(param) if request.view_args else None

    # A path parameter and a proto body that name DIFFERENT resources is unresolvable
    # without per-route knowledge of MLflow's handler, and guessing is unsafe in both
    # directions. Most handlers act on the path argument, but FinalizeLoggedModel
    # (PATCH /logged-models/<model_id>) ignores it and acts on request_message.model_id
    # from the body — so "path wins" authorizes the URL while MLflow mutates the body's
    # model, and "body wins" breaks the opposite way on every other route. No legitimate
    # client sends two different values for one field, so reject the ambiguity outright
    # rather than pick a side, exactly as the dual-spelling guard does for two spellings.
    # This raises INVALID_PARAMETER_VALUE, which catch_mlflow_exception turns into a 400
    # returned from the hook, so the view never runs.
    if is_proto_route and path_value is not None and proto_value is not None and path_value != proto_value:
        raise MlflowException(
            f"Ambiguous request: '{param}' was given as both a path parameter and a request body field, with different values.",
            INVALID_PARAMETER_VALUE,
        )

    if path_value is not None:
        return path_value
    if is_proto_route:
        return proto_value

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


def get_run_id() -> str:
    """Get the run id from the source MLflow itself will read.

    Unlike ``get_request_param("run_id")`` this goes through
    ``_extract_param_from_all_sources``, so on a proto route it reads exactly the source
    MLflow proto-parses and accepts the ``runId`` json_name spelling too. Used by
    validators for proto routes carrying a run id in the body; the older helper is left
    alone because many validators depend on its behaviour.

    Raises:
        MlflowException: INVALID_PARAMETER_VALUE if no run id is present, which
        ``catch_mlflow_exception`` turns into a 400 returned from the hook.
    """
    run_id = _extract_param_from_all_sources("run_id")
    if run_id is None:
        # Some MLflow routes spell it run_uuid.
        run_id = _extract_param_from_all_sources("run_uuid")
    if run_id is not None:
        return run_id
    raise MlflowException(
        "Run ID must be provided in the request data.",
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
