from typing import Any, Callable
from flask import Response, g, has_app_context, request
from mlflow.protos.model_registry_pb2 import (
    CreateRegisteredModel,
    DeleteRegisteredModel,
    RenameRegisteredModel,
    SearchModelVersions,
    SearchRegisteredModels,
)
from mlflow.protos.mlflow_artifacts_pb2 import ListArtifacts as ListArtifactsMlflowArtifacts
from mlflow.protos.review_queues_pb2 import ListReviewQueues
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
    ListScorers,
    ListWorkspaces,
    RegisterScorer,
    SearchEvaluationDatasets,
    SearchExperiments,
    SearchLoggedModels,
    UpdateGatewayEndpoint,
    UpdateGatewayModelDefinition,
)
from mlflow.server.handlers import (
    _get_ajax_path,
    _get_model_registry_store,
    _get_request_message,
    _get_tracking_store,
    catch_mlflow_exception,
    get_endpoints,
)
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST, ErrorCode
from mlflow.utils.proto_json_utils import message_to_json, parse_dict
from mlflow.entities.lifecycle_stage import LifecycleStage
from mlflow.utils.search_utils import SearchUtils
from mlflow.utils.workspace_utils import resolve_entity_workspace_name

import json

from mlflow_oidc_auth.bridge import get_fastapi_admin_status, get_fastapi_username
from mlflow_oidc_auth.bridge.user import get_auth_context
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.hooks.http_method import authorization_method
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import MANAGE
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import (
    can_read_experiment,
    can_read_registered_model,
    effective_scorer_permission,
    get_experiment_ids,
    get_model_name,
    get_request_param,
)
from mlflow_oidc_auth.utils.permissions import (
    can_read_gateway_endpoint,
    can_read_gateway_model_definition,
    can_read_gateway_secret,
)
from mlflow_oidc_auth.validators._experiment_scope import permission_on_all_experiments
from mlflow_oidc_auth.validators.experiment import get_active_artifact_experiments, is_artifact_root_listing
from mlflow_oidc_auth.validators.review import is_review_queue_member
from mlflow_oidc_auth.validators.scorers import scorer_has_versions
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

    Memoized for the current request. ``get_workspace_permission_cached`` caches grants and
    (since issue #456) denials; the memo additionally spares a shared-cache round trip per
    row. It uses the same request-scoped dict as the ``_cached_can_read_*`` helpers, so it
    adds no new staleness window (issue #253).
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return True
    if not workspace:
        return True  # Pre-workspace-era resource (WSSEC-05)

    def _lookup() -> bool:
        perm = get_workspace_permission_cached(username, workspace)
        return perm is not None and perm.can_read

    # The memo is an optimization, not a requirement: outside a Flask request context
    # (direct calls, tests) fall through to the uncached lookup rather than failing.
    if not has_app_context():
        return _lookup()
    cache = _get_request_permission_cache()
    key = ("ws", workspace, username)
    if key not in cache:
        cache[key] = _lookup()
    return cache[key]


def _top_up_page(
    rows: Any,
    max_results: int,
    page_token: str,
    fetch: Callable[[str], Any],
    keep: Callable[[Any], bool],
    decode_offset: Callable[[str], int] | None = None,
    encode_offset: Callable[[int], str] | None = None,
) -> str:
    """Fill a filtered page back up to ``max_results`` from the following offset-token pages.

    Each fetched batch is walked in full: a row the user cannot read is skipped, a readable
    one is appended, and as soon as the page is full the returned token points at the row
    right after the one that filled it. No fetched row is discarded unexamined, so no row is
    fetched twice (issue #456) — the earlier loop sliced the *unfiltered* batch to the free
    space before filtering and advanced the token by the slice, so the tail was re-fetched on
    the next iteration. Shared by every re-paging search filter.

    Parameters:
        rows: The page's repeated field (or list); readable rows are appended as protos.
        max_results: The page size the client asked for.
        page_token: The token for the next unfiltered page, ``""`` when there is none.
        fetch: Fetches the batch that starts at a token, at most ``max_results`` rows.
        keep: Whether the current user may see a fetched row. Only kept rows are appended.
        decode_offset: Reads the row offset a token starts at. Defaults to MLflow's
            ``SearchUtils`` offset token; logged models pass their own token codec.
        encode_offset: Builds the token for a row offset; pairs with ``decode_offset``.

    Returns:
        The token for the next page, or ``""`` when the result set is exhausted.
    """
    # Resolved per call, not as default arguments, so the codec is looked up when it is used.
    decode = decode_offset or SearchUtils.parse_start_offset_from_page_token
    encode = encode_offset or SearchUtils.create_page_token
    while len(rows) < max_results and page_token:
        batch = fetch(page_token)
        if len(batch) == 0:
            return ""
        offset = decode(page_token)
        # MLflow's PagedList carries ``token=None`` on the last page. Anything without the
        # attribute is not known to be the last page, so keep paging until an empty batch.
        is_last_page = hasattr(batch, "token") and batch.token is None
        last_index = len(batch) - 1
        for index, row in enumerate(batch):
            if not keep(row):
                continue
            rows.append(row.to_proto())
            if len(rows) >= max_results:
                return "" if is_last_page and index == last_index else encode(offset + index + 1)
        page_token = "" if is_last_page else encode(offset + len(batch))
    return page_token


def _search_scope_workspace() -> str:
    """Return the workspace the current request's search ran in.

    With workspaces enabled MLflow's stores scope every search to the request's active
    workspace: registered models and model versions by their ``workspace`` column, logged
    models through their experiment. Every row of every page — first page and top-up alike —
    lives there. Registered-model, model-version and logged-model protos carry no
    ``workspace`` field; this is what the matching entity's ``.workspace`` resolves to,
    without a per-row store lookup (issue #456). Never None, so a row is never mistaken for
    a pre-workspace-era resource and waved through.
    """
    return resolve_entity_workspace_name(None)


def _search_scope_denied(username: str) -> bool:
    """Whether workspaces are on and ``username`` cannot read the workspace the search ran in.

    One check covers a whole experiment, registry or logged-model search, both halves of the
    page: when it is denied, every row the search can ever return is denied with it.
    """
    return bool(config.MLFLOW_ENABLE_WORKSPACES) and not _can_access_workspace(username, _search_scope_workspace())


def _filter_search_experiments(resp: Response):
    if get_fastapi_admin_status():
        return

    response_message = SearchExperiments.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    request_message = _get_request_message(SearchExperiments())

    username = get_fastapi_username()

    # Filter by workspace permission (WSSEC-01). MLflow scopes an experiment search to the
    # request's workspace, so one check covers every row, on this page and any top-up page.
    if _search_scope_denied(username):
        del response_message.experiments[:]
        response_message.next_page_token = ""
        resp.data = message_to_json(response_message)
        return

    # Filter out unreadable experiments from the current response page.
    for e in list(response_message.experiments):
        if not _cached_can_read_experiment(e.experiment_id, username):
            response_message.experiments.remove(e)

    # Re-fetch to fill max_results, preserving MLflow pagination semantics.
    tracking_store = _get_tracking_store()
    response_message.next_page_token = _top_up_page(
        response_message.experiments,
        request_message.max_results,
        response_message.next_page_token,
        fetch=lambda token: tracking_store.search_experiments(
            view_type=request_message.view_type,
            max_results=request_message.max_results,
            order_by=request_message.order_by,
            filter_string=request_message.filter,
            page_token=token,
        ),
        keep=lambda e: _cached_can_read_experiment(e.experiment_id, username),
    )

    resp.data = message_to_json(response_message)


def _filter_search_registered_models(resp: Response):
    if get_fastapi_admin_status():
        return

    response_message = SearchRegisteredModels.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    request_message = _get_request_message(SearchRegisteredModels())

    username = get_fastapi_username()

    # Filter by workspace permission (WSSEC-02). Every row of the search, on this page and
    # on any top-up page, lives in the workspace it was scoped to, so one check covers all.
    if _search_scope_denied(username):
        del response_message.registered_models[:]
        response_message.next_page_token = ""
        resp.data = message_to_json(response_message)
        return

    # Filter out unreadable models from the current response page.
    for rm in list(response_message.registered_models):
        if not _cached_can_read_registered_model(rm.name, username):
            response_message.registered_models.remove(rm)

    # Re-fetch to fill max_results, preserving MLflow pagination semantics.
    model_registry_store = _get_model_registry_store()
    response_message.next_page_token = _top_up_page(
        response_message.registered_models,
        request_message.max_results,
        response_message.next_page_token,
        fetch=lambda token: model_registry_store.search_registered_models(
            filter_string=request_message.filter,
            max_results=request_message.max_results,
            order_by=request_message.order_by,
            page_token=token,
        ),
        keep=lambda rm: _cached_can_read_registered_model(rm.name, username),
    )

    resp.data = message_to_json(response_message)


def _filter_search_model_versions(resp: Response):
    """Filter out model versions belonging to registered models the user cannot read."""
    if get_fastapi_admin_status():
        return

    response_message = SearchModelVersions.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    request_message = _get_request_message(SearchModelVersions())

    username = get_fastapi_username()

    # Filter by workspace permission (WSSEC-02 — model versions inherit workspace from their
    # model). Every row of the search, on this page and on any top-up page, lives in the
    # workspace it was scoped to, so one check covers all; no row depends on a field of its own.
    if _search_scope_denied(username):
        del response_message.model_versions[:]
        response_message.next_page_token = ""
        resp.data = message_to_json(response_message)
        return

    # Filter out unreadable model versions from the current response page.
    for mv in list(response_message.model_versions):
        if not _cached_can_read_registered_model(mv.name, username):
            response_message.model_versions.remove(mv)

    # Re-fetch to fill max_results, preserving MLflow pagination semantics.
    model_registry_store = _get_model_registry_store()
    response_message.next_page_token = _top_up_page(
        response_message.model_versions,
        request_message.max_results,
        response_message.next_page_token,
        fetch=lambda token: model_registry_store.search_model_versions(
            filter_string=request_message.filter,
            max_results=request_message.max_results,
            order_by=request_message.order_by,
            page_token=token,
        ),
        keep=lambda mv: _cached_can_read_registered_model(mv.name, username),
    )

    resp.data = message_to_json(response_message)


def _search_logged_models_needs_no_filtering(payload: Any, username: str) -> bool:
    """Report whether the already-decoded response body can be passed through untouched.

    Rewriting the body costs a `parse_dict` into protobuf plus a full re-serialisation
    at the end of the filter, and a page of logged models carries every metric value of
    every model on it, so together those two steps cost more than the tracking server
    spent producing the body in the first place. When no model has to be removed, and
    the tracking server reported no further page to top the current one up from, the
    body it produced is already the correct answer.

    Answering from the raw JSON keeps that check cheap. This returns True only when
    every model has been positively confirmed visible; anything unexpected in the
    payload returns False and leaves the filtering below to do its work.

    ``payload`` is ``resp.json`` decoded once by the caller — werkzeug does not cache
    ``Response.get_json``, and the body is large. The workspace has already been checked
    by the caller, once for the whole search.
    """
    if not isinstance(payload, dict):
        return False

    # A further page means the filter below may need to top this one up, and it can
    # only do that through the protobuf path.
    if payload.get("next_page_token"):
        return False

    models = payload.get("models")
    if models is None:
        return True
    if not isinstance(models, list):
        return False

    for model in models:
        if not isinstance(model, dict):
            return False
        info = model.get("info")
        if not isinstance(info, dict):
            return False
        experiment_id = info.get("experiment_id")
        if not isinstance(experiment_id, str):
            return False
        if not _cached_can_read_experiment(experiment_id, username):
            return False

    return True


def _filter_search_logged_models(resp: Response) -> None:
    """
    Filter out unreadable logged models from the search results.
    """
    if get_fastapi_admin_status():
        return

    username = get_fastapi_username()

    # Filter by workspace permission (WSSEC-03). MLflow scopes a logged-model search to the
    # experiments of the request's workspace, so one check covers every row of every page.
    payload = resp.json
    if _search_scope_denied(username):
        response_message = SearchLoggedModels.Response()  # type: ignore
        parse_dict(payload, response_message)
        del response_message.models[:]
        response_message.next_page_token = ""
        resp.data = message_to_json(response_message)
        return

    if _search_logged_models_needs_no_filtering(payload, username):
        return

    response_message = SearchLoggedModels.Response()  # type: ignore
    parse_dict(payload, response_message)
    request_message = _get_request_message(SearchLoggedModels())

    # Remove unreadable models from the current response page.
    for m in list(response_message.models):
        if not _cached_can_read_experiment(m.info.experiment_id, username):
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

    tracking_store = _get_tracking_store()
    response_message.next_page_token = _top_up_page(
        response_message.models,
        max_results,
        response_message.next_page_token,
        fetch=lambda token: tracking_store.search_logged_models(max_results=max_results, page_token=token, **params),
        keep=lambda model: _cached_can_read_experiment(model.experiment_id, username),
        decode_offset=lambda token: Token.decode(token).offset,
        encode_offset=lambda offset: Token(offset=offset, **params).encode(),
    )
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
    # Each rename raises RESOURCE_DOES_NOT_EXIST when it has no grants to move; the model may have
    # user grants and no group grants in this workspace or the reverse, so neither may skip the other.
    for rename in (store.rename_registered_model_permissions, store.rename_group_model_permissions):
        try:
            rename(name, new_name)
        except MlflowException as e:
            if e.error_code != ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
                raise


def _set_can_manage_scorer_permission(resp: Response):
    """Create MANAGE scorer permission for the scorer creator.

    ``RegisterScorer`` on an existing (experiment_id, name) appends a new version — that is how
    the UI edits a judge or guardrail scorer. Only version 1 is a creation; a later version is
    an update and must neither grant MANAGE to the caller nor fail on the creator's existing
    grant (issue #453).
    """

    response_message = RegisterScorer.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    if response_message.version != 1:
        return
    experiment_id = response_message.experiment_id
    scorer_name = response_message.name
    username = get_fastapi_username()
    try:
        store.create_scorer_permission(experiment_id, scorer_name, username, MANAGE.name)
    except MlflowException as e:
        if e.error_code != ErrorCode.Name(RESOURCE_ALREADY_EXISTS):
            raise
        # A grant set on the name before this scorer existed stays at the level it was given;
        # the registration does not raise it.
        get_logger().warning("Scorer created over an existing grant for its creator; keeping that grant")


def _delete_scorer_permissions_cascade(resp: Response):
    """Delete all scorer permissions once a scorer has no version left.

    ``DeleteScorer`` with a ``version`` removes only that version and the scorer stays, so
    its grants — denials included — must stay with it. They go when the last version does,
    whether by a delete of every version or of the last one, so a later registration of
    the name starts clean (issue #453). Only the pair MLflow acted on is considered: it
    was resolved in the request's workspace, so "no version left" means deleted there,
    not merely out of view.
    """

    experiment_id = get_request_param("experiment_id")
    scorer_name = get_request_param("name")
    if not scorer_has_versions(experiment_id, scorer_name):
        store.delete_scorer_permissions_for_scorer(str(experiment_id), str(scorer_name))


def _set_can_manage_gateway_endpoint_permission(resp: Response):
    """Create MANAGE gateway endpoint permission for the endpoint creator."""
    response_message = CreateGatewayEndpoint.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    name = response_message.endpoint.name
    username = get_fastapi_username()
    store.grant_creator_gateway_endpoint_permission(name, username)


def _rename_gateway_resource_permissions(resp: Response, *, old_name_attr: str, ids_attr: str, response_class, response_field: str, rename) -> None:
    """Move a renamed gateway resource's user and group permissions to its new name.

    The before-request hook stashes the current name in ``flask.g`` (it is resolved from the
    resource id); the new name is read from MLflow's response.

    Parameters:
        resp: MLflow's successful update response.
        old_name_attr: The ``flask.g`` attribute holding the stashed name.
        ids_attr: The ``flask.g`` attribute holding the ids of the rows to move, recorded with the name.
        response_class: The update message whose ``Response`` to parse.
        response_field: The response field holding the updated resource.
        rename: The store method moving the permissions, called as ``rename(old_name, new_name, ids)``.
    """
    old_name = getattr(g, old_name_attr, None)
    if not old_name:
        return

    response_message = response_class.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    new_name = getattr(response_message, response_field).name

    if not new_name or new_name == old_name:
        return

    try:
        rename(old_name, new_name, getattr(g, ids_attr, None))
    except Exception as exc:
        # MLflow has already committed the rename; the permissions stayed on the old name.
        get_logger().error("Failed to move permissions of a renamed gateway %s (%s)", response_field.replace("_", " "), type(exc).__name__)


def _rename_gateway_endpoint_permission(resp: Response):
    """Propagate endpoint name changes to all user and group permission records."""
    _rename_gateway_resource_permissions(
        resp,
        old_name_attr="_updating_gateway_endpoint_old_name",
        ids_attr="_updating_gateway_endpoint_permission_ids",
        response_class=UpdateGatewayEndpoint,
        response_field="endpoint",
        rename=store.rename_gateway_endpoint_permissions,
    )


def _set_can_manage_gateway_secret_permission(resp: Response):
    """Create MANAGE gateway secret permission for the secret creator."""
    response_message = CreateGatewaySecret.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    secret_name = response_message.secret.secret_name
    username = get_fastapi_username()
    store.grant_creator_gateway_secret_permission(secret_name, username)


def _set_can_manage_gateway_model_definition_permission(resp: Response):
    """Create MANAGE gateway model definition permission for the model definition creator."""
    response_message = CreateGatewayModelDefinition.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    name = response_message.model_definition.name
    username = get_fastapi_username()
    store.grant_creator_gateway_model_definition_permission(name, username)


def _can_read_listed_scorer(experiment_id: str, scorer_name: str, username: str) -> bool:
    """Whether a ``ListScorers`` row is visible to ``username``.

    READ on the scorer's experiment is always required. A grant on the scorer itself then
    decides: READ or better keeps the row, ``NO_PERMISSIONS`` hides it. A scorer with no grant
    of its own follows its experiment. Any lookup error hides the row.
    """
    try:
        if not _cached_can_read_experiment(experiment_id, username):
            return False
        return bool(effective_scorer_permission(experiment_id=experiment_id, scorer_name=scorer_name, user=username).permission.can_read)
    except Exception:
        get_logger().debug("Scorer permission lookup failed while filtering ListScorers")
        return False


def _filter_list_scorers(resp: Response) -> None:
    """Remove the scorers the caller cannot read from a ``ListScorers`` response.

    Applies to both forms of the request: with an ``experiment_id`` (already gated on READ
    for that experiment, so this removes scorers hidden by a ``NO_PERMISSIONS`` grant on the
    scorer) and without one, where MLflow lists the scorers of every active experiment.
    """
    if get_fastapi_admin_status():
        return

    response_message = ListScorers.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    username = get_fastapi_username()

    for scorer in list(response_message.scorers):
        if not _can_read_listed_scorer(str(scorer.experiment_id), scorer.scorer_name, username):
            response_message.scorers.remove(scorer)

    resp.data = message_to_json(response_message)


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


def _rename_gateway_model_definition_permission(resp: Response):
    """Propagate model definition name changes to all user and group permission records."""
    _rename_gateway_resource_permissions(
        resp,
        old_name_attr="_updating_gateway_model_definition_old_name",
        ids_attr="_updating_gateway_model_definition_permission_ids",
        response_class=UpdateGatewayModelDefinition,
        response_field="model_definition",
        rename=store.rename_gateway_model_definition_permissions,
    )


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


def _filter_search_evaluation_datasets(resp: Response) -> None:
    """Drop evaluation datasets linked to any experiment the caller cannot read.

    ``before_request`` already requires READ on every experiment the search is scoped to, but
    a dataset can be linked to more experiments than the one it was found through. Reading
    it by id requires READ on all of them, so the search shows exactly the datasets a
    ``GET datasets/<id>`` would serve. A dataset linked to no experiment is admin-only.
    """
    if get_fastapi_admin_status():
        return
    data = resp.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("datasets"), list):
        return
    from mlflow_oidc_auth.validators.dataset import dataset_experiment_ids

    username = get_fastapi_username()

    def _readable(dataset: Any) -> bool:
        if not isinstance(dataset, dict) or not dataset.get("dataset_id"):
            return False
        # MLflow serializes a dataset's links only when they were loaded, which a search
        # does not do, so resolve them from the store.
        experiment_ids = dataset_experiment_ids(str(dataset["dataset_id"]))
        return bool(experiment_ids) and all(_cached_can_read_experiment(e, username) for e in experiment_ids)

    data["datasets"] = [d for d in data["datasets"] if _readable(d)]
    resp.set_data(json.dumps(data))


def _filter_list_artifact_root(resp: Response) -> None:
    """Trim an artifact-ROOT listing to the experiments the caller can READ (issue #289).

    ``GET /mlflow-artifacts/artifacts`` with no ``path`` (or ``.``, ``%2e``, ``./``,
    ``workspaces/<ws>`` ...) lists the artifact root, which holds one directory per
    experiment across every tenant. It used to be served whole, enumerating every
    experiment id. Listing the root is legitimate, so rather than deny it outright the
    listing keeps only entries that:

    * name, in canonical form, an experiment that exists and is ACTIVE (the same
      canonical-id and exact-match rules as the path check, fetched in one batched store
      lookup) — a stray directory, a ``0<id>`` alias, a garbage-collected experiment's
      leftovers and a soft-deleted experiment are not browsable from the root,
    * the caller can READ, and
    * with workspaces enabled, belongs to the workspace being listed — the one a
      ``workspaces/<ws>`` path names, otherwise the request workspace — and one the
      caller can read, mirroring the search filters.

    A listing that is not of a root (``path=12/run/artifacts``) is left alone: its
    entries are file names, and ``before_request`` has already required READ on it.
    """
    if get_fastapi_admin_status():
        return
    roots = is_artifact_root_listing()
    if roots is None:
        return
    data = resp.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        return

    username = get_fastapi_username()
    workspaces_enabled = bool(config.MLFLOW_ENABLE_WORKSPACES)
    allowed_workspaces: set = set()
    if workspaces_enabled:
        from mlflow.utils.workspace_utils import DEFAULT_WORKSPACE_NAME

        from mlflow_oidc_auth.bridge.user import get_request_workspace

        request_workspace = get_request_workspace() or DEFAULT_WORKSPACE_NAME
        allowed_workspaces = {workspace or request_workspace for workspace in roots}

    # One batched store lookup for every candidate, not one per listed directory.
    names = [entry.get("path") if isinstance(entry, dict) else None for entry in data["files"]]
    active = get_active_artifact_experiments(name for name in names if isinstance(name, str))

    def _visible(entry: Any) -> bool:
        name = entry.get("path") if isinstance(entry, dict) else None
        experiment = active.get(name) if isinstance(name, str) else None
        if experiment is None or getattr(experiment, "lifecycle_stage", None) != LifecycleStage.ACTIVE:
            return False
        if not _cached_can_read_experiment(name, username):
            return False
        if workspaces_enabled:
            from mlflow.utils.workspace_utils import DEFAULT_WORKSPACE_NAME

            workspace = getattr(experiment, "workspace", None) or DEFAULT_WORKSPACE_NAME
            if workspace not in allowed_workspaces or not _can_access_workspace(username, workspace):
                return False
        return True

    data["files"] = [entry for entry in data["files"] if _visible(entry)]
    resp.set_data(json.dumps(data))


def _redact_gateway_secrets_config(resp: Response) -> None:
    """Reduce the gateway secrets-config response to what a non-admin needs (issue #366).

    MLflow's handler returns two server-wide flags and no per-secret data::

        {"secrets_available": true, "using_default_passphrase": <bool>}

    ``secrets_available`` gates MLflow's gateway page: when it is not true the page shows
    only its setup guide, so it must pass through or the page stays blank.
    ``using_default_passphrase`` says whether stored gateway secrets are encrypted under
    MLflow's well-known default KEK passphrase. MLflow's UI never reads it, and to anyone
    other than an operator it is a statement of how weakly the secrets are protected, so
    it is removed. Admins receive the response unchanged.

    There is nothing per-secret to filter here: which secrets a user can see is decided by
    ``ListGatewaySecretInfos`` (``_filter_list_gateway_secrets``) and ``GetGatewaySecretInfo``.
    A body that is not a JSON object is replaced with ``secrets_available: false`` rather
    than passed through.
    """
    if get_fastapi_admin_status():
        return
    data = resp.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    # Rebuilt from an allowlist, not stripped by denylist: a field a future MLflow release
    # adds is withheld from non-admins until it has been reviewed here.
    resp.set_data(json.dumps({"secrets_available": data.get("secrets_available") is True}))


def _filter_list_review_queues(resp: Response) -> None:
    """Narrow a ``ListReviewQueues`` response to the queues the caller may see.

    Admins and callers with EDIT (or MANAGE) on the experiment see every queue; opening
    one is gated separately in before_request. Anyone else, who holds READ, sees only the
    queues they are assigned to. Matches MLflow's own auth plugin.

    Parameters:
        resp: The response from MLflow's ``ListReviewQueues`` handler.
    """
    if get_fastapi_admin_status():
        return

    username = get_fastapi_username()
    # before_request already required READ on every experiment the request names.
    if permission_on_all_experiments(get_experiment_ids(), username).can_update:
        return

    response_message = ListReviewQueues.Response()  # type: ignore
    parse_dict(resp.json, response_message)
    visible = [queue for queue in response_message.review_queues if is_review_queue_member(queue, username)]
    response_message.ClearField("review_queues")
    response_message.review_queues.extend(visible)
    resp.data = message_to_json(response_message)


GATEWAY_SECRETS_CONFIG_PATH = _get_ajax_path("/mlflow/gateway/secrets/config", version=3)


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
    ListScorers: _filter_list_scorers,
    CreateGatewayEndpoint: _set_can_manage_gateway_endpoint_permission,
    CreateGatewaySecret: _set_can_manage_gateway_secret_permission,
    CreateGatewayModelDefinition: _set_can_manage_gateway_model_definition_permission,
    UpdateGatewayEndpoint: _rename_gateway_endpoint_permission,
    UpdateGatewayModelDefinition: _rename_gateway_model_definition_permission,
    DeleteGatewayEndpoint: _delete_gateway_endpoint_permissions_cascade,
    DeleteGatewaySecret: _delete_gateway_secret_permissions_cascade,
    DeleteGatewayModelDefinition: _delete_gateway_model_definition_permissions_cascade,
    ListGatewayEndpoints: _filter_list_gateway_endpoints,
    ListGatewaySecretInfos: _filter_list_gateway_secrets,
    ListGatewayModelDefinitions: _filter_list_gateway_model_definitions,
    ListWorkspaces: _filter_list_workspaces,
    SearchEvaluationDatasets: _filter_search_evaluation_datasets,
    ListArtifactsMlflowArtifacts: _filter_list_artifact_root,
    ListReviewQueues: _filter_list_review_queues,
    CreateWorkspace: _auto_grant_workspace_manage_permission,
    DeleteWorkspace: _cascade_delete_workspace_permissions,
}

# Create endpoints whose after-request handler auto-grants the creator MANAGE via a
# get_user lookup. If the authenticated user has no permission-DB record yet, that grant
# fails *after* MLflow has already committed the resource, leaving it ownerless (issue #262).
# before_request uses this set to reject such creates pre-commit. Derived from the handler
# map so a newly added create type is covered automatically.
CREATOR_GRANT_HANDLERS = frozenset(
    {
        _set_can_manage_experiment_permission,
        _set_can_manage_registered_model_permission,
        _set_can_manage_scorer_permission,
        _set_can_manage_gateway_endpoint_permission,
        _set_can_manage_gateway_secret_permission,
        _set_can_manage_gateway_model_definition_permission,
        _auto_grant_workspace_manage_permission,
    }
)
CREATOR_GRANT_REQUEST_CLASSES = frozenset(proto for proto, handler in AFTER_REQUEST_PATH_HANDLERS.items() if handler in CREATOR_GRANT_HANDLERS)

_our_handlers = set(AFTER_REQUEST_PATH_HANDLERS.values())
AFTER_REQUEST_HANDLERS = {
    (http_path, method): handler
    for http_path, handler, methods in get_endpoints(_get_after_request_handler)
    for method in methods
    if handler in _our_handlers and "/graphql" not in http_path
}
# Non-proto Flask route, so get_endpoints() above cannot map it; bound by exact path.
AFTER_REQUEST_HANDLERS[(GATEWAY_SECRETS_CONFIG_PATH, "GET")] = _redact_gateway_secrets_config


@catch_mlflow_exception
def after_request_hook(resp: Response):
    if 400 <= resp.status_code < 600:
        return resp

    # HEAD is folded onto GET (issue #286). werkzeug dispatches HEAD to the GET view and
    # then strips the body, but it PRESERVES Content-Length. The handlers registered here
    # filter search/list responses down to what the caller may see, so a HEAD that skipped
    # them was served the unfiltered global result set and leaked its exact size — the
    # existence/size oracle #286 is about. Folding the lookup in before_request alone only
    # closed the authorization half; without this the response half stayed open.
    method = authorization_method(request.method)
    if handler := AFTER_REQUEST_HANDLERS.get((request.path, method)):
        handler(resp)
    return resp
