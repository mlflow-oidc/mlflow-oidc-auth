"""
Permissions router for FastAPI application.

This router handles permission management endpoints for experiments, models, and users.
"""

from typing import Any, Callable, List, Tuple

from fastapi import APIRouter, Body, Depends, Path
from fastapi.exceptions import HTTPException
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import (
    INVALID_PARAMETER_VALUE,
    RESOURCE_ALREADY_EXISTS,
    RESOURCE_DOES_NOT_EXIST,
)
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.dependencies import (
    check_admin_permission,
    check_experiment_manage_permission,
    check_registered_model_manage_permission,
)
from mlflow_oidc_auth.audit import emit_audit_event
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import (
    ExperimentPermission,
    ExperimentPermissionRecord,
    ExperimentPermissionResponse,
    ExperimentPermissionSummary,
    ExperimentRegexCreate,
    ExperimentRegexPermission,
    GatewayPermission,
    GatewayRegexCreate,
    MessageResponse,
    NamedPermissionSummary,
    PromptPermission,
    PromptPermissionResponse,
    PromptRegexCreate,
    PromptRegexPermissionResponse,
    RegisteredModelPermission,
    RegisteredModelPermissionRecord,
    RegisteredModelPermissionResponse,
    RegisteredModelRegexCreate,
    RegisteredModelRegexPermissionRecord,
    RegisteredModelRegexPermissionResponse,
    ScorerPermission,
    ScorerPermissionRecord,
    ScorerPermissionResponse,
    ScorerRegexCreate,
    ScorerRegexPermissionRecord,
    ScorerRegexPermissionResponse,
    StatusMessageResponse,
    StatusOnlyResponse,
    UserGatewayRegexPermissionItem,
)
from mlflow_oidc_auth.permissions import NO_PERMISSIONS
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import (
    effective_experiment_permission,
    fetch_all_gateway_endpoints,
    fetch_all_gateway_model_definitions,
    fetch_all_gateway_secrets,
    fetch_all_prompts,
    fetch_all_registered_models,
    get_is_admin,
    get_username,
)
from mlflow_oidc_auth.utils.batch_permissions import (
    batch_resolve_experiment_permissions,
    batch_resolve_model_permissions,
    batch_resolve_prompt_permissions,
)
from mlflow_oidc_auth.utils.permissions import (
    effective_gateway_endpoint_permission,
    effective_gateway_model_definition_permission,
    effective_gateway_secret_permission,
)

from ._permission_routes import ADMIN, CALLER, SCORER_KEYS, USER, Failure, Route, add_route, exact_routes, pattern_fields, regex_names, regex_routes
from ._prefix import USER_PERMISSIONS_ROUTER_PREFIX
from mlflow_oidc_auth.utils.grant_workspace import pattern_workspace_of

logger = get_logger()

USER_EXPERIMENT_PERMISSION = "/{username}/experiments"
USER_EXPERIMENT_PERMISSION_DETAIL = "/{username}/experiments/{experiment_id}"
USER_EXPERIMENT_PATTERN_PERMISSIONS = "/{username}/experiment-patterns"
USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL = "/{username}/experiment-patterns/{id}"

USER_REGISTERED_MODEL_PERMISSIONS = "/{username}/registered-models"
USER_REGISTERED_MODEL_PERMISSION_DETAIL = "/{username}/registered-models/{name:path}"
USER_REGISTERED_MODEL_PATTERN_PERMISSIONS = "/{username}/registered-models-patterns"
USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL = "/{username}/registered-models-patterns/{id}"

USER_PROMPT_PERMISSIONS = "/{username}/prompts"
USER_PROMPT_PERMISSION_DETAIL = "/{username}/prompts/{name:path}"
USER_PROMPT_PATTERN_PERMISSIONS = "/{username}/prompts-patterns"
USER_PROMPT_PATTERN_PERMISSION_DETAIL = "/{username}/prompts-patterns/{id}"

USER_SCORER_PERMISSIONS = "/{username}/scorers"
USER_SCORER_PERMISSION_DETAIL = "/{username}/scorers/{experiment_id}/{scorer_name:path}"
USER_SCORER_PATTERN_PERMISSIONS = "/{username}/scorer-patterns"
USER_SCORER_PATTERN_PERMISSION_DETAIL = "/{username}/scorer-patterns/{id}"

USER_GATEWAY_ENDPOINT_PERMISSIONS = "/{username}/gateways/endpoints"
USER_GATEWAY_ENDPOINT_PERMISSION_DETAIL = "/{username}/gateways/endpoints/{name:path}"
USER_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS = "/{username}/gateways/endpoints-patterns"
USER_GATEWAY_ENDPOINT_PATTERN_PERMISSION_DETAIL = "/{username}/gateways/endpoints-patterns/{id}"

USER_GATEWAY_MODEL_DEFINITION_PERMISSIONS = "/{username}/gateways/model-definitions"
USER_GATEWAY_MODEL_DEFINITION_PERMISSION_DETAIL = "/{username}/gateways/model-definitions/{name:path}"
USER_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSIONS = "/{username}/gateways/model-definitions-patterns"
USER_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSION_DETAIL = "/{username}/gateways/model-definitions-patterns/{id}"

USER_GATEWAY_SECRET_PERMISSIONS = "/{username}/gateways/secrets"
USER_GATEWAY_SECRET_PERMISSION_DETAIL = "/{username}/gateways/secrets/{name:path}"
USER_GATEWAY_SECRET_PATTERN_PERMISSIONS = "/{username}/gateways/secrets-patterns"
USER_GATEWAY_SECRET_PATTERN_PERMISSION_DETAIL = "/{username}/gateways/secrets-patterns/{id}"

user_permissions_router = APIRouter(
    prefix=USER_PERMISSIONS_ROUTER_PREFIX,
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
    },
)


@user_permissions_router.get(
    USER_EXPERIMENT_PERMISSION,
    response_model=List[ExperimentPermissionSummary],
    summary="Get experiment permissions for a user",
    description="Retrieves a list of experiments with permission information for the specified user.",
    tags=["user experiment permissions"],
)
async def get_user_experiment_permissions(
    username: str = Path(..., description="The username to get permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[ExperimentPermissionSummary]:
    """
    Retrieve a list of experiments with permission information for a user.

    This endpoint returns experiments that are accessible to the specified user,
    filtered based on the requesting user's permissions. If the requesting user
    is an admin, all experiments are returned. If requesting their own permissions,
    users see all experiments they have access to. Otherwise, only experiments the
    current user can manage are shown.

    Parameters:
    -----------
    username : str
        The username to get experiment permissions for.
    request : Request
        The FastAPI request object.

    Returns:
    --------
    List[ExperimentPermissionSummary]
        A list of experiments with permission information.

    Raises:
    -------
    HTTPException
        If the user is not found or the requesting user lacks sufficient permissions.
    """
    tracking_store = _get_tracking_store()
    all_experiments = tracking_store.search_experiments()

    # Batch resolve permissions for all experiments (fixed number of DB queries)
    experiment_permissions = batch_resolve_experiment_permissions(username, all_experiments)

    # Determine which experiments to include based on permissions
    if is_admin:
        # Admins can see all experiments
        list_experiments = all_experiments
    elif current_username == username:
        # Users can see their own accessible experiments (filter using pre-computed permissions)
        list_experiments = [exp for exp in all_experiments if experiment_permissions[exp.experiment_id].permission.name != NO_PERMISSIONS.name]
    else:
        # For other users, only show experiments the current user can manage
        current_user_permissions = batch_resolve_experiment_permissions(current_username, all_experiments)
        list_experiments = [exp for exp in all_experiments if current_user_permissions[exp.experiment_id].permission.can_manage]

    # Format experiment information with permissions (reuse pre-computed permissions)
    return [
        ExperimentPermissionSummary(
            name=exp.name,
            id=exp.experiment_id,
            permission=experiment_permissions[exp.experiment_id].permission.name,
            kind=experiment_permissions[exp.experiment_id].kind,
        )
        for exp in list_experiments
    ]


exact_routes(
    user_permissions_router,
    USER,
    "experiment",
    "user experiment permissions",
    USER_EXPERIMENT_PERMISSION_DETAIL,
    keys=(("experiment_id", "The experiment ID to {purpose} permissions for"),),
    auth=(("current_username", check_experiment_manage_permission),),
    body=ExperimentPermission,
    call={
        "create": lambda a: store.create_experiment_permission(a.experiment_id, a.username, a.permission_data.permission),
        "get": lambda a: store.get_experiment_permission(a.experiment_id, a.username),
        "update": lambda a: store.update_experiment_permission(a.experiment_id, a.username, a.permission_data.permission),
        "delete": lambda a: store.delete_experiment_permission(a.experiment_id, a.username),
    },
    models={"get": ExperimentPermissionResponse},
    respond={"get": lambda a, ep: ExperimentPermissionResponse(experiment_permission=ExperimentPermissionRecord(**ep.to_json()))},
    message_model=MessageResponse,
    messages={
        "create": "Experiment permission has been created.",
        "update": "Experiment permission has been changed.",
        "delete": "Experiment permission has been deleted.",
    },
    created=None,
    handled=False,
    text={
        "create": {
            "description": "Creates a permission for a user to access a specific experiment.",
            "subject": "The username to grant permissions to",
            "body": "The permission level to grant",
        },
        "get": {"subject": "The username to grant permissions to", "experiment_id": "The experiment ID to set permissions for"},
        "update": {
            "subject": "The username to grant permissions to",
            "experiment_id": "The experiment ID to set permissions for",
            "body": "The permission level to grant",
        },
        "delete": {"subject": "The username to revoke permissions from", "experiment_id": "The experiment ID to revoke permissions for"},
    },
)

regex_routes(
    user_permissions_router,
    USER,
    "experiment",
    "user experiment pattern permissions",
    USER_EXPERIMENT_PATTERN_PERMISSIONS,
    USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    ops=("create", "list", "get", "update", "delete"),
    names={"list": "list_user_experiment_pattern_permissions"},
    id_type=str,
    lab="",
    body=ExperimentRegexCreate,
    item=lambda p: ExperimentRegexPermission(id=str(p.id), regex=p.regex, priority=p.priority, permission=p.permission, workspace=pattern_workspace_of(p)),
    item_model=ExperimentRegexPermission,
    call={
        "list": lambda a: store.list_experiment_regex_permissions(username=a.username),
        "create": lambda a: store.create_experiment_regex_permission(**pattern_fields(a), username=a.username),
        "get": lambda a: store.get_experiment_regex_permission(a.username, int(a.id)),
        "update": lambda a: store.update_experiment_regex_permission(id=int(a.id), **pattern_fields(a), username=a.username),
        "delete": lambda a: store.delete_experiment_regex_permission(a.username, int(a.id)),
    },
    text={"create": {"summary": "Create experiment pattern permission"}},
)


@user_permissions_router.get(
    USER_PROMPT_PERMISSIONS,
    response_model=List[NamedPermissionSummary],
    summary="List prompt permissions for a user",
    description="Retrieves a list of prompts with permission information for the specified user.",
    tags=["user prompt permissions"],
)
async def get_user_prompts(
    username: str = Path(..., description="The username to get prompt permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[NamedPermissionSummary]:
    """
    List prompt permissions for a user.

    This endpoint returns prompts that are accessible to the specified user,
    filtered based on the requesting user's permissions.

    Parameters:
    -----------
    username : str
        The username to get prompt permissions for.
    request : Request
        The FastAPI request object.

    Returns:
    --------
    JSONResponse
        A list of prompts with permission information.

    Raises:
    -------
    HTTPException
        If there's an error retrieving the permissions.
    """
    # Get all prompts and filter based on permissions
    prompts = fetch_all_prompts()

    # Batch resolve permissions for all prompts (fixed number of DB queries)
    prompt_permissions = batch_resolve_prompt_permissions(username, prompts)

    if is_admin:
        list_prompts = prompts
    elif current_username == username:
        list_prompts = [prompt for prompt in prompts if prompt_permissions[prompt.name].permission.name != "NO_PERMISSIONS"]
    else:
        current_user_permissions = batch_resolve_prompt_permissions(current_username, prompts)
        list_prompts = [prompt for prompt in prompts if current_user_permissions[prompt.name].permission.can_manage]

    # Format prompt information with permissions (reuse pre-computed permissions)
    return [
        NamedPermissionSummary(
            name=prompt.name,
            permission=prompt_permissions[prompt.name].permission.name,
            kind=prompt_permissions[prompt.name].kind,
        )
        for prompt in list_prompts
    ]


exact_routes(
    user_permissions_router,
    USER,
    "prompt",
    "user prompt permissions",
    USER_PROMPT_PERMISSION_DETAIL,
    keys=(("name", "The prompt name to {purpose} permissions for"),),
    auth=(("current_username", check_registered_model_manage_permission),),
    body=PromptPermission,
    call={
        "create": lambda a: store.create_registered_model_permission(name=a.name, username=a.username, permission=a.permission_data.permission),
        "get": lambda a: store.get_registered_model_permission(a.name, a.username),
        "update": lambda a: store.update_registered_model_permission(name=a.name, username=a.username, permission=a.permission_data.permission),
        "delete": lambda a: store.delete_registered_model_permission(a.name, a.username),
    },
    models={"get": PromptPermissionResponse},
    respond={"get": lambda a, rmp: PromptPermissionResponse(prompt_permission=RegisteredModelPermissionRecord(**rmp.to_json()))},
    conflicts=True,
)

regex_routes(
    user_permissions_router,
    USER,
    "prompt",
    "user prompt pattern permissions",
    USER_PROMPT_PATTERN_PERMISSIONS,
    USER_PROMPT_PATTERN_PERMISSION_DETAIL,
    names={**regex_names("user_prompt"), "list": "get_user_prompt_pattern_permissions"},
    id_type=str,
    quiet_delete=True,
    body=PromptRegexCreate,
    item=lambda r: RegisteredModelRegexPermissionRecord(**r.to_json()),
    item_model=RegisteredModelRegexPermissionRecord,
    models={"get": PromptRegexPermissionResponse, "update": PromptRegexPermissionResponse},
    respond={
        op: lambda a, rm: PromptRegexPermissionResponse(prompt_permission=RegisteredModelRegexPermissionRecord(**rm.to_json())) for op in ("get", "update")
    },
    call={
        "list": lambda a: store.list_prompt_regex_permissions(username=a.username),
        "create": lambda a: store.create_prompt_regex_permission(**pattern_fields(a), username=a.username),
        "get": lambda a: store.get_prompt_regex_permission(id=int(a.id), username=a.username),
        "update": lambda a: store.update_prompt_regex_permission(id=int(a.id), **pattern_fields(a), username=a.username),
        "delete": lambda a: store.delete_prompt_regex_permission(id=int(a.id), username=a.username),
    },
)


@user_permissions_router.get(
    USER_REGISTERED_MODEL_PERMISSIONS,
    response_model=List[NamedPermissionSummary],
    summary="List registered model permissions for a user",
    description="Retrieves a list of registered models with permission information for the specified user.",
    tags=["user registered model permissions"],
)
async def get_user_registered_models(
    username: str = Path(..., description="The username to get registered model permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[NamedPermissionSummary]:
    """
    List registered model permissions for a user.

    This endpoint returns registered models that are accessible to the specified user,
    filtered based on the requesting user's permissions.

    Parameters:
    -----------
    request : Request
        The FastAPI request object.
    username : str
        The username to get registered model permissions for.

    Returns:
    --------
    JSONResponse
        A list of registered models with permission information.
    """

    # Get all registered models and filter based on permissions
    models = fetch_all_registered_models()

    # Batch resolve permissions for all models (fixed number of DB queries)
    model_permissions = batch_resolve_model_permissions(username, models)

    if is_admin:
        list_models = models
    elif current_username == username:
        list_models = [model for model in models if model_permissions[model.name].permission.name != "NO_PERMISSIONS"]
    else:
        current_user_permissions = batch_resolve_model_permissions(current_username, models)
        list_models = [model for model in models if current_user_permissions[model.name].permission.can_manage]

    # Format model information with permissions (reuse pre-computed permissions)
    return [
        NamedPermissionSummary(
            name=model.name,
            permission=model_permissions[model.name].permission.name,
            kind=model_permissions[model.name].kind,
        )
        for model in list_models
    ]


exact_routes(
    user_permissions_router,
    USER,
    "registered model",
    "user registered model permissions",
    USER_REGISTERED_MODEL_PERMISSION_DETAIL,
    keys=(("name", "The registered model name to {purpose} permissions for"),),
    auth=(("current_username", check_registered_model_manage_permission),),
    body=RegisteredModelPermission,
    call={
        "create": lambda a: store.create_registered_model_permission(name=a.name, username=a.username, permission=a.permission_data.permission),
        "get": lambda a: store.get_registered_model_permission(a.name, a.username),
        "update": lambda a: store.update_registered_model_permission(name=a.name, username=a.username, permission=a.permission_data.permission),
        "delete": lambda a: store.delete_registered_model_permission(a.name, a.username),
    },
    models={"get": RegisteredModelPermissionResponse},
    respond={"get": lambda a, rmp: RegisteredModelPermissionResponse(registered_model_permission=RegisteredModelPermissionRecord(**rmp.to_json()))},
    conflicts=True,
)


@user_permissions_router.get(
    USER_SCORER_PERMISSIONS,
    response_model=List[ScorerPermissionRecord],
    summary="List scorer permissions for a user",
    description="Retrieves a list of scorers with permission information for the specified user.",
    tags=["user scorer permissions"],
)
async def get_user_scorer_permissions(
    username: str = Path(..., description="The username to get scorer permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[ScorerPermissionRecord]:
    """List scorer permissions for a user.

    Admins can see all scorer permissions for any user. Users can see their own.
    For other users, only include scorers in experiments the current user can manage.
    """
    try:
        perms = store.list_scorer_permissions(username=username)
        if is_admin or current_username == username:
            filtered = perms
        else:
            filtered = [sp for sp in perms if effective_experiment_permission(sp.experiment_id, current_username).permission.can_manage]
        return [ScorerPermissionRecord(**p.to_json()) for p in filtered]
    except Exception as e:
        logger.error(f"Error listing scorer permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve scorer permissions")


exact_routes(
    user_permissions_router,
    USER,
    "scorer",
    "user scorer permissions",
    USER_SCORER_PERMISSION_DETAIL,
    keys=SCORER_KEYS,
    auth=(("current_username", check_experiment_manage_permission),),
    body=ScorerPermission,
    call={
        "create": lambda a: store.create_scorer_permission(
            experiment_id=str(a.experiment_id), scorer_name=str(a.scorer_name), username=str(a.username), permission=str(a.permission_data.permission)
        ),
        "get": lambda a: store.get_scorer_permission(str(a.experiment_id), str(a.scorer_name), str(a.username)),
        "update": lambda a: store.update_scorer_permission(
            experiment_id=str(a.experiment_id), scorer_name=str(a.scorer_name), username=str(a.username), permission=str(a.permission_data.permission)
        ),
        "delete": lambda a: store.delete_scorer_permission(str(a.experiment_id), str(a.scorer_name), str(a.username)),
    },
    models={"create": ScorerPermissionResponse, "get": ScorerPermissionResponse},
    respond={op: lambda a, sp: ScorerPermissionResponse(scorer_permission=ScorerPermissionRecord(**sp.to_json())) for op in ("create", "get")},
    conflicts=True,
)

regex_routes(
    user_permissions_router,
    USER,
    "scorer",
    "user scorer pattern permissions",
    USER_SCORER_PATTERN_PERMISSIONS,
    USER_SCORER_PATTERN_PERMISSION_DETAIL,
    names={"list": "get_user_scorer_regex_permissions", "create": "create_user_scorer_regex_permission"},
    specific=("get", "update", "delete"),
    conflicts=True,
    body=ScorerRegexCreate,
    item=lambda p: ScorerRegexPermissionRecord(**p.to_json()),
    item_model=ScorerRegexPermissionRecord,
    models={op: ScorerRegexPermissionResponse for op in ("create", "get", "update")},
    respond={op: lambda a, perm: ScorerRegexPermissionResponse(pattern=ScorerRegexPermissionRecord(**perm.to_json())) for op in ("create", "get", "update")},
    call={
        "list": lambda a: store.list_scorer_regex_permissions(username=a.username),
        "create": lambda a: store.create_scorer_regex_permission(**pattern_fields(a), username=a.username),
        "get": lambda a: store.get_scorer_regex_permission(username=a.username, id=a.id),
        "update": lambda a: store.update_scorer_regex_permission(id=a.id, **pattern_fields(a), username=a.username),
        "delete": lambda a: store.delete_scorer_regex_permission(id=a.id, username=a.username),
    },
)


regex_routes(
    user_permissions_router,
    USER,
    "registered model",
    "user registered model pattern permissions",
    USER_REGISTERED_MODEL_PATTERN_PERMISSIONS,
    USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    names=regex_names("user_registered_model"),
    id_type=str,
    quiet_delete=True,
    body=RegisteredModelRegexCreate,
    item=lambda r: RegisteredModelRegexPermissionRecord(**r.to_json()),
    item_model=RegisteredModelRegexPermissionRecord,
    models={"get": RegisteredModelRegexPermissionResponse, "update": RegisteredModelRegexPermissionResponse},
    respond={
        op: lambda a, rm: RegisteredModelRegexPermissionResponse(registered_model_permission=RegisteredModelRegexPermissionRecord(**rm.to_json()))
        for op in ("get", "update")
    },
    call={
        "list": lambda a: store.list_registered_model_regex_permissions(username=a.username),
        "create": lambda a: store.create_registered_model_regex_permission(**pattern_fields(a), username=a.username),
        "get": lambda a: store.get_registered_model_regex_permission(id=int(a.id), username=a.username),
        "update": lambda a: store.update_registered_model_regex_permission(id=int(a.id), **pattern_fields(a), username=a.username),
        "delete": lambda a: store.delete_registered_model_regex_permission(id=int(a.id), username=a.username),
    },
)


# ========================================================================================
# GATEWAY ENDPOINT PERMISSIONS
# ========================================================================================


def _gateway_routes(
    label: str,
    id_attr: str,
    paths: Tuple[str, str, str, str],
    fetch: Callable[[], List[dict]],
    name_of: Callable[[dict], str],
    effective: Callable[[str, str], Any],
) -> None:
    """Add a user's routes for one gateway resource kind: the listing, exact grants and pattern grants.

    :param label: The kind as the texts name it, e.g. ``"gateway endpoint"``.
    :param id_attr: Attribute of a stored grant holding the resource name.
    :param paths: The listing, grant, pattern and pattern-detail paths.
    :param fetch: Lists the gateway resources.
    :param name_of: The name of one listed resource ("" to skip it).
    :param effective: Resolves a user's effective permission on a resource.
    """
    snake = label.replace(" ", "_")
    listing, detail, patterns, pattern_detail = paths

    def list_permissions(a) -> List[NamedPermissionSummary]:
        results: list[NamedPermissionSummary] = []
        for resource in fetch():
            resource_name = name_of(resource)
            if not resource_name:
                continue
            perm_result = effective(resource_name, a.username)
            if a.is_admin:
                listed = True
            elif a.current_username == a.username:
                listed = perm_result.permission.name != NO_PERMISSIONS.name
            else:
                listed = effective(resource_name, a.current_username).permission.can_manage
            if listed:
                results.append(NamedPermissionSummary(name=resource_name, permission=perm_result.permission.name, kind=perm_result.kind))
        return results

    add_route(
        user_permissions_router,
        Route(
            name=f"get_user_{snake}_permissions",
            op="list",
            path=listing,
            summary=f"List {label} permissions for a user",
            description=f"Retrieves a list of {label} permissions for the specified user.",
            tag=f"user {label} permissions",
            params=(("username", str, f"The username to get {label} permissions for"),),
            auth=CALLER,
            call=list_permissions,
            respond=lambda a, results: results,
            response_model=List[NamedPermissionSummary],
            failure=Failure(f"Error listing {label} permissions", 500, f"Failed to retrieve {label} permissions"),
        ),
    )
    exact_routes(
        user_permissions_router,
        USER,
        label,
        f"user {label} permissions",
        detail,
        keys=(("name", f"The {label} name to {{purpose}} permissions for"),),
        auth=ADMIN,
        body=GatewayPermission,
        call={
            "create": lambda a: getattr(store, f"create_{snake}_permission")(gateway_name=a.name, username=a.username, permission=a.permission_data.permission),
            "get": lambda a: getattr(store, f"get_{snake}_permission")(gateway_name=a.name, username=a.username),
            "update": lambda a: getattr(store, f"update_{snake}_permission")(gateway_name=a.name, username=a.username, permission=a.permission_data.permission),
            "delete": lambda a: getattr(store, f"delete_{snake}_permission")(gateway_name=a.name, username=a.username),
        },
        models={"create": NamedPermissionSummary, "get": NamedPermissionSummary},
        respond={op: lambda a, perm: NamedPermissionSummary(name=getattr(perm, id_attr), permission=perm.permission, kind="user") for op in ("create", "get")},
    )

    def item(p) -> UserGatewayRegexPermissionItem:
        return UserGatewayRegexPermissionItem(
            id=p.id, regex=p.regex, priority=p.priority, user_id=p.user_id, permission=p.permission, workspace=pattern_workspace_of(p)
        )

    regex_routes(
        user_permissions_router,
        USER,
        label,
        f"user {label} pattern permissions",
        patterns,
        pattern_detail,
        body=GatewayRegexCreate,
        item=item,
        item_model=UserGatewayRegexPermissionItem,
        models={"create": UserGatewayRegexPermissionItem, "update": UserGatewayRegexPermissionItem},
        respond={"create": lambda a, perm: item(perm), "update": lambda a, perm: item(perm)},
        call={
            "list": lambda a: getattr(store, f"list_{snake}_regex_permissions")(username=a.username),
            "create": lambda a: getattr(store, f"create_{snake}_regex_permission")(**pattern_fields(a), username=a.username),
            "get": lambda a: getattr(store, f"get_{snake}_regex_permission")(id=a.id, username=a.username),
            "update": lambda a: getattr(store, f"update_{snake}_regex_permission")(id=a.id, **pattern_fields(a), username=a.username),
            "delete": lambda a: getattr(store, f"delete_{snake}_regex_permission")(id=a.id, username=a.username),
        },
    )


_gateway_routes(
    "gateway endpoint",
    "endpoint_id",
    (
        USER_GATEWAY_ENDPOINT_PERMISSIONS,
        USER_GATEWAY_ENDPOINT_PERMISSION_DETAIL,
        USER_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS,
        USER_GATEWAY_ENDPOINT_PATTERN_PERMISSION_DETAIL,
    ),
    fetch=lambda: fetch_all_gateway_endpoints(),
    name_of=lambda ep: ep.get("name", ""),
    effective=lambda name, username: effective_gateway_endpoint_permission(name, username),
)


# ========================================================================================
# GATEWAY MODEL DEFINITION PERMISSIONS
# ========================================================================================


@user_permissions_router.get(
    USER_GATEWAY_MODEL_DEFINITION_PERMISSIONS,
    response_model=List[NamedPermissionSummary],
    summary="List gateway model definition permissions for a user",
    description="Retrieves a list of gateway model definition permissions for the specified user.",
    tags=["user gateway model definition permissions"],
)
async def get_user_gateway_model_definition_permissions(
    username: str = Path(..., description="The username to get gateway model definition permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[NamedPermissionSummary]:
    """List gateway model definition permissions for a user.

    - Admins see all gateway model definitions with the target user's effective permissions.
    - The target user sees model definitions where their effective permission is not NO_PERMISSIONS.
    - Other users see only model definitions they themselves can MANAGE.
    """
    try:
        all_models = fetch_all_gateway_model_definitions()

        results: list[NamedPermissionSummary] = []
        for md in all_models:
            md_name = md.get("name", "")
            if not md_name:
                continue
            perm_result = effective_gateway_model_definition_permission(md_name, username)
            if is_admin:
                results.append(
                    NamedPermissionSummary(
                        name=md_name,
                        permission=perm_result.permission.name,
                        kind=perm_result.kind,
                    )
                )
            elif current_username == username:
                if perm_result.permission.name != NO_PERMISSIONS.name:
                    results.append(
                        NamedPermissionSummary(
                            name=md_name,
                            permission=perm_result.permission.name,
                            kind=perm_result.kind,
                        )
                    )
            else:
                caller_perm = effective_gateway_model_definition_permission(md_name, current_username)
                if caller_perm.permission.can_manage:
                    results.append(
                        NamedPermissionSummary(
                            name=md_name,
                            permission=perm_result.permission.name,
                            kind=perm_result.kind,
                        )
                    )
        return results
    except Exception as e:
        logger.error(f"Error listing gateway model definition permissions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve gateway model definition permissions",
        )


@user_permissions_router.post(
    USER_GATEWAY_MODEL_DEFINITION_PERMISSION_DETAIL,
    status_code=201,
    response_model=NamedPermissionSummary,
    summary="Create gateway model definition permission for a user",
    description="Creates a new permission for a user to access a specific gateway model definition.",
    tags=["user gateway model definition permissions"],
)
async def create_user_gateway_model_definition_permission(
    username: str = Path(..., description="The username to grant gateway model definition permission to"),
    name: str = Path(..., description="The gateway model definition name to set permissions for"),
    permission_data: GatewayPermission = Body(..., description="The permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> NamedPermissionSummary:
    """Create a gateway model definition permission for a user."""
    try:
        perm = store.create_gateway_model_definition_permission(gateway_name=name, username=username, permission=permission_data.permission)
        emit_audit_event(
            "permission.create",
            actor=admin_username,
            resource_type="gateway_model_definition_permission",
            resource_id=name,
            detail={"username": username, "permission": permission_data.permission},
        )
        return NamedPermissionSummary(name=perm.model_definition_id, permission=perm.permission, kind="user")
    except Exception as e:
        logger.error(f"Error creating gateway model definition permission: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create gateway model definition permission",
        )


@user_permissions_router.get(
    USER_GATEWAY_MODEL_DEFINITION_PERMISSION_DETAIL,
    response_model=NamedPermissionSummary,
    summary="Get gateway model definition permission for a user",
    description="Retrieves the permission for a user on a specific gateway model definition.",
    tags=["user gateway model definition permissions"],
)
async def get_user_gateway_model_definition_permission(
    username: str = Path(..., description="The username to get gateway model definition permission for"),
    name: str = Path(..., description="The gateway model definition name to get permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> NamedPermissionSummary:
    """Get a gateway model definition permission for a user."""
    try:
        perm = store.get_gateway_model_definition_permission(gateway_name=name, username=username)
        return NamedPermissionSummary(name=perm.model_definition_id, permission=perm.permission, kind="user")
    except Exception as e:
        logger.error(f"Error getting gateway model definition permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Gateway model definition permission not found")


@user_permissions_router.patch(
    USER_GATEWAY_MODEL_DEFINITION_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Update gateway model definition permission for a user",
    description="Updates the permission for a user on a specific gateway model definition.",
    tags=["user gateway model definition permissions"],
)
async def update_user_gateway_model_definition_permission(
    username: str = Path(
        ...,
        description="The username to update gateway model definition permission for",
    ),
    name: str = Path(..., description="The gateway model definition name to update permissions for"),
    permission_data: GatewayPermission = Body(..., description="Updated permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Update a gateway model definition permission for a user."""
    try:
        store.update_gateway_model_definition_permission(gateway_name=name, username=username, permission=permission_data.permission)
        emit_audit_event(
            "permission.update",
            actor=admin_username,
            resource_type="gateway_model_definition_permission",
            resource_id=name,
            detail={"username": username, "permission": permission_data.permission},
        )
        return StatusMessageResponse(message=f"Gateway model definition permission updated for {username} on {name}")
    except Exception as e:
        logger.error(f"Error updating gateway model definition permission: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update gateway model definition permission",
        )


@user_permissions_router.delete(
    USER_GATEWAY_MODEL_DEFINITION_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway model definition permission for a user",
    description="Deletes the permission for a user on a specific gateway model definition.",
    tags=["user gateway model definition permissions"],
)
async def delete_user_gateway_model_definition_permission(
    username: str = Path(
        ...,
        description="The username to delete gateway model definition permission for",
    ),
    name: str = Path(..., description="The gateway model definition name to delete permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway model definition permission for a user."""
    try:
        store.delete_gateway_model_definition_permission(gateway_name=name, username=username)
        emit_audit_event(
            "permission.delete",
            actor=admin_username,
            resource_type="gateway_model_definition_permission",
            resource_id=name,
            detail={"username": username},
        )
        return StatusMessageResponse(message=f"Gateway model definition permission deleted for {username} on {name}")
    except Exception as e:
        logger.error(f"Error deleting gateway model definition permission: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete gateway model definition permission",
        )


# ========================================================================================
# GATEWAY MODEL DEFINITION PATTERN PERMISSIONS
# ========================================================================================


@user_permissions_router.get(
    USER_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSIONS,
    response_model=List[UserGatewayRegexPermissionItem],
    summary="List gateway model definition pattern permissions for a user",
    description="Retrieves a list of regex-based gateway model definition permission patterns for the specified user.",
    tags=["user gateway model definition pattern permissions"],
)
async def get_user_gateway_model_definition_pattern_permissions(
    username: str = Path(
        ...,
        description="The username to list gateway model definition pattern permissions for",
    ),
    admin_username: str = Depends(check_admin_permission),
) -> List[UserGatewayRegexPermissionItem]:
    """List gateway model definition pattern permissions for a user."""
    try:
        perms = store.list_gateway_model_definition_regex_permissions(username=username)
        return [
            UserGatewayRegexPermissionItem(
                id=p.id,
                regex=p.regex,
                priority=p.priority,
                user_id=p.user_id,
                permission=p.permission,
                workspace=pattern_workspace_of(p),
            )
            for p in perms
        ]
    except Exception as e:
        logger.error(f"Error listing gateway model definition pattern permissions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve gateway model definition pattern permissions",
        )


@user_permissions_router.post(
    USER_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSIONS,
    status_code=201,
    response_model=UserGatewayRegexPermissionItem,
    summary="Create gateway model definition pattern permission for a user",
    description="Creates a new regex-based permission pattern for gateway model definition access.",
    tags=["user gateway model definition pattern permissions"],
)
async def create_user_gateway_model_definition_pattern_permission(
    username: str = Path(
        ...,
        description="The username to create gateway model definition pattern permission for",
    ),
    pattern_data: GatewayRegexCreate = Body(..., description="The regex pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> UserGatewayRegexPermissionItem:
    """Create a gateway model definition pattern permission for a user."""
    try:
        perm = store.create_gateway_model_definition_regex_permission(
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
            username=username,
        )
        emit_audit_event(
            "permission.create",
            actor=admin_username,
            resource_type="gateway_model_definition_regex_permission",
            resource_id=username,
            detail={"regex": pattern_data.regex, "priority": pattern_data.priority, "permission": pattern_data.permission},
        )
        return UserGatewayRegexPermissionItem(
            id=perm.id,
            regex=perm.regex,
            priority=perm.priority,
            user_id=perm.user_id,
            permission=perm.permission,
            workspace=pattern_workspace_of(perm),
        )
    except Exception as e:
        logger.error(f"Error creating gateway model definition pattern permission: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create gateway model definition pattern permission",
        )


@user_permissions_router.get(
    USER_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSION_DETAIL,
    response_model=UserGatewayRegexPermissionItem,
    summary="Get gateway model definition pattern permission for a user",
    description="Retrieves a specific regex-based gateway model definition permission pattern for the specified user.",
    tags=["user gateway model definition pattern permissions"],
)
async def get_user_gateway_model_definition_pattern_permission(
    username: str = Path(
        ...,
        description="The username to get gateway model definition pattern permission for",
    ),
    id: int = Path(..., description="The pattern ID to retrieve"),
    admin_username: str = Depends(check_admin_permission),
) -> UserGatewayRegexPermissionItem:
    """Get a gateway model definition pattern permission for a user."""
    try:
        perm = store.get_gateway_model_definition_regex_permission(id=id, username=username)
        return UserGatewayRegexPermissionItem(
            id=perm.id,
            regex=perm.regex,
            priority=perm.priority,
            user_id=perm.user_id,
            permission=perm.permission,
            workspace=pattern_workspace_of(perm),
        )
    except Exception as e:
        logger.error(f"Error getting gateway model definition pattern permission: {str(e)}")
        raise HTTPException(
            status_code=404,
            detail="Gateway model definition pattern permission not found",
        )


@user_permissions_router.patch(
    USER_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSION_DETAIL,
    response_model=UserGatewayRegexPermissionItem,
    summary="Update gateway model definition pattern permission for a user",
    description="Updates a specific regex-based gateway model definition permission pattern for the specified user.",
    tags=["user gateway model definition pattern permissions"],
)
async def update_user_gateway_model_definition_pattern_permission(
    username: str = Path(
        ...,
        description="The username to update gateway model definition pattern permission for",
    ),
    id: int = Path(..., description="The pattern ID to update"),
    pattern_data: GatewayRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> UserGatewayRegexPermissionItem:
    """Update a gateway model definition pattern permission for a user."""
    try:
        perm = store.update_gateway_model_definition_regex_permission(
            id=id,
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
            username=username,
        )
        emit_audit_event(
            "permission.update",
            actor=admin_username,
            resource_type="gateway_model_definition_regex_permission",
            resource_id=username,
            detail={"id": id, "regex": pattern_data.regex, "priority": pattern_data.priority, "permission": pattern_data.permission},
        )
        return UserGatewayRegexPermissionItem(
            id=perm.id,
            regex=perm.regex,
            priority=perm.priority,
            user_id=perm.user_id,
            permission=perm.permission,
            workspace=pattern_workspace_of(perm),
        )
    except Exception as e:
        logger.error(f"Error updating gateway model definition pattern permission: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update gateway model definition pattern permission",
        )


@user_permissions_router.delete(
    USER_GATEWAY_MODEL_DEFINITION_PATTERN_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway model definition pattern permission for a user",
    description="Deletes a specific regex-based gateway model definition permission pattern for the specified user.",
    tags=["user gateway model definition pattern permissions"],
)
async def delete_user_gateway_model_definition_pattern_permission(
    username: str = Path(
        ...,
        description="The username to delete gateway model definition pattern permission for",
    ),
    id: int = Path(..., description="The pattern ID to delete"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway model definition pattern permission for a user."""
    try:
        store.delete_gateway_model_definition_regex_permission(id=id, username=username)
        emit_audit_event(
            "permission.delete",
            actor=admin_username,
            resource_type="gateway_model_definition_regex_permission",
            resource_id=username,
            detail={"id": id},
        )
        return StatusMessageResponse(message=f"Gateway model definition pattern permission deleted for {username}")
    except Exception as e:
        logger.error(f"Error deleting gateway model definition pattern permission: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete gateway model definition pattern permission",
        )


# ========================================================================================
# GATEWAY SECRET PERMISSIONS
# ========================================================================================


@user_permissions_router.get(
    USER_GATEWAY_SECRET_PERMISSIONS,
    response_model=List[NamedPermissionSummary],
    summary="List gateway secret permissions for a user",
    description="Retrieves a list of gateway secret permissions for the specified user.",
    tags=["user gateway secret permissions"],
)
async def get_user_gateway_secret_permissions(
    username: str = Path(..., description="The username to get gateway secret permissions for"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> List[NamedPermissionSummary]:
    """List gateway secret permissions for a user.

    - Admins see all gateway secrets with the target user's effective permissions.
    - The target user sees secrets where their effective permission is not NO_PERMISSIONS.
    - Other users see only secrets they themselves can MANAGE.
    """
    try:
        all_secrets = fetch_all_gateway_secrets()

        results: list[NamedPermissionSummary] = []
        for secret in all_secrets:
            secret_name = secret.get("secret_name") or secret.get("name") or secret.get("key", "")
            if not secret_name:
                continue
            perm_result = effective_gateway_secret_permission(secret_name, username)
            if is_admin:
                results.append(
                    NamedPermissionSummary(
                        name=secret_name,
                        permission=perm_result.permission.name,
                        kind=perm_result.kind,
                    )
                )
            elif current_username == username:
                if perm_result.permission.name != NO_PERMISSIONS.name:
                    results.append(
                        NamedPermissionSummary(
                            name=secret_name,
                            permission=perm_result.permission.name,
                            kind=perm_result.kind,
                        )
                    )
            else:
                caller_perm = effective_gateway_secret_permission(secret_name, current_username)
                if caller_perm.permission.can_manage:
                    results.append(
                        NamedPermissionSummary(
                            name=secret_name,
                            permission=perm_result.permission.name,
                            kind=perm_result.kind,
                        )
                    )
        return results
    except Exception as e:
        logger.error(f"Error listing gateway secret permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve gateway secret permissions")


@user_permissions_router.post(
    USER_GATEWAY_SECRET_PERMISSION_DETAIL,
    status_code=201,
    response_model=NamedPermissionSummary,
    summary="Create gateway secret permission for a user",
    description="Creates a new permission for a user to access a specific gateway secret.",
    tags=["user gateway secret permissions"],
)
async def create_user_gateway_secret_permission(
    username: str = Path(..., description="The username to grant gateway secret permission to"),
    name: str = Path(..., description="The gateway secret name to set permissions for"),
    permission_data: GatewayPermission = Body(..., description="The permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> NamedPermissionSummary:
    """Create a gateway secret permission for a user."""
    try:
        perm = store.create_gateway_secret_permission(gateway_name=name, username=username, permission=permission_data.permission)
        emit_audit_event(
            "permission.create",
            actor=admin_username,
            resource_type="gateway_secret_permission",
            resource_id=name,
            detail={"username": username, "permission": permission_data.permission},
        )
        return NamedPermissionSummary(name=perm.secret_id, permission=perm.permission, kind="user")
    except Exception as e:
        logger.error(f"Error creating gateway secret permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create gateway secret permission")


@user_permissions_router.get(
    USER_GATEWAY_SECRET_PERMISSION_DETAIL,
    response_model=NamedPermissionSummary,
    summary="Get gateway secret permission for a user",
    description="Retrieves the permission for a user on a specific gateway secret.",
    tags=["user gateway secret permissions"],
)
async def get_user_gateway_secret_permission(
    username: str = Path(..., description="The username to get gateway secret permission for"),
    name: str = Path(..., description="The gateway secret name to get permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> NamedPermissionSummary:
    """Get a gateway secret permission for a user."""
    try:
        perm = store.get_gateway_secret_permission(gateway_name=name, username=username)
        return NamedPermissionSummary(name=perm.secret_id, permission=perm.permission, kind="user")
    except Exception as e:
        logger.error(f"Error getting gateway secret permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Gateway secret permission not found")


@user_permissions_router.patch(
    USER_GATEWAY_SECRET_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Update gateway secret permission for a user",
    description="Updates the permission for a user on a specific gateway secret.",
    tags=["user gateway secret permissions"],
)
async def update_user_gateway_secret_permission(
    username: str = Path(..., description="The username to update gateway secret permission for"),
    name: str = Path(..., description="The gateway secret name to update permissions for"),
    permission_data: GatewayPermission = Body(..., description="Updated permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Update a gateway secret permission for a user."""
    try:
        store.update_gateway_secret_permission(gateway_name=name, username=username, permission=permission_data.permission)
        emit_audit_event(
            "permission.update",
            actor=admin_username,
            resource_type="gateway_secret_permission",
            resource_id=name,
            detail={"username": username, "permission": permission_data.permission},
        )
        return StatusMessageResponse(message=f"Gateway secret permission updated for {username} on {name}")
    except Exception as e:
        logger.error(f"Error updating gateway secret permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update gateway secret permission")


@user_permissions_router.delete(
    USER_GATEWAY_SECRET_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway secret permission for a user",
    description="Deletes the permission for a user on a specific gateway secret.",
    tags=["user gateway secret permissions"],
)
async def delete_user_gateway_secret_permission(
    username: str = Path(..., description="The username to delete gateway secret permission for"),
    name: str = Path(..., description="The gateway secret name to delete permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway secret permission for a user."""
    try:
        store.delete_gateway_secret_permission(gateway_name=name, username=username)
        emit_audit_event(
            "permission.delete",
            actor=admin_username,
            resource_type="gateway_secret_permission",
            resource_id=name,
            detail={"username": username},
        )
        return StatusMessageResponse(message=f"Gateway secret permission deleted for {username} on {name}")
    except Exception as e:
        logger.error(f"Error deleting gateway secret permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete gateway secret permission")


# ========================================================================================
# GATEWAY SECRET PATTERN PERMISSIONS
# ========================================================================================


@user_permissions_router.get(
    USER_GATEWAY_SECRET_PATTERN_PERMISSIONS,
    response_model=List[UserGatewayRegexPermissionItem],
    summary="List gateway secret pattern permissions for a user",
    description="Retrieves a list of regex-based gateway secret permission patterns for the specified user.",
    tags=["user gateway secret pattern permissions"],
)
async def get_user_gateway_secret_pattern_permissions(
    username: str = Path(..., description="The username to list gateway secret pattern permissions for"),
    admin_username: str = Depends(check_admin_permission),
) -> List[UserGatewayRegexPermissionItem]:
    """List gateway secret pattern permissions for a user."""
    try:
        perms = store.list_gateway_secret_regex_permissions(username=username)
        return [
            UserGatewayRegexPermissionItem(
                id=p.id,
                regex=p.regex,
                priority=p.priority,
                user_id=p.user_id,
                permission=p.permission,
                workspace=pattern_workspace_of(p),
            )
            for p in perms
        ]
    except Exception as e:
        logger.error(f"Error listing gateway secret pattern permissions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve gateway secret pattern permissions",
        )


@user_permissions_router.post(
    USER_GATEWAY_SECRET_PATTERN_PERMISSIONS,
    status_code=201,
    response_model=UserGatewayRegexPermissionItem,
    summary="Create gateway secret pattern permission for a user",
    description="Creates a new regex-based permission pattern for gateway secret access.",
    tags=["user gateway secret pattern permissions"],
)
async def create_user_gateway_secret_pattern_permission(
    username: str = Path(..., description="The username to create gateway secret pattern permission for"),
    pattern_data: GatewayRegexCreate = Body(..., description="The regex pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> UserGatewayRegexPermissionItem:
    """Create a gateway secret pattern permission for a user."""
    try:
        perm = store.create_gateway_secret_regex_permission(
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
            username=username,
        )
        emit_audit_event(
            "permission.create",
            actor=admin_username,
            resource_type="gateway_secret_regex_permission",
            resource_id=username,
            detail={"regex": pattern_data.regex, "priority": pattern_data.priority, "permission": pattern_data.permission},
        )
        return UserGatewayRegexPermissionItem(
            id=perm.id,
            regex=perm.regex,
            priority=perm.priority,
            user_id=perm.user_id,
            permission=perm.permission,
            workspace=pattern_workspace_of(perm),
        )
    except Exception as e:
        logger.error(f"Error creating gateway secret pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create gateway secret pattern permission")


@user_permissions_router.get(
    USER_GATEWAY_SECRET_PATTERN_PERMISSION_DETAIL,
    response_model=UserGatewayRegexPermissionItem,
    summary="Get gateway secret pattern permission for a user",
    description="Retrieves a specific regex-based gateway secret permission pattern for the specified user.",
    tags=["user gateway secret pattern permissions"],
)
async def get_user_gateway_secret_pattern_permission(
    username: str = Path(..., description="The username to get gateway secret pattern permission for"),
    id: int = Path(..., description="The pattern ID to retrieve"),
    admin_username: str = Depends(check_admin_permission),
) -> UserGatewayRegexPermissionItem:
    """Get a gateway secret pattern permission for a user."""
    try:
        perm = store.get_gateway_secret_regex_permission(id=id, username=username)
        return UserGatewayRegexPermissionItem(
            id=perm.id,
            regex=perm.regex,
            priority=perm.priority,
            user_id=perm.user_id,
            permission=perm.permission,
            workspace=pattern_workspace_of(perm),
        )
    except Exception as e:
        logger.error(f"Error getting gateway secret pattern permission: {str(e)}")
        raise HTTPException(status_code=404, detail="Gateway secret pattern permission not found")


@user_permissions_router.patch(
    USER_GATEWAY_SECRET_PATTERN_PERMISSION_DETAIL,
    response_model=UserGatewayRegexPermissionItem,
    summary="Update gateway secret pattern permission for a user",
    description="Updates a specific regex-based gateway secret permission pattern for the specified user.",
    tags=["user gateway secret pattern permissions"],
)
async def update_user_gateway_secret_pattern_permission(
    username: str = Path(..., description="The username to update gateway secret pattern permission for"),
    id: int = Path(..., description="The pattern ID to update"),
    pattern_data: GatewayRegexCreate = Body(..., description="Updated pattern permission details"),
    admin_username: str = Depends(check_admin_permission),
) -> UserGatewayRegexPermissionItem:
    """Update a gateway secret pattern permission for a user."""
    try:
        perm = store.update_gateway_secret_regex_permission(
            id=id,
            regex=pattern_data.regex,
            priority=pattern_data.priority,
            permission=pattern_data.permission,
            username=username,
        )
        emit_audit_event(
            "permission.update",
            actor=admin_username,
            resource_type="gateway_secret_regex_permission",
            resource_id=username,
            detail={"id": id, "regex": pattern_data.regex, "priority": pattern_data.priority, "permission": pattern_data.permission},
        )
        return UserGatewayRegexPermissionItem(
            id=perm.id,
            regex=perm.regex,
            priority=perm.priority,
            user_id=perm.user_id,
            permission=perm.permission,
            workspace=pattern_workspace_of(perm),
        )
    except Exception as e:
        logger.error(f"Error updating gateway secret pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update gateway secret pattern permission")


@user_permissions_router.delete(
    USER_GATEWAY_SECRET_PATTERN_PERMISSION_DETAIL,
    response_model=StatusMessageResponse,
    summary="Delete gateway secret pattern permission for a user",
    description="Deletes a specific regex-based gateway secret permission pattern for the specified user.",
    tags=["user gateway secret pattern permissions"],
)
async def delete_user_gateway_secret_pattern_permission(
    username: str = Path(..., description="The username to delete gateway secret pattern permission for"),
    id: int = Path(..., description="The pattern ID to delete"),
    admin_username: str = Depends(check_admin_permission),
) -> StatusMessageResponse:
    """Delete a gateway secret pattern permission for a user."""
    try:
        store.delete_gateway_secret_regex_permission(id=id, username=username)
        emit_audit_event(
            "permission.delete",
            actor=admin_username,
            resource_type="gateway_secret_regex_permission",
            resource_id=username,
            detail={"id": id},
        )
        return StatusMessageResponse(message=f"Gateway secret pattern permission deleted for {username}")
    except Exception as e:
        logger.error(f"Error deleting gateway secret pattern permission: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete gateway secret pattern permission")
