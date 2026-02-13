from flask import Response, g, request
from mlflow.protos.model_registry_pb2 import CreateRegisteredModel, DeleteRegisteredModel, RenameRegisteredModel, SearchRegisteredModels
from mlflow.protos.service_pb2 import (
    CreateExperiment,
    CreateGatewayEndpoint,
    CreateGatewayModelDefinition,
    CreateGatewaySecret,
    DeleteGatewayEndpoint,
    DeleteGatewayModelDefinition,
    DeleteGatewaySecret,
    DeleteScorer,
    ListGatewayEndpoints,
    ListGatewayModelDefinitions,
    ListGatewaySecretInfos,
    RegisterScorer,
    SearchExperiments,
    SearchLoggedModels,
    UpdateGatewayEndpoint,
)
from mlflow.server.handlers import _get_model_registry_store, _get_request_message, _get_tracking_store, catch_mlflow_exception, get_endpoints
from mlflow.utils.proto_json_utils import message_to_json, parse_dict
from mlflow.utils.search_utils import SearchUtils

from mlflow_oidc_auth.bridge import get_fastapi_admin_status, get_fastapi_username
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import MANAGE
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import can_read_experiment, can_read_registered_model, get_model_name
from mlflow_oidc_auth.utils.permissions import can_read_gateway_endpoint, can_read_gateway_model_definition, can_read_gateway_secret


def _set_can_manage_experiment_permission(resp: Response):
    response_message = CreateExperiment.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    experiment_id = response_message.experiment_id
    username = get_fastapi_username()
    store.create_experiment_permission(experiment_id, username, MANAGE.name)


def _set_can_manage_registered_model_permission(resp: Response):
    response_message = CreateRegisteredModel.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    name = response_message.registered_model.name
    username = get_fastapi_username()
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


def _set_can_manage_gateway_endpoint_permission(resp: Response):
    """Create MANAGE gateway endpoint permission for the endpoint creator."""
    response_message = CreateGatewayEndpoint.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    name = response_message.endpoint.name
    username = get_fastapi_username()
    store.create_gateway_endpoint_permission(name, username, MANAGE.name)


def _rename_gateway_endpoint_permission(resp: Response):
    """Propagate endpoint name changes to all user and group permission records.

    The old name was stashed in ``flask.g`` by the before-request validator.
    The new name is read from the response.
    """
    old_name = getattr(g, "_updating_gateway_endpoint_old_name", None)
    if not old_name:
        return

    response_message = UpdateGatewayEndpoint.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    new_name = response_message.endpoint.name

    if not new_name or new_name == old_name:
        # Name unchanged — nothing to do.
        return

    try:
        store.rename_gateway_endpoint_permissions(old_name, new_name)
    except Exception:
        get_logger().warning(f"Failed to rename gateway endpoint permissions from '{old_name}' to '{new_name}'")


def _set_can_manage_gateway_secret_permission(resp: Response):
    """Create MANAGE gateway secret permission for the secret creator."""
    response_message = CreateGatewaySecret.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    secret_name = response_message.secret.secret_name
    username = get_fastapi_username()
    store.create_gateway_secret_permission(secret_name, username, MANAGE.name)


def _set_can_manage_gateway_model_definition_permission(resp: Response):
    """Create MANAGE gateway model definition permission for the model definition creator."""
    response_message = CreateGatewayModelDefinition.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    name = response_message.model_definition.name
    username = get_fastapi_username()
    store.create_gateway_model_definition_permission(name, username, MANAGE.name)


def _filter_list_gateway_endpoints(resp: Response) -> None:
    """Filter out gateway endpoints the user cannot read."""
    if get_fastapi_admin_status():
        return

    response_message = ListGatewayEndpoints.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    username = get_fastapi_username()
    logger = get_logger()

    for endpoint in list(response_message.endpoints):
        if not can_read_gateway_endpoint(endpoint.name, username):
            response_message.endpoints.remove(endpoint)
            logger.debug(f"Filtered gateway endpoint '{endpoint.name}' for user '{username}'")

    resp.data = message_to_json(response_message)


def _filter_list_gateway_secrets(resp: Response) -> None:
    """Filter out gateway secrets the user cannot read."""
    if get_fastapi_admin_status():
        return

    response_message = ListGatewaySecretInfos.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    username = get_fastapi_username()
    logger = get_logger()

    for secret in list(response_message.secrets):
        if not can_read_gateway_secret(secret.secret_name, username):
            response_message.secrets.remove(secret)
            logger.debug(f"Filtered gateway secret '{secret.secret_name}' for user '{username}'")

    resp.data = message_to_json(response_message)


def _filter_list_gateway_model_definitions(resp: Response) -> None:
    """Filter out gateway model definitions the user cannot read."""
    if get_fastapi_admin_status():
        return

    response_message = ListGatewayModelDefinitions.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    username = get_fastapi_username()
    logger = get_logger()

    for model_def in list(response_message.model_definitions):
        if not can_read_gateway_model_definition(model_def.name, username):
            response_message.model_definitions.remove(model_def)
            logger.debug(f"Filtered gateway model definition '{model_def.name}' for user '{username}'")

    resp.data = message_to_json(response_message)


def _delete_gateway_endpoint_permissions_cascade(resp: Response) -> None:
    """Delete all permissions for a gateway endpoint after it is deleted."""
    name = getattr(g, "_deleting_gateway_endpoint_name", None)
    if not name:
        return
    try:
        store.wipe_gateway_endpoint_permissions(name)
    except Exception:
        get_logger().warning(f"Failed to cascade-delete permissions for gateway endpoint '{name}'")


def _delete_gateway_secret_permissions_cascade(resp: Response) -> None:
    """Delete all permissions for a gateway secret after it is deleted."""
    name = getattr(g, "_deleting_gateway_secret_name", None)
    if not name:
        return
    try:
        store.wipe_gateway_secret_permissions(name)
    except Exception:
        get_logger().warning(f"Failed to cascade-delete permissions for gateway secret '{name}'")


def _delete_gateway_model_definition_permissions_cascade(resp: Response) -> None:
    """Delete all permissions for a gateway model definition after it is deleted."""
    name = getattr(g, "_deleting_gateway_model_definition_name", None)
    if not name:
        return
    try:
        store.wipe_gateway_model_definition_permissions(name)
    except Exception:
        get_logger().warning(f"Failed to cascade-delete permissions for gateway model definition '{name}'")


AFTER_REQUEST_PATH_HANDLERS = {
    CreateExperiment: _set_can_manage_experiment_permission,
    CreateRegisteredModel: _set_can_manage_registered_model_permission,
    DeleteRegisteredModel: _delete_can_manage_registered_model_permission,
    SearchExperiments: _filter_search_experiments,
    SearchLoggedModels: _filter_search_logged_models,
    SearchRegisteredModels: _filter_search_registered_models,
    RenameRegisteredModel: _rename_registered_model_permission,
    RegisterScorer: _set_can_manage_scorer_permission,
    DeleteScorer: _delete_scorer_permissions_cascade,
    CreateGatewayEndpoint: _set_can_manage_gateway_endpoint_permission,
    CreateGatewaySecret: _set_can_manage_gateway_secret_permission,
    CreateGatewayModelDefinition: _set_can_manage_gateway_model_definition_permission,
    UpdateGatewayEndpoint: _rename_gateway_endpoint_permission,
    DeleteGatewayEndpoint: _delete_gateway_endpoint_permissions_cascade,
    DeleteGatewaySecret: _delete_gateway_secret_permissions_cascade,
    DeleteGatewayModelDefinition: _delete_gateway_model_definition_permissions_cascade,
    ListGatewayEndpoints: _filter_list_gateway_endpoints,
    ListGatewaySecretInfos: _filter_list_gateway_secrets,
    ListGatewayModelDefinitions: _filter_list_gateway_model_definitions,
}

_our_handlers = set(AFTER_REQUEST_PATH_HANDLERS.values())
AFTER_REQUEST_HANDLERS = {
    (http_path, method): handler
    for http_path, handler, methods in get_endpoints(_get_after_request_handler)
    for method in methods
    if handler in _our_handlers and "/graphql" not in http_path
}


@catch_mlflow_exception
def after_request_hook(resp: Response):
    if 400 <= resp.status_code < 600:
        return resp

    if handler := AFTER_REQUEST_HANDLERS.get((request.path, request.method)):
        handler(resp)
    return resp
