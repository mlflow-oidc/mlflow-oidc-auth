from flask import Response, request
from mlflow.entities import Experiment
from mlflow.entities.model_registry import RegisteredModel
from mlflow.protos.model_registry_pb2 import CreateRegisteredModel, DeleteRegisteredModel, SearchRegisteredModels
from mlflow.protos.service_pb2 import CreateExperiment, SearchExperiments
from mlflow.server.handlers import (
    _get_model_registry_store,
    _get_request_message,
    _get_tracking_store,
    catch_mlflow_exception,
    get_endpoints,
)
from mlflow.store.entities.paged_list import PagedList
from mlflow.utils.proto_json_utils import message_to_json, parse_dict
from mlflow.utils.search_utils import SearchUtils

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.permissions import MANAGE
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import (
    can_read_experiment,
    can_read_registered_model,
    get_is_admin,
    get_username,
    get_model_name,
    fetch_registered_models_paginated,
    fetch_readable_registered_models,
    fetch_readable_experiments,
    get_user_groups,
)


def _set_initial_experiment_permission(resp: Response):
    response_message = CreateExperiment.Response()
    parse_dict(resp.json, response_message)
    experiment_id = response_message.experiment_id
    username = get_username()
    store.create_experiment_permission(experiment_id, username, MANAGE.name)
    user_groups = get_user_groups(username)
    if permission := config.DEFAULT_MLFLOW_GROUP_PERMISSION:
        for group_name in user_groups:
            store.create_group_experiment_permission(group_name, experiment_id, permission)


def _set_initial_registered_model_permission(resp: Response):
    response_message = CreateRegisteredModel.Response()
    parse_dict(resp.json, response_message)
    model_name = response_message.registered_model.name
    username = get_username()
    store.create_registered_model_permission(model_name, username, MANAGE.name)
    user_groups = get_user_groups(username)
    if permission := config.DEFAULT_MLFLOW_GROUP_PERMISSION:
        for group_name in user_groups:
            store.create_group_model_permission(group_name, model_name, permission)


# TODO: Should a _delete_experiment_permission be added?


def _delete_registered_model_permission(resp: Response):
    """
    Delete registered model permission when the model is deleted.

    We need to do this because the primary key of the registered model is the name,
    unlike the experiment where the primary key is experiment_id (UUID). Therefore,
    we have to delete the permission record when the model is deleted otherwise it
    conflicts with the new model registered with the same name.
    """
    model_name = get_model_name()
    store.wipe_group_model_permissions(model_name)
    store.wipe_registered_model_permissions(model_name)


def _get_after_request_handler(request_class):
    return AFTER_REQUEST_PATH_HANDLERS.get(request_class)


def _filter_search_experiments(resp: Response):
    if get_is_admin():
        return

    response_message = SearchExperiments.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    request_message = _get_request_message(SearchExperiments())

    # Get current user
    username = get_username()

    # Get all readable experiments with the original filter and order
    readable_experiments = fetch_readable_experiments(
        view_type=request_message.view_type, order_by=request_message.order_by, filter_string=request_message.filter, username=username
    )

    # Convert to proto format and apply max_results limit
    readable_experiments_proto = [experiment.to_proto() for experiment in readable_experiments[: request_message.max_results]]

    # Update response with filtered experiments
    response_message.ClearField("experiments")
    response_message.experiments.extend(readable_experiments_proto)

    # Handle pagination token
    if len(readable_experiments) > request_message.max_results:
        # Set next page token if there are more results
        response_message.next_page_token = SearchUtils.create_page_token(request_message.max_results)
    else:
        # Clear next page token if all results fit
        response_message.next_page_token = ""

    resp.data = message_to_json(response_message)


def _filter_search_registered_models(resp: Response):
    if get_is_admin():
        return

    response_message = SearchRegisteredModels.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    request_message = _get_request_message(SearchRegisteredModels())

    # Get current user
    username = get_username()

    # Get all readable models with the original filter and order
    readable_models = fetch_readable_registered_models(filter_string=request_message.filter, order_by=request_message.order_by, username=username)

    # Convert to proto format and apply max_results limit
    readable_models_proto = [model.to_proto() for model in readable_models[: request_message.max_results]]

    # Update response with filtered models
    response_message.ClearField("registered_models")
    response_message.registered_models.extend(readable_models_proto)

    # Handle pagination token
    if len(readable_models) > request_message.max_results:
        # Set next page token if there are more results
        response_message.next_page_token = SearchUtils.create_page_token(request_message.max_results)
    else:
        # Clear next page token if all results fit
        response_message.next_page_token = ""

    resp.data = message_to_json(response_message)


AFTER_REQUEST_PATH_HANDLERS = {
    CreateExperiment: _set_initial_experiment_permission,
    CreateRegisteredModel: _set_initial_registered_model_permission,
    DeleteRegisteredModel: _delete_registered_model_permission,
    SearchExperiments: _filter_search_experiments,
    SearchRegisteredModels: _filter_search_registered_models,
}

AFTER_REQUEST_HANDLERS = {(http_path, method): handler for http_path, handler, methods in get_endpoints(_get_after_request_handler) for method in methods}


@catch_mlflow_exception
def after_request_hook(resp: Response):
    if 400 <= resp.status_code < 600:
        return resp

    if handler := AFTER_REQUEST_HANDLERS.get((request.path, request.method)):
        handler(resp)
    return resp
