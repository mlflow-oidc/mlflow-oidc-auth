import re
from typing import Any, Callable, Dict, Optional

from flask import Request, g, request
from mlflow.protos.model_registry_pb2 import (
    CreateModelVersion,
    DeleteModelVersion,
    DeleteModelVersionTag,
    DeleteRegisteredModel,
    DeleteRegisteredModelAlias,
    DeleteRegisteredModelTag,
    GetLatestVersions,
    GetModelVersion,
    GetModelVersionByAlias,
    GetModelVersionDownloadUri,
    GetRegisteredModel,
    RenameRegisteredModel,
    SetModelVersionTag,
    SetRegisteredModelAlias,
    SetRegisteredModelTag,
    TransitionModelVersionStage,
    UpdateModelVersion,
    UpdateRegisteredModel,
)
from mlflow.protos.service_pb2 import (
    AttachModelToGatewayEndpoint,
    CreateGatewayEndpoint,
    CreateGatewayEndpointBinding,
    CreateGatewayModelDefinition,
    CreateGatewaySecret,
    CreateLoggedModel,
    CreateRun,
    DeleteExperiment,
    DeleteExperimentTag,
    DeleteGatewayEndpoint,
    DeleteGatewayEndpointBinding,
    DeleteGatewayEndpointTag,
    DeleteGatewayModelDefinition,
    DeleteGatewaySecret,
    DeleteLoggedModel,
    DeleteLoggedModelTag,
    DeleteRun,
    DeleteTag,
    DetachModelFromGatewayEndpoint,
    FinalizeLoggedModel,
    GetExperiment,
    GetExperimentByName,
    GetGatewayEndpoint,
    GetGatewayModelDefinition,
    GetGatewaySecretInfo,
    GetLoggedModel,
    GetMetricHistory,
    GetRun,
    ListArtifacts,
    ListGatewayEndpointBindings,
    LogBatch,
    LogLoggedModelParamsRequest,
    LogMetric,
    LogModel,
    LogParam,
    RestoreExperiment,
    RestoreRun,
    SetExperimentTag,
    SetGatewayEndpointTag,
    SetLoggedModelTags,
    SetTag,
    UpdateExperiment,
    UpdateGatewayEndpoint,
    UpdateGatewayModelDefinition,
    UpdateGatewaySecret,
    UpdateRun,
    RegisterScorer,
    ListScorers,
    GetScorer,
    DeleteScorer,
    ListScorerVersions,
)

from mlflow.server.handlers import catch_mlflow_exception, get_endpoints
from mlflow.utils.rest_utils import _REST_API_PATH_PREFIX

from mlflow_oidc_auth.bridge import get_fastapi_admin_status, get_fastapi_username
import mlflow_oidc_auth.responses as responses
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.validators import (
    validate_can_delete_experiment,
    validate_can_delete_experiment_artifact_proxy,
    validate_can_delete_logged_model,
    validate_can_delete_registered_model,
    validate_can_delete_run,
    validate_can_manage_experiment,
    validate_can_manage_registered_model,
    validate_can_read_experiment,
    validate_can_read_experiment_artifact_proxy,
    validate_can_read_experiment_by_name,
    validate_can_read_logged_model,
    validate_can_read_registered_model,
    validate_can_read_run,
    validate_can_update_experiment,
    validate_can_update_experiment_artifact_proxy,
    validate_can_update_logged_model,
    validate_can_update_registered_model,
    validate_can_update_run,
    validate_can_read_experiments_from_experiment_ids,
    validate_can_update_experiment_from_experiment_id,
    validate_can_read_metric_history_bulk_interval,
    validate_can_read_traces_from_experiment_ids,
    validate_can_read_trace,
    validate_can_update_trace_from_experiment_id,
    validate_can_update_trace_from_run_id,
    validate_can_update_trace,
    validate_can_delete_traces_from_experiment_id,
    validate_can_delete_scorer,
    validate_can_manage_scorer,
    validate_can_manage_scorer_permission,
    validate_can_read_scorer,
    validate_can_update_scorer,
    validate_can_read_run_artifact,
    validate_can_update_run_artifact,
    validate_can_read_model_version_artifact,
    validate_can_read_trace_artifact,
    validate_can_read_metric_history_bulk,
    validate_can_search_datasets,
    validate_can_create_promptlab_run,
    validate_gateway_proxy,
    validate_can_read_gateway_endpoint,
    validate_can_update_gateway_endpoint,
    validate_can_delete_gateway_endpoint,
    validate_can_read_gateway_secret,
    validate_can_update_gateway_secret,
    validate_can_delete_gateway_secret,
    validate_can_read_gateway_model_definition,
    validate_can_update_gateway_model_definition,
    validate_can_delete_gateway_model_definition,
    validate_can_create_gateway,
)


def _is_unprotected_route(path: str) -> bool:
    return path.startswith(("/static", "/favicon.ico", "/health", "/metrics", "/docs", "/redoc", "/openapi.json"))


def _get_auth_context() -> tuple[Optional[str], bool]:
    """Best-effort retrieval of auth context injected by FastAPI."""
    try:
        username = get_fastapi_username()
    except Exception:
        username = None

    try:
        is_admin = get_fastapi_admin_status()
    except Exception:
        is_admin = False

    return username, is_admin


BEFORE_REQUEST_HANDLERS = {
    # Routes for experiments
    GetExperiment: validate_can_read_experiment,
    GetExperimentByName: validate_can_read_experiment_by_name,
    DeleteExperiment: validate_can_delete_experiment,
    RestoreExperiment: validate_can_delete_experiment,
    UpdateExperiment: validate_can_update_experiment,
    SetExperimentTag: validate_can_update_experiment,
    DeleteExperimentTag: validate_can_update_experiment,
    # Routes for runs
    CreateRun: validate_can_update_experiment,
    GetRun: validate_can_read_run,
    DeleteRun: validate_can_delete_run,
    RestoreRun: validate_can_delete_run,
    UpdateRun: validate_can_update_run,
    LogMetric: validate_can_update_run,
    LogBatch: validate_can_update_run,
    LogModel: validate_can_update_run,
    SetTag: validate_can_update_run,
    DeleteTag: validate_can_update_run,
    LogParam: validate_can_update_run,
    GetMetricHistory: validate_can_read_run,
    ListArtifacts: validate_can_read_run,
    # Routes for model registry
    GetRegisteredModel: validate_can_read_registered_model,
    DeleteRegisteredModel: validate_can_delete_registered_model,
    UpdateRegisteredModel: validate_can_update_registered_model,
    RenameRegisteredModel: validate_can_update_registered_model,
    GetLatestVersions: validate_can_read_registered_model,
    CreateModelVersion: validate_can_update_registered_model,
    GetModelVersion: validate_can_read_registered_model,
    DeleteModelVersion: validate_can_delete_registered_model,
    UpdateModelVersion: validate_can_update_registered_model,
    TransitionModelVersionStage: validate_can_update_registered_model,
    GetModelVersionDownloadUri: validate_can_read_registered_model,
    SetRegisteredModelTag: validate_can_update_registered_model,
    DeleteRegisteredModelTag: validate_can_update_registered_model,
    SetModelVersionTag: validate_can_update_registered_model,
    DeleteModelVersionTag: validate_can_delete_registered_model,
    SetRegisteredModelAlias: validate_can_update_registered_model,
    DeleteRegisteredModelAlias: validate_can_delete_registered_model,
    GetModelVersionByAlias: validate_can_read_registered_model,
    # Routes for scorers
    RegisterScorer: validate_can_update_experiment,
    ListScorers: validate_can_read_experiment,
    GetScorer: validate_can_read_scorer,
    DeleteScorer: validate_can_delete_scorer,
    ListScorerVersions: validate_can_read_scorer,
    # Routes for gateway endpoints
    CreateGatewayEndpoint: validate_can_create_gateway,
    GetGatewayEndpoint: validate_can_read_gateway_endpoint,
    UpdateGatewayEndpoint: validate_can_update_gateway_endpoint,
    DeleteGatewayEndpoint: validate_can_delete_gateway_endpoint,
    # Routes for gateway secrets
    CreateGatewaySecret: validate_can_create_gateway,
    GetGatewaySecretInfo: validate_can_read_gateway_secret,
    UpdateGatewaySecret: validate_can_update_gateway_secret,
    DeleteGatewaySecret: validate_can_delete_gateway_secret,
    # Routes for gateway model definitions
    CreateGatewayModelDefinition: validate_can_create_gateway,
    GetGatewayModelDefinition: validate_can_read_gateway_model_definition,
    UpdateGatewayModelDefinition: validate_can_update_gateway_model_definition,
    DeleteGatewayModelDefinition: validate_can_delete_gateway_model_definition,
    # Routes for gateway endpoint-model mappings
    AttachModelToGatewayEndpoint: validate_can_update_gateway_endpoint,
    DetachModelFromGatewayEndpoint: validate_can_update_gateway_endpoint,
    # Routes for gateway endpoint bindings
    CreateGatewayEndpointBinding: validate_can_update_gateway_endpoint,
    DeleteGatewayEndpointBinding: validate_can_update_gateway_endpoint,
    ListGatewayEndpointBindings: validate_can_read_gateway_endpoint,
    # Routes for gateway endpoint tags
    SetGatewayEndpointTag: validate_can_update_gateway_endpoint,
    DeleteGatewayEndpointTag: validate_can_update_gateway_endpoint,
}

# `mlflow.server.handlers.get_endpoints()` also includes non-protobuf endpoints like `/graphql`
# and Gateway discovery routes, whose handlers are *not* our auth validators. We must not treat
# those as validators (they don't accept `username`), otherwise the hook will crash at runtime.
_PROTO_VALIDATORS = set(BEFORE_REQUEST_HANDLERS.values())


logger = get_logger()


def _get_before_request_handler(request_class):
    return BEFORE_REQUEST_HANDLERS.get(request_class)


BEFORE_REQUEST_VALIDATORS = {
    (http_path, method): handler
    for http_path, handler, methods in get_endpoints(_get_before_request_handler)
    for method in methods
    if handler in _PROTO_VALIDATORS
}

from mlflow.server.handlers import _add_static_prefix, _get_ajax_path

# Flask routes (not part of Protobuf API)
GET_ARTIFACT = _add_static_prefix("/get-artifact")
UPLOAD_ARTIFACT = _get_ajax_path("/mlflow/upload-artifact")
GET_MODEL_VERSION_ARTIFACT = _add_static_prefix("/model-versions/get-artifact")
GET_TRACE_ARTIFACT = _get_ajax_path("/mlflow/get-trace-artifact")
GET_METRIC_HISTORY_BULK = _get_ajax_path("/mlflow/metrics/get-history-bulk")
GET_METRIC_HISTORY_BULK_INTERVAL = _get_ajax_path("/mlflow/metrics/get-history-bulk-interval")
SEARCH_DATASETS = _get_ajax_path("/mlflow/experiments/search-datasets")
CREATE_PROMPTLAB_RUN = _get_ajax_path("/mlflow/runs/create-promptlab-run")
GATEWAY_PROXY = _get_ajax_path("/mlflow/gateway-proxy")

# Flask routes (no proto mapping)
BEFORE_REQUEST_VALIDATORS.update(
    {
        (GET_ARTIFACT, "GET"): validate_can_read_run_artifact,
        (UPLOAD_ARTIFACT, "POST"): validate_can_update_run_artifact,
        (GET_MODEL_VERSION_ARTIFACT, "GET"): validate_can_read_model_version_artifact,
        (GET_TRACE_ARTIFACT, "GET"): validate_can_read_trace_artifact,
        (GET_METRIC_HISTORY_BULK, "GET"): validate_can_read_metric_history_bulk,
        (GET_METRIC_HISTORY_BULK_INTERVAL, "GET"): validate_can_read_metric_history_bulk_interval,
        (SEARCH_DATASETS, "POST"): validate_can_search_datasets,
        (CREATE_PROMPTLAB_RUN, "POST"): validate_can_create_promptlab_run,
        (GATEWAY_PROXY, "GET"): validate_gateway_proxy,
        (GATEWAY_PROXY, "POST"): validate_gateway_proxy,
    }
)

LOGGED_MODEL_BEFORE_REQUEST_HANDLERS = {
    CreateLoggedModel: validate_can_update_experiment,
    GetLoggedModel: validate_can_read_logged_model,
    DeleteLoggedModel: validate_can_delete_logged_model,
    FinalizeLoggedModel: validate_can_update_logged_model,
    DeleteLoggedModelTag: validate_can_delete_logged_model,
    SetLoggedModelTags: validate_can_update_logged_model,
    LogLoggedModelParamsRequest: validate_can_update_logged_model,
}


def get_logged_model_before_request_handler(request_class):
    return LOGGED_MODEL_BEFORE_REQUEST_HANDLERS.get(request_class)


def _re_compile_path(path: str) -> re.Pattern:
    """
    Convert a path with angle brackets to a regex pattern. For example,
    "/api/2.0/experiments/<experiment_id>" becomes "/api/2.0/experiments/([^/]+)".
    """
    return re.compile(re.sub(r"<([^>]+)>", r"([^/]+)", path))


LOGGED_MODEL_BEFORE_REQUEST_VALIDATORS = {
    # Paths for logged models contains path parameters (e.g. /mlflow/logged-models/<model_id>)
    (_re_compile_path(http_path), method): handler
    for http_path, handler, methods in get_endpoints(get_logged_model_before_request_handler)
    for method in methods
}


def _get_proxy_artifact_validator(method: str, view_args: Optional[Dict[str, Any]]) -> Optional[Callable[[str], bool]]:
    if view_args is None:
        return validate_can_read_experiment_artifact_proxy  # List

    return {
        "GET": validate_can_read_experiment_artifact_proxy,  # Download
        "PUT": validate_can_update_experiment_artifact_proxy,  # Upload
        "DELETE": validate_can_delete_experiment_artifact_proxy,  # Delete
    }.get(method)


def _is_proxy_artifact_path(path: str) -> bool:
    return path.startswith(f"{_REST_API_PATH_PREFIX}/mlflow-artifacts/artifacts/")


def _find_validator(req: Request) -> Optional[Callable[[str], bool]]:
    """
    Finds the validator matching the request path and method.
    """
    if "/mlflow/logged-models" in req.path:
        # logged model routes are not registered in the app
        # so we need to check them manually
        return next(
            (v for (pat, method), v in LOGGED_MODEL_BEFORE_REQUEST_VALIDATORS.items() if pat.fullmatch(req.path) and method == req.method),
            None,
        )
    else:
        return BEFORE_REQUEST_VALIDATORS.get((req.path, req.method))


def before_request_hook():
    """Called before each request. If it did not return a response,
    the view function for the matched route is called and returns a response"""

    if _is_unprotected_route(request.path):
        return

    username, is_admin = _get_auth_context()
    if username is None:
        return responses.make_auth_required_response()

    logger.debug(f"Before request hook called for path: {request.path}, method: {request.method}, username: {username}, is admin: {is_admin}")
    validator = _find_validator(request)
    _stash_gateway_context(validator)
    if is_admin:
        return
    # authorization
    if validator:
        if not validator(username):
            return responses.make_forbidden_response()
    elif _is_proxy_artifact_path(request.path):
        if validator := _get_proxy_artifact_validator(request.method, request.view_args):
            if not validator(username):
                return responses.make_forbidden_response()


before_request_hook = catch_mlflow_exception(before_request_hook)


def _stash_gateway_context(validator) -> None:
    """Resolve and stash gateway resource names for after-request handlers.

    This must run for ALL users (including admins) because after-request
    handlers need the old resource name to propagate permission changes
    (renames) or clean up permission records (deletes).  The before-request
    validators run only for non-admin users and therefore cannot be relied
    upon for stashing.

    The tracking store still has the old name/state at before-request time,
    so ID-based resolution works correctly here.
    """
    if validator is None:
        return

    from mlflow_oidc_auth.validators.gateway import (
        _resolve_endpoint_name_from_id,
        _resolve_secret_name_from_id,
        _resolve_model_definition_name_from_id,
    )

    # --- Gateway endpoint: update (rename) or delete ---
    if validator in (validate_can_update_gateway_endpoint, validate_can_delete_gateway_endpoint):
        data = request.get_json(force=True, silent=True) or {}
        endpoint_id = data.get("endpoint_id")
        if endpoint_id:
            name = _resolve_endpoint_name_from_id(endpoint_id)
            if name:
                if validator is validate_can_update_gateway_endpoint:
                    g._updating_gateway_endpoint_old_name = name
                else:
                    g._deleting_gateway_endpoint_name = name
        return

    # --- Gateway secret: delete ---
    if validator is validate_can_delete_gateway_secret:
        data = request.get_json(force=True, silent=True) or {}
        secret_name = data.get("secret_name")
        if not secret_name:
            secret_id = data.get("secret_id")
            if secret_id:
                secret_name = _resolve_secret_name_from_id(secret_id)
        if secret_name:
            g._deleting_gateway_secret_name = secret_name
        return

    # --- Gateway model definition: delete ---
    if validator is validate_can_delete_gateway_model_definition:
        data = request.get_json(force=True, silent=True) or {}
        name = data.get("name")
        if not name:
            model_definition_id = data.get("model_definition_id")
            if model_definition_id:
                name = _resolve_model_definition_name_from_id(model_definition_id)
        if name:
            g._deleting_gateway_model_definition_name = name
        return
