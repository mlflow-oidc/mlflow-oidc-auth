import re
from typing import Any, Callable, Dict, Optional

from flask import Request, redirect, render_template, request, session, url_for
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
    CreateLoggedModel,
    CreateRun,
    DeleteExperiment,
    DeleteExperimentTag,
    DeleteLoggedModel,
    DeleteLoggedModelTag,
    DeleteRun,
    DeleteTag,
    FinalizeLoggedModel,
    GetExperiment,
    GetExperimentByName,
    GetLoggedModel,
    GetMetricHistory,
    GetRun,
    ListArtifacts,
    LogBatch,
    LogLoggedModelParamsRequest,
    LogMetric,
    LogModel,
    LogParam,
    RestoreExperiment,
    RestoreRun,
    SetExperimentTag,
    SetLoggedModelTags,
    SetTag,
    UpdateExperiment,
    UpdateRun,
)
from mlflow.server.handlers import get_endpoints
from mlflow.utils.rest_utils import _REST_API_PATH_PREFIX

import mlflow_oidc_auth.responses as responses
from mlflow_oidc_auth import routes
from mlflow_oidc_auth.auth import authenticate_request_basic_auth, authenticate_request_bearer_token
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.utils import get_is_admin
from mlflow_oidc_auth.validators import (
    validate_can_create_user,
    validate_can_delete_experiment,
    validate_can_delete_experiment_artifact_proxy,
    validate_can_delete_logged_model,
    validate_can_delete_registered_model,
    validate_can_delete_run,
    validate_can_delete_user,
    validate_can_get_user_token,
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
    validate_can_update_user_admin,
    validate_can_update_user_password,
)


def _is_unprotected_route(path: str) -> bool:
    return path.startswith(
        (
            "/health",
            "/login",
            "/callback",
            "/oidc/static",
            "/metrics",
        )
    )


BEFORE_REQUEST_HANDLERS = {
    # Routes for experiments
    ## CreateExperiment: _validate_can_manage_experiment,
    GetExperiment: validate_can_read_experiment,
    GetExperimentByName: validate_can_read_experiment_by_name,
    DeleteExperiment: validate_can_delete_experiment,
    RestoreExperiment: validate_can_delete_experiment,
    UpdateExperiment: validate_can_update_experiment,
    SetExperimentTag: validate_can_update_experiment,
    DeleteExperimentTag: validate_can_update_experiment,
    # # Routes for runs
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
    # # Routes for model registry
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
}


def _get_before_request_handler(request_class):
    return BEFORE_REQUEST_HANDLERS.get(request_class)


BEFORE_REQUEST_VALIDATORS = {(http_path, method): handler for http_path, handler, methods in get_endpoints(_get_before_request_handler) for method in methods}

BEFORE_REQUEST_VALIDATORS.update(
    {
        (routes.CREATE_ACCESS_TOKEN, "PATCH"): validate_can_get_user_token,
        # (SIGNUP, "GET"): validate_can_create_user,
        # (routes.GET_USER, "GET"): validate_can_read_user,
        (routes.CREATE_USER, "POST"): validate_can_create_user,
        (routes.UPDATE_USER_PASSWORD, "PATCH"): validate_can_update_user_password,
        (routes.UPDATE_USER_ADMIN, "PATCH"): validate_can_update_user_admin,
        (routes.DELETE_USER, "DELETE"): validate_can_delete_user,
        (routes.USER_EXPERIMENT_PERMISSIONS, "GET"): validate_can_manage_experiment,
        (routes.USER_EXPERIMENT_PERMISSIONS, "POST"): validate_can_manage_experiment,
        (routes.USER_EXPERIMENT_PERMISSION_DETAIL, "GET"): validate_can_manage_experiment,
        (routes.USER_EXPERIMENT_PERMISSION_DETAIL, "POST"): validate_can_manage_experiment,
        (routes.USER_EXPERIMENT_PERMISSION_DETAIL, "PATCH"): validate_can_manage_experiment,
        (routes.USER_EXPERIMENT_PERMISSION_DETAIL, "DELETE"): validate_can_manage_experiment,
        (routes.EXPERIMENT_USER_PERMISSIONS, "GET"): validate_can_manage_experiment,
        (routes.EXPERIMENT_USER_PERMISSIONS, "POST"): validate_can_manage_experiment,
        (routes.EXPERIMENT_USER_PERMISSION_DETAIL, "GET"): validate_can_manage_experiment,
        (routes.EXPERIMENT_USER_PERMISSION_DETAIL, "POST"): validate_can_manage_experiment,
        (routes.EXPERIMENT_USER_PERMISSION_DETAIL, "PATCH"): validate_can_manage_experiment,
        (routes.EXPERIMENT_USER_PERMISSION_DETAIL, "DELETE"): validate_can_manage_experiment,
        (routes.USER_REGISTERED_MODEL_PERMISSIONS, "GET"): validate_can_manage_registered_model,
        (routes.USER_REGISTERED_MODEL_PERMISSIONS, "POST"): validate_can_manage_registered_model,
        (routes.USER_REGISTERED_MODEL_PERMISSION_DETAIL, "GET"): validate_can_manage_registered_model,
        (routes.USER_REGISTERED_MODEL_PERMISSION_DETAIL, "POST"): validate_can_manage_registered_model,
        (routes.USER_REGISTERED_MODEL_PERMISSION_DETAIL, "PATCH"): validate_can_manage_registered_model,
        (routes.USER_REGISTERED_MODEL_PERMISSION_DETAIL, "DELETE"): validate_can_manage_registered_model,
        (routes.REGISTERED_MODEL_USER_PERMISSIONS, "GET"): validate_can_manage_registered_model,
        (routes.REGISTERED_MODEL_USER_PERMISSIONS, "POST"): validate_can_manage_registered_model,
        (routes.REGISTERED_MODEL_USER_PERMISSION_DETAIL, "GET"): validate_can_manage_registered_model,
        (routes.REGISTERED_MODEL_USER_PERMISSION_DETAIL, "POST"): validate_can_manage_registered_model,
        (routes.REGISTERED_MODEL_USER_PERMISSION_DETAIL, "PATCH"): validate_can_manage_registered_model,
        (routes.REGISTERED_MODEL_USER_PERMISSION_DETAIL, "DELETE"): validate_can_manage_registered_model,
        (routes.USER_PROMPT_PERMISSIONS, "GET"): validate_can_manage_registered_model,
        (routes.USER_PROMPT_PERMISSIONS, "POST"): validate_can_manage_registered_model,
        (routes.USER_PROMPT_PERMISSION_DETAIL, "GET"): validate_can_manage_registered_model,
        (routes.USER_PROMPT_PERMISSION_DETAIL, "POST"): validate_can_manage_registered_model,
        (routes.USER_PROMPT_PERMISSION_DETAIL, "PATCH"): validate_can_manage_registered_model,
        (routes.USER_PROMPT_PERMISSION_DETAIL, "DELETE"): validate_can_manage_registered_model,
        (routes.PROMPT_USER_PERMISSIONS, "GET"): validate_can_manage_registered_model,
        (routes.PROMPT_USER_PERMISSIONS, "POST"): validate_can_manage_registered_model,
        (routes.PROMPT_USER_PERMISSION_DETAIL, "GET"): validate_can_manage_registered_model,
        (routes.PROMPT_USER_PERMISSION_DETAIL, "POST"): validate_can_manage_registered_model,
        (routes.PROMPT_USER_PERMISSION_DETAIL, "PATCH"): validate_can_manage_registered_model,
        (routes.PROMPT_USER_PERMISSION_DETAIL, "DELETE"): validate_can_manage_registered_model,
        (routes.USER_EXPERIMENT_PATTERN_PERMISSIONS, "GET"): validate_can_manage_experiment,
        (routes.USER_EXPERIMENT_PATTERN_PERMISSIONS, "POST"): validate_can_manage_experiment,
        (routes.USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL, "GET"): validate_can_manage_experiment,
        (routes.USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL, "POST"): validate_can_manage_experiment,
        (routes.USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL, "PATCH"): validate_can_manage_experiment,
        (routes.USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL, "DELETE"): validate_can_manage_experiment,
        (routes.USER_REGISTERED_MODEL_PATTERN_PERMISSIONS, "GET"): validate_can_manage_registered_model,
        (routes.USER_REGISTERED_MODEL_PATTERN_PERMISSIONS, "POST"): validate_can_manage_registered_model,
        (routes.USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL, "GET"): validate_can_manage_registered_model,
        (routes.USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL, "POST"): validate_can_manage_registered_model,
        (routes.USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL, "PATCH"): validate_can_manage_registered_model,
        (routes.USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL, "DELETE"): validate_can_manage_registered_model,
        (routes.USER_PROMPT_PATTERN_PERMISSIONS, "GET"): validate_can_manage_registered_model,
        (routes.USER_PROMPT_PATTERN_PERMISSIONS, "POST"): validate_can_manage_registered_model,
        (routes.USER_PROMPT_PATTERN_PERMISSION_DETAIL, "GET"): validate_can_manage_registered_model,
        (routes.USER_PROMPT_PATTERN_PERMISSION_DETAIL, "POST"): validate_can_manage_registered_model,
        (routes.USER_PROMPT_PATTERN_PERMISSION_DETAIL, "PATCH"): validate_can_manage_registered_model,
        (routes.USER_PROMPT_PATTERN_PERMISSION_DETAIL, "DELETE"): validate_can_manage_registered_model,
        (routes.GROUP_EXPERIMENT_PERMISSIONS, "GET"): validate_can_manage_experiment,
        (routes.GROUP_EXPERIMENT_PERMISSIONS, "POST"): validate_can_manage_experiment,
        (routes.GROUP_EXPERIMENT_PERMISSION_DETAIL, "GET"): validate_can_manage_experiment,
        (routes.GROUP_EXPERIMENT_PERMISSION_DETAIL, "POST"): validate_can_manage_experiment,
        (routes.GROUP_EXPERIMENT_PERMISSION_DETAIL, "PATCH"): validate_can_manage_experiment,
        (routes.GROUP_EXPERIMENT_PERMISSION_DETAIL, "DELETE"): validate_can_manage_experiment,
        (routes.EXPERIMENT_GROUP_PERMISSIONS, "GET"): validate_can_manage_experiment,
        (routes.EXPERIMENT_GROUP_PERMISSIONS, "POST"): validate_can_manage_experiment,
        (routes.EXPERIMENT_GROUP_PERMISSION_DETAIL, "GET"): validate_can_manage_experiment,
        (routes.EXPERIMENT_GROUP_PERMISSION_DETAIL, "POST"): validate_can_manage_experiment,
        (routes.EXPERIMENT_GROUP_PERMISSION_DETAIL, "PATCH"): validate_can_manage_experiment,
        (routes.EXPERIMENT_GROUP_PERMISSION_DETAIL, "DELETE"): validate_can_manage_experiment,
        (routes.GROUP_EXPERIMENT_PATTERN_PERMISSIONS, "GET"): validate_can_manage_experiment,
        (routes.GROUP_EXPERIMENT_PATTERN_PERMISSIONS, "POST"): validate_can_manage_experiment,
        (routes.GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL, "GET"): validate_can_manage_experiment,
        (routes.GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL, "POST"): validate_can_manage_experiment,
        (routes.GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL, "PATCH"): validate_can_manage_experiment,
        (routes.GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL, "DELETE"): validate_can_manage_experiment,
        (routes.GROUP_REGISTERED_MODEL_PERMISSIONS, "GET"): validate_can_manage_registered_model,
        (routes.GROUP_REGISTERED_MODEL_PERMISSIONS, "POST"): validate_can_manage_registered_model,
        (routes.GROUP_REGISTERED_MODEL_PERMISSION_DETAIL, "GET"): validate_can_manage_registered_model,
        (routes.GROUP_REGISTERED_MODEL_PERMISSION_DETAIL, "POST"): validate_can_manage_registered_model,
        (routes.GROUP_REGISTERED_MODEL_PERMISSION_DETAIL, "PATCH"): validate_can_manage_registered_model,
        (routes.GROUP_REGISTERED_MODEL_PERMISSION_DETAIL, "DELETE"): validate_can_manage_registered_model,
        (routes.REGISTERED_MODEL_GROUP_PERMISSIONS, "GET"): validate_can_manage_registered_model,
        (routes.REGISTERED_MODEL_GROUP_PERMISSIONS, "POST"): validate_can_manage_registered_model,
        (routes.REGISTERED_MODEL_GROUP_PERMISSION_DETAIL, "GET"): validate_can_manage_registered_model,
        (routes.REGISTERED_MODEL_GROUP_PERMISSION_DETAIL, "POST"): validate_can_manage_registered_model,
        (routes.REGISTERED_MODEL_GROUP_PERMISSION_DETAIL, "PATCH"): validate_can_manage_registered_model,
        (routes.REGISTERED_MODEL_GROUP_PERMISSION_DETAIL, "DELETE"): validate_can_manage_registered_model,
        (routes.GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS, "GET"): validate_can_manage_registered_model,
        (routes.GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS, "POST"): validate_can_manage_registered_model,
        (routes.GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL, "GET"): validate_can_manage_registered_model,
        (routes.GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL, "POST"): validate_can_manage_registered_model,
        (routes.GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL, "PATCH"): validate_can_manage_registered_model,
        (routes.GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL, "DELETE"): validate_can_manage_registered_model,
        (routes.GROUP_PROMPT_PERMISSIONS, "GET"): validate_can_manage_registered_model,
        (routes.GROUP_PROMPT_PERMISSIONS, "POST"): validate_can_manage_registered_model,
        (routes.GROUP_PROMPT_PERMISSION_DETAIL, "GET"): validate_can_manage_registered_model,
        (routes.GROUP_PROMPT_PERMISSION_DETAIL, "POST"): validate_can_manage_registered_model,
        (routes.GROUP_PROMPT_PERMISSION_DETAIL, "PATCH"): validate_can_manage_registered_model,
        (routes.GROUP_PROMPT_PERMISSION_DETAIL, "DELETE"): validate_can_manage_registered_model,
        (routes.PROMPT_GROUP_PERMISSIONS, "GET"): validate_can_manage_registered_model,
        (routes.PROMPT_GROUP_PERMISSIONS, "POST"): validate_can_manage_registered_model,
        (routes.PROMPT_GROUP_PERMISSION_DETAIL, "GET"): validate_can_manage_registered_model,
        (routes.PROMPT_GROUP_PERMISSION_DETAIL, "POST"): validate_can_manage_registered_model,
        (routes.PROMPT_GROUP_PERMISSION_DETAIL, "PATCH"): validate_can_manage_registered_model,
        (routes.PROMPT_GROUP_PERMISSION_DETAIL, "DELETE"): validate_can_manage_registered_model,
        (routes.GROUP_PROMPT_PATTERN_PERMISSIONS, "GET"): validate_can_manage_registered_model,
        (routes.GROUP_PROMPT_PATTERN_PERMISSIONS, "POST"): validate_can_manage_registered_model,
        (routes.GROUP_PROMPT_PATTERN_PERMISSION_DETAIL, "GET"): validate_can_manage_registered_model,
        (routes.GROUP_PROMPT_PATTERN_PERMISSION_DETAIL, "POST"): validate_can_manage_registered_model,
        (routes.GROUP_PROMPT_PATTERN_PERMISSION_DETAIL, "PATCH"): validate_can_manage_registered_model,
        (routes.GROUP_PROMPT_PATTERN_PERMISSION_DETAIL, "DELETE"): validate_can_manage_registered_model,
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


def _get_proxy_artifact_validator(method: str, view_args: Optional[Dict[str, Any]]) -> Optional[Callable[[], bool]]:
    if view_args is None:
        return validate_can_read_experiment_artifact_proxy  # List

    return {
        "GET": validate_can_read_experiment_artifact_proxy,  # Download
        "PUT": validate_can_update_experiment_artifact_proxy,  # Upload
        "DELETE": validate_can_delete_experiment_artifact_proxy,  # Delete
    }.get(method)


def _is_proxy_artifact_path(path: str) -> bool:
    return path.startswith(f"{_REST_API_PATH_PREFIX}/mlflow-artifacts/artifacts/")


def _find_validator(req: Request) -> Optional[Callable[[], bool]]:
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
    if request.authorization is not None:
        if request.authorization.type == "basic":
            if not authenticate_request_basic_auth():
                return responses.make_basic_auth_response()
        if request.authorization.type == "bearer":
            if not authenticate_request_bearer_token():
                return responses.make_auth_required_response()
    else:
        if session.get("username") is None:
            session.clear()

            if config.AUTOMATIC_LOGIN_REDIRECT:
                return redirect(url_for("login"))
            return render_template(
                "auth.html",
                username=None,
                provide_display_name=config.OIDC_PROVIDER_DISPLAY_NAME,
            )
    # admins don't need to be authorized
    if get_is_admin():
        return
    # authorization
    if validator := _find_validator(request):
        if not validator():
            return responses.make_forbidden_response()
    elif _is_proxy_artifact_path(request.path):
        if validator := _get_proxy_artifact_validator(request.method, request.view_args):
            if not validator():
                return responses.make_forbidden_response()
