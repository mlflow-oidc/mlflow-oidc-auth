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
    message_to_json,
)
from mlflow.store.entities.paged_list import PagedList
from mlflow.utils.proto_json_utils import parse_dict
from mlflow.utils.search_utils import SearchUtils

from mlflow_oidc_auth.app import config
from mlflow_oidc_auth.permissions import MANAGE, get_permission
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import get_is_admin, get_request_param, get_username, get_user_groups


def _set_can_manage_experiment_permission(resp: Response):
    response_message = CreateExperiment.Response()
    parse_dict(resp.json, response_message)
    experiment_id = response_message.experiment_id
    username = get_username()
    store.create_experiment_permission(experiment_id, username, MANAGE.name)
    user_groups = get_user_groups()
    if permission := config.DEFAULT_MLFLOW_GROUP_PERMISSION:
        for group_name in user_groups:
            store.create_group_experiment_permission(group_name, experiment_id, permission)


def _set_can_manage_registered_model_permission(resp: Response):
    response_message = CreateRegisteredModel.Response()
    parse_dict(resp.json, response_message)
    model_name = response_message.registered_model.name
    username = get_username()
    store.create_registered_model_permission(model_name, username, MANAGE.name)
    user_groups = get_user_groups()
    if permission := config.DEFAULT_MLFLOW_GROUP_PERMISSION:
        for group_name in user_groups:
            store.create_group_model_permission(group_name, model_name, permission)



def _delete_can_manage_registered_model_permission(resp: Response):
    """
    Delete registered model permission when the model is deleted.

    We need to do this because the primary key of the registered model is the name,
    unlike the experiment where the primary key is experiment_id (UUID). Therefore,
    we have to delete the permission record when the model is deleted otherwise it
    conflicts with the new model registered with the same name.
    """
    # Get model name from request context because it's not available in the response
    model_name = get_request_param("name")
    username = get_request_param("user_name")
    store.delete_registered_model_permission(model_name, username)


def _get_after_request_handler(request_class):
    return AFTER_REQUEST_PATH_HANDLERS.get(request_class)


def _filter_search_experiments(resp: Response):
    if get_is_admin():
        return

    response_message = SearchExperiments.Response()
    parse_dict(resp.json, response_message)

    # fetch permissions
    username = get_username()
    perms = store.list_experiment_permissions(username)
    perms_group = store.list_user_groups_experiment_permissions(username)
    can_read = {p.experiment_id: get_permission(p.permission).can_read for p in perms_group}
    can_read.update({p.experiment_id: get_permission(p.permission).can_read for p in perms})
    default_can_read = get_permission(config.DEFAULT_MLFLOW_PERMISSION).can_read

    # filter out unreadable
    for e in list(response_message.experiments):
        if not can_read.get(e.experiment_id, default_can_read):
            response_message.experiments.remove(e)

    # re-fetch to fill max results
    request_message = _get_request_message(SearchExperiments())
    while len(response_message.experiments) < request_message.max_results and response_message.next_page_token != "":
        refetched: PagedList[Experiment] = _get_tracking_store().search_experiments(
            view_type=request_message.view_type,
            max_results=request_message.max_results,
            order_by=request_message.order_by,
            filter_string=request_message.filter,
            page_token=response_message.next_page_token,
        )
        refetched = refetched[: request_message.max_results - len(response_message.experiments)]
        if len(refetched) == 0:
            response_message.next_page_token = ""
            break

        refetched_readable_proto = [e.to_proto() for e in refetched if can_read.get(e.experiment_id, default_can_read)]
        response_message.experiments.extend(refetched_readable_proto)

        # recalculate next page token
        start_offset = SearchUtils.parse_start_offset_from_page_token(response_message.next_page_token)
        final_offset = start_offset + len(refetched)
        response_message.next_page_token = SearchUtils.create_page_token(final_offset)

    resp.data = message_to_json(response_message)


def _filter_search_registered_models(resp: Response):
    if get_is_admin():
        return

    response_message = SearchRegisteredModels.Response()
    parse_dict(resp.json, response_message)

    # fetch permissions
    username = get_username()
    perms = store.list_registered_model_permissions(username)
    perms_group = store.list_user_groups_registered_model_permissions(username)
    can_read = {p.name: get_permission(p.permission).can_read for p in perms_group}
    can_read.update({p.name: get_permission(p.permission).can_read for p in perms})
    default_can_read = get_permission(config.DEFAULT_MLFLOW_PERMISSION).can_read

    # filter out unreadable
    for rm in list(response_message.registered_models):
        if not can_read.get(rm.name, default_can_read):
            response_message.registered_models.remove(rm)

    # re-fetch to fill max results
    request_message = _get_request_message(SearchRegisteredModels())
    while len(response_message.registered_models) < request_message.max_results and response_message.next_page_token != "":
        refetched: PagedList[RegisteredModel] = _get_model_registry_store().search_registered_models(
            filter_string=request_message.filter,
            max_results=request_message.max_results,
            order_by=request_message.order_by,
            page_token=response_message.next_page_token,
        )
        refetched = refetched[: request_message.max_results - len(response_message.registered_models)]
        if len(refetched) == 0:
            response_message.next_page_token = ""
            break

        refetched_readable_proto = [rm.to_proto() for rm in refetched if can_read.get(rm.name, default_can_read)]
        response_message.registered_models.extend(refetched_readable_proto)

        # recalculate next page token
        start_offset = SearchUtils.parse_start_offset_from_page_token(response_message.next_page_token)
        final_offset = start_offset + len(refetched)
        response_message.next_page_token = SearchUtils.create_page_token(final_offset)

    resp.data = message_to_json(response_message)


AFTER_REQUEST_PATH_HANDLERS = {
    CreateExperiment: _set_can_manage_experiment_permission,
    CreateRegisteredModel: _set_can_manage_registered_model_permission,
    DeleteRegisteredModel: _delete_can_manage_registered_model_permission,
    SearchExperiments: _filter_search_experiments,
    SearchRegisteredModels: _filter_search_registered_models,
}

AFTER_REQUEST_HANDLERS = {
    (http_path, method): handler
    for http_path, handler, methods in get_endpoints(_get_after_request_handler)
    for method in methods
}


@catch_mlflow_exception
def after_request_hook(resp: Response):
    if 400 <= resp.status_code < 600:
        return resp

    if handler := AFTER_REQUEST_HANDLERS.get((request.path, request.method)):
        handler(resp)
    return resp
