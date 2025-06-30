from flask import Response, request
from mlflow.protos.model_registry_pb2 import CreateRegisteredModel, DeleteRegisteredModel, RenameRegisteredModel, SearchRegisteredModels
from mlflow.protos.service_pb2 import CreateExperiment, SearchExperiments, SearchLoggedModels
from mlflow.server.handlers import _get_request_message, catch_mlflow_exception, get_endpoints
from mlflow.utils.proto_json_utils import message_to_json, parse_dict
from mlflow.utils.search_utils import SearchUtils

from mlflow_oidc_auth.permissions import MANAGE
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import (
    fetch_readable_experiments,
    fetch_readable_logged_models,
    fetch_readable_registered_models,
    get_is_admin,
    get_model_name,
    get_username,
)


def _set_can_manage_experiment_permission(resp: Response):
    response_message = CreateExperiment.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    experiment_id = response_message.experiment_id
    username = get_username()
    store.create_experiment_permission(experiment_id, username, MANAGE.name)


def _set_can_manage_registered_model_permission(resp: Response):
    response_message = CreateRegisteredModel.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    name = response_message.registered_model.name
    username = get_username()
    store.create_registered_model_permission(name, username, MANAGE.name)


def _delete_can_manage_registered_model_permission(resp: Response):
    """
    Delete registered model permission when the model is deleted.

    We need to do this because the primary key of the registered model is the name,
    unlike the experiment where the primary key is experiment_id (UUID). Therefore,
    we have to delete the permission record when the model is deleted otherwise it
    conflicts with the new model registered with the same name.
    """
    # Get model name from request context because it's not available in the response
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


def _filter_search_logged_models(resp: Response) -> None:
    """
    Filter out unreadable logged models from the search results.
    """
    if get_is_admin():
        return

    response_message = SearchLoggedModels.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    request_message = _get_request_message(SearchLoggedModels())

    # Get current user
    username = get_username()

    # Get all readable logged models with the original parameters
    readable_models = fetch_readable_logged_models(
        experiment_ids=list(request_message.experiment_ids),
        filter_string=request_message.filter or None,
        order_by=(
            [
                {
                    "field_name": ob.field_name,
                    "ascending": ob.ascending,
                    "dataset_name": ob.dataset_name,
                    "dataset_digest": ob.dataset_digest,
                }
                for ob in request_message.order_by
            ]
            if request_message.order_by
            else None
        ),
        username=username,
    )

    # Convert to proto format and apply max_results limit
    readable_models_proto = [model.to_proto() for model in readable_models[: request_message.max_results]]

    # Update response with filtered models
    response_message.ClearField("models")
    response_message.models.extend(readable_models_proto)

    # Handle pagination token
    if len(readable_models) > request_message.max_results:
        # Set next page token if there are more results
        from mlflow.utils.search_utils import SearchLoggedModelsPaginationToken as Token

        params = {
            "experiment_ids": list(request_message.experiment_ids),
            "filter_string": request_message.filter or None,
            "order_by": (
                [
                    {
                        "field_name": ob.field_name,
                        "ascending": ob.ascending,
                        "dataset_name": ob.dataset_name,
                        "dataset_digest": ob.dataset_digest,
                    }
                    for ob in request_message.order_by
                ]
                if request_message.order_by
                else None
            ),
        }
        response_message.next_page_token = Token(offset=request_message.max_results, **params).encode()
    else:
        # Clear next page token if all results fit
        response_message.next_page_token = ""

    resp.data = message_to_json(response_message)


def _rename_registered_model_permission(resp: Response):
    """
    A model registry can be assigned to multiple users or groups with different permissions.
    Changing the model registry name must be propagated to all users or groups.
    """
    data = request.get_json(force=True, silent=True)
    name = data.get("name") if data else None
    new_name = data.get("new_name") if data else None
    if not name or not new_name:
        raise ValueError("Both 'name' and 'new_name' must be provided in the request data.")
    store.rename_registered_model_permissions(name, new_name)
    store.rename_group_model_permissions(name, new_name)


AFTER_REQUEST_PATH_HANDLERS = {
    CreateExperiment: _set_can_manage_experiment_permission,
    CreateRegisteredModel: _set_can_manage_registered_model_permission,
    DeleteRegisteredModel: _delete_can_manage_registered_model_permission,
    SearchExperiments: _filter_search_experiments,
    SearchLoggedModels: _filter_search_logged_models,
    SearchRegisteredModels: _filter_search_registered_models,
    RenameRegisteredModel: _rename_registered_model_permission,
}

AFTER_REQUEST_HANDLERS = {
    (http_path, method): handler
    for http_path, handler, methods in get_endpoints(_get_after_request_handler)
    for method in methods
    if handler is not None and "/graphql" not in http_path
}


@catch_mlflow_exception
def after_request_hook(resp: Response):
    if 400 <= resp.status_code < 600:
        return resp

    if handler := AFTER_REQUEST_HANDLERS.get((request.path, request.method)):
        handler(resp)
    return resp
