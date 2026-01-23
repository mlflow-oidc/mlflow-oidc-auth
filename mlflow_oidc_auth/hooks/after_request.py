from flask import Response, request
from mlflow.protos.model_registry_pb2 import CreateRegisteredModel, DeleteRegisteredModel, RenameRegisteredModel, SearchRegisteredModels
from mlflow.protos.service_pb2 import CreateExperiment, DeleteScorer, RegisterScorer, SearchExperiments, SearchLoggedModels
from mlflow.server.handlers import _get_model_registry_store, _get_request_message, _get_tracking_store, catch_mlflow_exception, get_endpoints
from mlflow.utils.proto_json_utils import message_to_json, parse_dict
from mlflow.utils.search_utils import SearchUtils

from mlflow_oidc_auth.bridge import get_fastapi_admin_status, get_fastapi_username
from mlflow_oidc_auth.permissions import MANAGE
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import can_read_experiment, can_read_registered_model, get_model_name, get_user_groups


def _set_initial_experiment_permission(resp: Response):
    response_message = CreateExperiment.Response()
    parse_dict(resp.json, response_message)
    experiment_id = response_message.experiment_id
    username = get_fastapi_username()
    store.create_experiment_permission(experiment_id, username, MANAGE.name)
    user_groups = store.get_groups_for_user(username)
    if permission := config.DEFAULT_MLFLOW_GROUP_PERMISSION:
        for group_name in user_groups:
            store.create_group_experiment_permission(group_name, experiment_id, permission)


def _set_initial_registered_model_permission(resp: Response):
    response_message = CreateRegisteredModel.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    model_name = response_message.registered_model.name
    username = get_fastapi_username()
    store.create_registered_model_permission(model_name, username, MANAGE.name)
    user_groups = store.get_groups_for_user(username)
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
    if not model_name:
        return
    store.wipe_group_model_permissions(model_name)
    store.wipe_registered_model_permissions(model_name)


def _get_after_request_handler(request_class):
    return AFTER_REQUEST_PATH_HANDLERS.get(request_class)


def _filter_search_experiments(resp: Response):
    if get_fastapi_admin_status():
        return

    response_message = SearchExperiments.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    request_message = _get_request_message(SearchExperiments())

    username = get_fastapi_username()

    # Filter out unreadable experiments from the current response page.
    for e in list(response_message.experiments):
        if not can_read_experiment(e.experiment_id, username):
            response_message.experiments.remove(e)

    # Re-fetch to fill max_results, preserving MLflow pagination semantics.
    tracking_store = _get_tracking_store()
    while len(response_message.experiments) < request_message.max_results and response_message.next_page_token != "":
        refetched = tracking_store.search_experiments(
            view_type=request_message.view_type,
            max_results=request_message.max_results,
            order_by=request_message.order_by,
            filter_string=request_message.filter,
            page_token=response_message.next_page_token,
        )

        remaining = request_message.max_results - len(response_message.experiments)
        refetched = refetched[:remaining]
        if len(refetched) == 0:
            response_message.next_page_token = ""
            break

        readable_proto = [e.to_proto() for e in refetched if can_read_experiment(e.experiment_id, username)]
        response_message.experiments.extend(readable_proto)

        start_offset = SearchUtils.parse_start_offset_from_page_token(response_message.next_page_token)
        final_offset = start_offset + len(refetched)
        response_message.next_page_token = SearchUtils.create_page_token(final_offset)

    resp.data = message_to_json(response_message)


def _filter_search_registered_models(resp: Response):
    if get_fastapi_admin_status():
        return

    response_message = SearchRegisteredModels.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    request_message = _get_request_message(SearchRegisteredModels())

    username = get_fastapi_username()

    # Filter out unreadable models from the current response page.
    for rm in list(response_message.registered_models):
        if not can_read_registered_model(rm.name, username):
            response_message.registered_models.remove(rm)

    # Re-fetch to fill max_results, preserving MLflow pagination semantics.
    model_registry_store = _get_model_registry_store()
    while len(response_message.registered_models) < request_message.max_results and response_message.next_page_token != "":
        refetched = model_registry_store.search_registered_models(
            filter_string=request_message.filter,
            max_results=request_message.max_results,
            order_by=request_message.order_by,
            page_token=response_message.next_page_token,
        )
        remaining = request_message.max_results - len(response_message.registered_models)
        refetched = refetched[:remaining]
        if len(refetched) == 0:
            response_message.next_page_token = ""
            break

        readable_proto = [rm.to_proto() for rm in refetched if can_read_registered_model(rm.name, username)]
        response_message.registered_models.extend(readable_proto)

        start_offset = SearchUtils.parse_start_offset_from_page_token(response_message.next_page_token)
        final_offset = start_offset + len(refetched)
        response_message.next_page_token = SearchUtils.create_page_token(final_offset)

    resp.data = message_to_json(response_message)


def _filter_search_logged_models(resp: Response) -> None:
    """
    Filter out unreadable logged models from the search results.
    """
    if get_fastapi_admin_status():
        return

    response_message = SearchLoggedModels.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    request_message = _get_request_message(SearchLoggedModels())

    username = get_fastapi_username()

    # Remove unreadable models from the current response page.
    for m in list(response_message.models):
        if not can_read_experiment(m.info.experiment_id, username):
            response_message.models.remove(m)

    from mlflow.utils.search_utils import SearchLoggedModelsPaginationToken as Token

    max_results = request_message.max_results
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

    next_page_token = response_message.next_page_token or None
    tracking_store = _get_tracking_store()

    while len(response_message.models) < max_results and next_page_token is not None:
        batch = tracking_store.search_logged_models(max_results=max_results, page_token=next_page_token, **params)
        is_last_page = batch.token is None
        offset = Token.decode(next_page_token).offset if next_page_token else 0
        last_index = len(batch) - 1

        for index, model in enumerate(batch):
            if not can_read_experiment(model.experiment_id, username):
                continue

            response_message.models.append(model.to_proto())
            if len(response_message.models) >= max_results:
                next_page_token = None if is_last_page and index == last_index else Token(offset=offset + index + 1, **params).encode()
                break
        else:
            next_page_token = None if is_last_page else Token(offset=offset + max_results, **params).encode()

    response_message.next_page_token = next_page_token or ""
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
        # Defensive no-op: avoid turning a successful rename into a 500 in after_request.
        return
    store.rename_registered_model_permissions(name, new_name)
    store.rename_group_model_permissions(name, new_name)


def _set_can_manage_scorer_permission(resp: Response):
    """Create MANAGE scorer permission for the scorer creator."""

    response_message = RegisterScorer.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    experiment_id = response_message.experiment_id
    scorer_name = response_message.name
    username = get_fastapi_username()
    store.create_scorer_permission(experiment_id, scorer_name, username, MANAGE.name)


def _delete_scorer_permissions_cascade(resp: Response):
    """Delete all scorer permissions when a scorer is deleted."""

    data = request.get_json(force=True, silent=True) or {}
    experiment_id = data.get("experiment_id")
    scorer_name = data.get("name")
    if experiment_id and scorer_name:
        store.delete_scorer_permissions_for_scorer(str(experiment_id), str(scorer_name))


AFTER_REQUEST_PATH_HANDLERS = {
    CreateExperiment: _set_initial_experiment_permission,
    CreateRegisteredModel: _set_initial_registered_model_permission,
    DeleteRegisteredModel: _delete_registered_model_permission,
    SearchExperiments: _filter_search_experiments,
    SearchLoggedModels: _filter_search_logged_models,
    SearchRegisteredModels: _filter_search_registered_models,
    RenameRegisteredModel: _rename_registered_model_permission,
    RegisterScorer: _set_can_manage_scorer_permission,
    DeleteScorer: _delete_scorer_permissions_cascade,
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
