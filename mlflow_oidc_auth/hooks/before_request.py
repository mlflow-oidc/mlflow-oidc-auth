from typing import Any, Callable, Dict, Optional

from flask import render_template, request, session, redirect, url_for
from mlflow.protos.model_registry_pb2 import (
    CreateModelVersion,
    CreateRegisteredModel,
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
    SearchRegisteredModels,
    SetModelVersionTag,
    SetRegisteredModelAlias,
    SetRegisteredModelTag,
    TransitionModelVersionStage,
    UpdateModelVersion,
    UpdateRegisteredModel,
)
from mlflow.protos.service_pb2 import (
    CreateExperiment,
    CreateRun,
    DeleteExperiment,
    DeleteRun,
    DeleteTag,
    GetExperiment,
    GetExperimentByName,
    GetMetricHistory,
    GetRun,
    ListArtifacts,
    LogBatch,
    LogMetric,
    LogModel,
    LogParam,
    RestoreExperiment,
    RestoreRun,
    SearchExperiments,
    SetExperimentTag,
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
    validate_can_delete_registered_model,
    validate_can_delete_run,
    validate_can_delete_user,
    validate_can_manage_experiment,
    validate_can_manage_registered_model,
    validate_can_read_experiment,
    validate_can_read_experiment_artifact_proxy,
    validate_can_read_experiment_by_name,
    validate_can_read_registered_model,
    validate_can_read_run,
    validate_can_update_experiment,
    validate_can_update_experiment_artifact_proxy,
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


BEFORE_REQUEST_VALIDATORS = {
    (http_path, method): handler
    for http_path, handler, methods in get_endpoints(_get_before_request_handler)
    for method in methods
}

BEFORE_REQUEST_VALIDATORS.update(
    {
        (routes.GET_EXPERIMENT_PERMISSION, "GET"): validate_can_manage_experiment,
        (routes.CREATE_EXPERIMENT_PERMISSION, "GET"): validate_can_manage_experiment,
        (routes.CREATE_EXPERIMENT_PERMISSION, "POST"): validate_can_manage_experiment,
        (routes.UPDATE_EXPERIMENT_PERMISSION, "PATCH"): validate_can_manage_experiment,
        (routes.DELETE_EXPERIMENT_PERMISSION, "DELETE"): validate_can_manage_experiment,
        (routes.GET_REGISTERED_MODEL_PERMISSION, "GET"): validate_can_manage_registered_model,
        (routes.CREATE_REGISTERED_MODEL_PERMISSION, "POST"): validate_can_manage_registered_model,
        (routes.UPDATE_REGISTERED_MODEL_PERMISSION, "PATCH"): validate_can_manage_registered_model,
        (routes.DELETE_REGISTERED_MODEL_PERMISSION, "DELETE"): validate_can_manage_registered_model,
        # (SIGNUP, "GET"): validate_can_create_user,
        # (routes.GET_USER, "GET"): validate_can_read_user,
        (routes.CREATE_USER, "POST"): validate_can_create_user,
        (routes.UPDATE_USER_PASSWORD, "PATCH"): validate_can_update_user_password,
        (routes.UPDATE_USER_ADMIN, "PATCH"): validate_can_update_user_admin,
        (routes.DELETE_USER, "DELETE"): validate_can_delete_user,
    }
)


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

            if config.ENABLE_AUTOMATIC_LOGIN_REDIRECT:
                return redirect(url_for("login", _external=True))
            return render_template(
                "auth.html",
                username=None,
                provide_display_name=config.OIDC_PROVIDER_DISPLAY_NAME,
            )
    # admins don't need to be authorized
    if get_is_admin():
        return
    # authorization
    if validator := BEFORE_REQUEST_VALIDATORS.get((request.path, request.method)):
        if not validator():
            return responses.make_forbidden_response()
    elif _is_proxy_artifact_path(request.path):
        if validator := _get_proxy_artifact_validator(request.method, request.view_args):
            if not validator():
                return responses.make_forbidden_response()
