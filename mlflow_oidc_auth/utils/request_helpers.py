import json

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
    # On a proto route MLflow proto-parses exactly one source (the query string for a
    # GET with a non-empty one, the body otherwise — including a DELETE/PATCH body sent
    # without a JSON content type, which MLflow force-parses). Read that source and
    # nothing else, so the value authorized is the value MLflow acts on (issue #285).
    is_proto_route, value = _proto_route_value(param)
    if is_proto_route:
        if value is None and param == "run_id":
            # MLflow's run handlers act on ``run_id or run_uuid``.
            return get_request_param("run_uuid")
        if value is None:
            raise MlflowException(
                f"Missing value for required parameter '{param}'. " "See the API docs for more information about request parameters.",
                INVALID_PARAMETER_VALUE,
            )
        if not value or (isinstance(value, str) and not value.strip()):
            raise MlflowException(
                f"Empty value for required parameter '{param}'. " "See the API docs for more information about request parameters.",
                INVALID_PARAMETER_VALUE,
            )
        return value

    # Off the proto surface, each handler sources its parameters itself; this is the
    # method-based reading those plain Flask handlers (/get-artifact, promptlab, ...) use.
    #
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


def _proto_route_value(param: str) -> tuple[bool, object]:
    """``(is_proto_route, value)`` — the value MLflow itself will act on for ``param``.

    On a proto route that is a path parameter (view_args) when present, else whichever
    single source ``_get_request_message`` proto-parses: the query string for a GET with
    a non-empty one, the request body for everything else. A path parameter that
    disagrees with the proto body is rejected outright — see below.

    Deliberately there is no cross-source fallback on a proto route: if the value is
    absent from the source MLflow reads, then MLflow does not see it either, and
    guessing from a source it ignores is exactly the divergence issue #285 closed.
    Values from the sources MLflow ignores are not dropped, though — they are added to
    the set that must be authorized by :func:`get_request_param_values` and friends.

    Returns ``(False, None)`` off the proto surface, where the caller must use its own
    handler-specific sourcing.
    """
    # Imported lazily: mlflow_oidc_auth.hooks.__init__ imports before_request, which
    # imports the validators that import this module, so a module-level import would
    # be circular. Module objects are cached in sys.modules, making this a dict lookup.
    from mlflow_oidc_auth.hooks.dual_spelling_guard import proto_request_value

    is_proto_route, proto_value = proto_request_value(request, param)
    if not is_proto_route:
        return False, None
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
    if path_value is not None and proto_value is not None and path_value != proto_value:
        raise MlflowException(
            f"Ambiguous request: '{param}' was given as both a path parameter and a request body field, with different values.",
            INVALID_PARAMETER_VALUE,
        )
    return True, path_value if path_value is not None else proto_value


def _extract_param_from_all_sources(param: str) -> str | None:
    """Extract a parameter value from the source MLflow itself will read.

    On a proto route this is exactly :func:`_proto_route_value`. On a non-proto route
    MLflow's sourcing is handler-specific, so fall back to view_args, then query args,
    then the JSON body.

    This returns the ONE value MLflow acts on. Authorization must not stop there: use
    the plural helpers (:func:`get_experiment_ids`, :func:`get_model_names`, ...) which
    also require permission on every value the other sources carry.

    Args:
        param: The parameter name to extract.

    Returns:
        The parameter value if found, None otherwise.
    """
    is_proto_route, value = _proto_route_value(param)
    if is_proto_route:
        return value

    path_value = request.view_args.get(param) if request.view_args else None
    if path_value is not None:
        return path_value
    # Next: check args (GET)
    if request.args and param in request.args:
        return request.args[param]
    # Last: check json (POST, PATCH, DELETE) — try request.json first (for mocking compatibility)
    try:
        if hasattr(request, "json") and request.json and param in request.json:
            return request.json[param]
    except Exception:
        pass  # an unreadable source contributes no value; the caller decides on what it did read
    # Fallback to get_json method
    try:
        json_data = request.get_json(silent=True)
        if json_data and param in json_data:
            return json_data[param]
    except Exception:
        pass  # an unreadable source contributes no value; the caller decides on what it did read
    return None


# ---------------------------------------------------------------------------
# Union of every request source (issues #285, #288)
#
# Mirroring MLflow's source picks the value MLflow acts on, but it is a model of
# MLflow's parsing that has to be kept in step by hand — and it has drifted before
# (#270, #283, #285, #288). So on top of it, every value a request carries for a field,
# in ANY source (path, query string, JSON body under either proto spelling, form), must
# be authorized. A legitimate client names a resource once, or names the same one in
# two places, so this never costs real traffic anything; a request that names two
# different resources is decided against both, and denied unless the caller holds the
# permission on every one. Whichever of them MLflow ends up acting on — even if our
# model of its parsing is wrong — has then been authorized.
# ---------------------------------------------------------------------------


def _is_scalar(value: object) -> bool:
    """True for a value that can name a single resource (str / int / float, not bool)."""
    return isinstance(value, (str, int, float)) and not isinstance(value, bool)


def request_body_dict() -> dict:
    """The request body as the dict MLflow would parse, or ``{}``.

    On a proto route this is MLflow's own ``_get_normalized_request_json`` (force-parsed,
    double-encoding aware), exactly as the dual-spelling guard reads it. Off the proto
    surface the body is read only when it is declared JSON: force-parsing an arbitrary
    body would buffer a streamed artifact upload into memory and leave the stream empty
    for the handler. A JSON body that is itself a JSON-encoded string is decoded a second
    time, as MLflow's plain JSON handlers (``_get_normalized_request_json``) do.
    """
    from mlflow_oidc_auth.hooks.dual_spelling_guard import _is_proto_route, _request_body

    try:
        if _is_proto_route(request.path, request.method):
            data = _request_body(request)
        elif request.is_json:
            data = request.get_json(silent=True)
            if isinstance(data, str):
                data = json.loads(data)
        else:
            data = None
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _form_values(param: str) -> list:
    if request.mimetype not in ("application/x-www-form-urlencoded", "multipart/form-data"):
        return []
    try:
        return list(request.form.getlist(param))
    except Exception:
        return []


def all_source_values(*params: str) -> list:
    """Every distinct non-empty value for any of ``params``, from every request source.

    Sources: path parameters, then — under both the snake_case and the lowerCamelCase
    proto spelling — every repetition in the query string, the JSON body (list values
    contribute their items), and form fields. Order is deterministic and
    duplicates are dropped by their string form, so ``1`` and ``"1"`` count once.
    """
    # The guard's own spelling function, imported lazily like _proto_route_value's
    # import, so the camelCase the union checks can never drift from the one the
    # dual-spelling guard and proto_request_value use.
    from mlflow_oidc_auth.hooks.dual_spelling_guard import _snake_to_camel

    values: list = []
    view_args = request.view_args if isinstance(request.view_args, dict) else {}
    body = request_body_dict()
    for param in params:
        values.append(view_args.get(param))
        # Both spellings everywhere. MLflow reads only the snake_case one from a query
        # string, but a value it cannot read costs nothing to authorize, and not having
        # to know which spelling each source honours is the point of the union.
        spellings = tuple(dict.fromkeys((param, _snake_to_camel(param))))
        for key in spellings:
            try:
                values.extend(request.args.getlist(key))
            except Exception:
                pass  # an unreadable source contributes no value; the caller decides on what it did read
            value = body.get(key)
            values.extend(value if isinstance(value, list) else [value])
            values.extend(_form_values(key))

    distinct: dict = {}
    for value in values:
        if not _is_scalar(value):
            continue
        key = str(value)
        if key.strip() and key not in distinct:
            distinct[key] = value
    return list(distinct.values())


def _with_all_sources(primary: object, *params: str) -> list:
    """``primary`` (the value MLflow acts on) first, then every other distinct value."""
    values = [primary] if primary is not None else []
    seen = {str(primary)} if primary is not None else set()
    for value in all_source_values(*params):
        if str(value) not in seen:
            seen.add(str(value))
            values.append(value)
    return values


def get_request_param_values(param: str) -> list:
    """Every value of ``param`` that must be authorized, MLflow's own first.

    The first element is :func:`get_request_param` — which still raises when the
    parameter is missing from the source MLflow reads, so an unresolvable resource is a
    400, never an allow. The rest are the distinct values any other source carries. For
    ``run_id`` the ``run_uuid`` alias is included, because MLflow acts on either.
    """
    params = (param, "run_uuid") if param == "run_id" else (param,)
    return _with_all_sources(get_request_param(param), *params)


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


def get_experiment_ids() -> list:
    """Every experiment id that must be authorized, the one MLflow acts on first.

    The primary value is :func:`get_experiment_id` (and raises as it does). Then every
    ``experiment_id`` any other source carries. When the request identifies the
    experiment by name, every ``experiment_name`` is resolved and included as well.
    """
    primary = get_experiment_id()
    ids = _with_all_sources(primary, "experiment_id")
    if _extract_param_from_all_sources("experiment_id") is None:
        for name in all_source_values("experiment_name"):
            experiment_id = _experiment_id_from_name(name)
            if str(experiment_id) not in {str(i) for i in ids}:
                ids.append(experiment_id)
    return ids


def get_model_ids() -> list:
    """Every logged-model id that must be authorized, the one MLflow acts on first."""
    return _with_all_sources(get_model_id(), "model_id")


def get_model_names() -> list:
    """Every registered-model name that must be authorized, the one MLflow acts on first."""
    return _with_all_sources(get_model_name(), "name")
