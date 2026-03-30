from flask import Response, g, request
from mlflow.protos.model_registry_pb2 import (
    CreateRegisteredModel,
    DeleteRegisteredModel,
    RenameRegisteredModel,
    SearchModelVersions,
    SearchRegisteredModels,
)
from mlflow.protos.service_pb2 import (
    CreateExperiment,
    CreateGatewayEndpoint,
    CreateGatewayModelDefinition,
    CreateGatewaySecret,
    CreateWorkspace,
    DeleteGatewayEndpoint,
    DeleteGatewayModelDefinition,
    DeleteGatewaySecret,
    DeleteScorer,
    DeleteWorkspace,
    ListGatewayEndpoints,
    ListGatewayModelDefinitions,
    ListGatewaySecretInfos,
    ListWorkspaces,
    RegisterScorer,
    SearchExperiments,
    SearchLoggedModels,
    UpdateGatewayEndpoint,
)
from mlflow.server.handlers import (
    _get_model_registry_store,
    _get_request_message,
    _get_tracking_store,
    catch_mlflow_exception,
    get_endpoints,
)
from mlflow.utils.proto_json_utils import message_to_json, parse_dict
from mlflow.utils.search_utils import SearchUtils

import json

from mlflow_oidc_auth.bridge import get_fastapi_admin_status, get_fastapi_username
from mlflow_oidc_auth.bridge.user import get_auth_context
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import MANAGE
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import (
    can_read_experiment,
    can_read_registered_model,
    get_model_name,
)
from mlflow_oidc_auth.utils.permissions import (
    can_read_gateway_endpoint,
    can_read_gateway_model_definition,
    can_read_gateway_secret,
)
from mlflow_oidc_auth.utils.workspace_cache import (
    flush_workspace_cache,
    get_workspace_permission_cached,
)

# ---------------------------------------------------------------------------
# Request-scoped permission cache
# ---------------------------------------------------------------------------
# During search-result filtering, the same permission may be checked many times
# (e.g. multiple model versions from the same registered model, or re-fetch
# loops). The global permission cache (30s TTL) already deduplicates DB
# lookups across requests, but a request-scoped dict avoids even the cache
# hash/lookup overhead for repeated checks within a single filter pass.
# ---------------------------------------------------------------------------


def _get_request_permission_cache() -> dict:
    """Return a dict scoped to the current Flask request via ``flask.g``.

    Each filter function uses this to memoize ``can_read_*`` results for the
    duration of a single after-request handler invocation.
    """
    cache = getattr(g, "_after_request_perm_cache", None)
    if cache is None:
        cache = {}
        g._after_request_perm_cache = cache
    return cache


def _cached_can_read_experiment(experiment_id: str, username: str) -> bool:
    """can_read_experiment with request-scoped memoization."""
    cache = _get_request_permission_cache()
    key = ("exp", experiment_id, username)
    if key not in cache:
        cache[key] = can_read_experiment(experiment_id, username)
    return cache[key]


def _cached_can_read_registered_model(model_name: str, username: str) -> bool:
    """can_read_registered_model with request-scoped memoization."""
    cache = _get_request_permission_cache()
    key = ("rm", model_name, username)
    if key not in cache:
        cache[key] = can_read_registered_model(model_name, username)
    return cache[key]


def _cached_can_read_gateway_endpoint(name: str, username: str) -> bool:
    """can_read_gateway_endpoint with request-scoped memoization."""
    cache = _get_request_permission_cache()
    key = ("gw_ep", name, username)
    if key not in cache:
        cache[key] = can_read_gateway_endpoint(name, username)
    return cache[key]


def _cached_can_read_gateway_secret(name: str, username: str) -> bool:
    """can_read_gateway_secret with request-scoped memoization."""
    cache = _get_request_permission_cache()
    key = ("gw_secret", name, username)
    if key not in cache:
        cache[key] = can_read_gateway_secret(name, username)
    return cache[key]


def _cached_can_read_gateway_model_definition(name: str, username: str) -> bool:
    """can_read_gateway_model_definition with request-scoped memoization."""
    cache = _get_request_permission_cache()
    key = ("gw_md", name, username)
    if key not in cache:
        cache[key] = can_read_gateway_model_definition(name, username)
    return cache[key]


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


def _can_access_workspace(username: str, workspace: str | None) -> bool:
    """Check if a user can access a resource in the given workspace.

    Returns True (allow) when:
    - Workspaces are disabled (MLFLOW_ENABLE_WORKSPACES is False)
    - Resource has no workspace assignment (pre-workspace-era, WSSEC-05)
    - User has at least READ workspace permission via get_workspace_permission_cached (WSSEC-01/02/03/04)
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return True
    if not workspace:
        return True  # Pre-workspace-era resource (WSSEC-05)
    perm = get_workspace_permission_cached(username, workspace)
    return perm is not None and perm.can_read


def _filter_search_experiments(resp: Response):
    if get_fastapi_admin_status():
        return

    response_message = SearchExperiments.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    request_message = _get_request_message(SearchExperiments())

    username = get_fastapi_username()

    # Filter out unreadable experiments from the current response page.
    for e in list(response_message.experiments):
        if not _cached_can_read_experiment(e.experiment_id, username):
            response_message.experiments.remove(e)

    # Filter by workspace permission (WSSEC-01)
    if config.MLFLOW_ENABLE_WORKSPACES:
        tracking_store = _get_tracking_store()
        ws_map = {}
        for e in list(response_message.experiments):
            try:
                ws_map[e.experiment_id] = tracking_store.get_experiment(e.experiment_id).workspace
            except Exception:
                ws_map[e.experiment_id] = None
        for e in list(response_message.experiments):
            if not _can_access_workspace(username, ws_map.get(e.experiment_id)):
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

        readable_proto = [
            e.to_proto() for e in refetched if _cached_can_read_experiment(e.experiment_id, username) and _can_access_workspace(username, e.workspace)
        ]
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
        if not _cached_can_read_registered_model(rm.name, username):
            response_message.registered_models.remove(rm)

    # Filter by workspace permission (WSSEC-02)
    if config.MLFLOW_ENABLE_WORKSPACES:
        model_registry_store_ws = _get_model_registry_store()
        ws_map = {}
        for rm in list(response_message.registered_models):
            try:
                ws_map[rm.name] = model_registry_store_ws.get_registered_model(rm.name).workspace
            except Exception:
                ws_map[rm.name] = None
        for rm in list(response_message.registered_models):
            if not _can_access_workspace(username, ws_map.get(rm.name)):
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

        readable_proto = [
            rm.to_proto() for rm in refetched if _cached_can_read_registered_model(rm.name, username) and _can_access_workspace(username, rm.workspace)
        ]
        response_message.registered_models.extend(readable_proto)

        start_offset = SearchUtils.parse_start_offset_from_page_token(response_message.next_page_token)
        final_offset = start_offset + len(refetched)
        response_message.next_page_token = SearchUtils.create_page_token(final_offset)

    resp.data = message_to_json(response_message)


def _filter_search_model_versions(resp: Response):
    """Filter out model versions belonging to registered models the user cannot read."""
    if get_fastapi_admin_status():
        return

    response_message = SearchModelVersions.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    request_message = _get_request_message(SearchModelVersions())

    username = get_fastapi_username()

    # Filter out unreadable model versions from the current response page.
    for mv in list(response_message.model_versions):
        if not _cached_can_read_registered_model(mv.name, username):
            response_message.model_versions.remove(mv)

    # Filter by workspace permission (WSSEC-02 — model versions inherit workspace from their model)
    if config.MLFLOW_ENABLE_WORKSPACES:
        model_registry_store_ws = _get_model_registry_store()
        ws_map: dict[str, str | None] = {}
        for mv in list(response_message.model_versions):
            if mv.name not in ws_map:
                try:
                    ws_map[mv.name] = model_registry_store_ws.get_registered_model(mv.name).workspace
                except Exception:
                    ws_map[mv.name] = None
            if not _can_access_workspace(username, ws_map.get(mv.name)):
                response_message.model_versions.remove(mv)

    # Re-fetch to fill max_results, preserving MLflow pagination semantics.
    model_registry_store = _get_model_registry_store()
    while len(response_message.model_versions) < request_message.max_results and response_message.next_page_token != "":
        refetched = model_registry_store.search_model_versions(
            filter_string=request_message.filter,
            max_results=request_message.max_results,
            order_by=request_message.order_by,
            page_token=response_message.next_page_token,
        )
        remaining = request_message.max_results - len(response_message.model_versions)
        refetched = refetched[:remaining]
        if len(refetched) == 0:
            response_message.next_page_token = ""
            break

        for mv in refetched:
            if _cached_can_read_registered_model(mv.name, username) and _can_access_workspace(username, getattr(mv, "workspace", None)):
                response_message.model_versions.append(mv.to_proto())

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
        if not _cached_can_read_experiment(m.info.experiment_id, username):
            response_message.models.remove(m)

    # Filter by workspace permission (WSSEC-03)
    exp_ws_map: dict[str, str | None] = {}
    if config.MLFLOW_ENABLE_WORKSPACES:
        tracking_store_ws = _get_tracking_store()
        for m in list(response_message.models):
            exp_id = m.info.experiment_id
            if exp_id not in exp_ws_map:
                try:
                    exp_ws_map[exp_id] = tracking_store_ws.get_experiment(exp_id).workspace
                except Exception:
                    exp_ws_map[exp_id] = None
        for m in list(response_message.models):
            if not _can_access_workspace(username, exp_ws_map.get(m.info.experiment_id)):
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
            if not _cached_can_read_experiment(model.experiment_id, username):
                continue

            # Workspace filtering for refetch path (WSSEC-03)
            if config.MLFLOW_ENABLE_WORKSPACES:
                exp_id = model.experiment_id
                if exp_id not in exp_ws_map:
                    try:
                        exp_ws_map[exp_id] = tracking_store.get_experiment(exp_id).workspace
                    except Exception:
                        exp_ws_map[exp_id] = None
                if not _can_access_workspace(username, exp_ws_map.get(exp_id)):
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
        get_logger().warning("Failed to rename gateway endpoint permissions")


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
        if not _cached_can_read_gateway_endpoint(endpoint.name, username):
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
        if not _cached_can_read_gateway_secret(secret.secret_name, username):
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
        if not _cached_can_read_gateway_model_definition(model_def.name, username):
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
        get_logger().warning("Failed to cascade-delete permissions for gateway endpoint")


def _delete_gateway_secret_permissions_cascade(resp: Response) -> None:
    """Delete all permissions for a gateway secret after it is deleted."""
    name = getattr(g, "_deleting_gateway_secret_name", None)
    if not name:
        return
    try:
        store.wipe_gateway_secret_permissions(name)
    except Exception:
        get_logger().warning("Failed to cascade-delete permissions for gateway secret")


def _delete_gateway_model_definition_permissions_cascade(resp: Response) -> None:
    """Delete all permissions for a gateway model definition after it is deleted."""
    name = getattr(g, "_deleting_gateway_model_definition_name", None)
    if not name:
        return
    try:
        store.wipe_gateway_model_definition_permissions(name)
    except Exception:
        get_logger().warning("Failed to cascade-delete permissions for gateway model definition")


def _auto_grant_workspace_manage_permission(resp: Response) -> None:
    """Create MANAGE workspace permission for the workspace creator.

    After a successful CreateWorkspace response, auto-grants MANAGE to the
    requesting user and flushes the workspace permission cache.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return
    if resp.status_code >= 300:
        return
    data = resp.get_json(silent=True)
    if not data:
        return
    workspace_name = None
    if isinstance(data.get("workspace"), dict):
        workspace_name = data["workspace"].get("name")
    if not workspace_name:
        return
    auth_context = get_auth_context()
    try:
        store.create_workspace_permission(workspace_name, auth_context.username, MANAGE.name)
    except Exception:
        get_logger().warning("Failed to auto-grant MANAGE on workspace for user")
    flush_workspace_cache()


def _cascade_delete_workspace_permissions(resp: Response) -> None:
    """Delete all permissions for a workspace after it is deleted.

    Reads the workspace name stashed by _find_validator in before_request.
    After a successful DeleteWorkspace response, wipes all user and group
    permissions for that workspace and flushes the cache.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return
    if resp.status_code >= 300:
        return
    name = getattr(g, "_deleting_workspace_name", None)
    if not name:
        return
    try:
        store.wipe_workspace_permissions(name)
    except Exception:
        get_logger().warning("Failed to cascade-delete permissions for workspace")
    flush_workspace_cache()


def _filter_list_workspaces(response: Response) -> None:
    """Filter ListWorkspaces response to only include workspaces user has permission for."""
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return
    if response.status_code != 200:
        return
    auth_context = get_auth_context()
    if auth_context.is_admin:
        return
    data = response.get_json(silent=True)
    if not data or "workspaces" not in data:
        return
    filtered = [
        ws for ws in data["workspaces"] if (perm := get_workspace_permission_cached(auth_context.username, ws.get("name", ""))) is not None and perm.can_read
    ]
    data["workspaces"] = filtered
    response.set_data(json.dumps(data))


AFTER_REQUEST_PATH_HANDLERS = {
    CreateExperiment: _set_can_manage_experiment_permission,
    CreateRegisteredModel: _set_can_manage_registered_model_permission,
    DeleteRegisteredModel: _delete_can_manage_registered_model_permission,
    SearchExperiments: _filter_search_experiments,
    SearchLoggedModels: _filter_search_logged_models,
    SearchRegisteredModels: _filter_search_registered_models,
    SearchModelVersions: _filter_search_model_versions,
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
    ListWorkspaces: _filter_list_workspaces,
    CreateWorkspace: _auto_grant_workspace_manage_permission,
    DeleteWorkspace: _cascade_delete_workspace_permissions,
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
