"""The workspace a name-keyed grant belongs to.

MLflow keeps registered models (and prompts, which are registered models), gateway endpoints,
gateway secrets, gateway model definitions and MCP servers unique per ``(workspace, name)``. A grant on one of
them names the resource by name, so it must also say which workspace's resource it is — otherwise
a grant on ``churn`` in one workspace would apply to another workspace's ``churn``.

The grant workspace is always the one MLflow serves the request from: the workspace the request
names, or the default workspace when it names none. With ``MLFLOW_ENABLE_WORKSPACES`` off every
resource lives in the default workspace, new grants record it, and lookups match the default
workspace's grants and grants written before the column existed (``workspace IS NULL``) — every
grant a deployment that has never enabled workspaces has, so it behaves exactly as before. Grants
recorded for another workspace, on a deployment that turns workspaces off again, do not count.

With workspaces on, a lookup matches only grants recorded for the request's workspace. Grants from
before the column existed carry no workspace and match nothing until
:mod:`mlflow_oidc_auth.grant_workspace_backfill` assigns them one at startup.
"""

from mlflow.utils.workspace_utils import DEFAULT_WORKSPACE_NAME
from sqlalchemy import or_
from sqlalchemy.sql.elements import ColumnElement

from mlflow_oidc_auth.config import config

#: Recorded by the startup backfill on a legacy grant it could not place in a workspace. MLflow's
#: workspace names cannot contain ":", so it never equals a real workspace: the grant matches
#: nothing — with workspaces disabled too — and the backfill does not try to place it again, so a
#: resource created later can never pick it up.
UNRESOLVED_WORKSPACE = "::unresolved"

#: Recorded on a resource pattern (regex grant) that applies in every workspace: one created with
#: no workspace named, and every pattern from before patterns carried a workspace. MLflow's
#: workspace names cannot contain "*", so it never equals a real workspace.
EVERY_WORKSPACE = "*"


def current_grant_workspace() -> str:
    """The workspace grants are read and written in for the current request.

    A workspace the request names (``X-MLFLOW-WORKSPACE``) comes from its ``AuthContext``, which
    Flask reads from its environ and FastAPI routes from the context the permission middleware
    bridges. When the request names none, or there is no ``AuthContext`` (outside a request, or on
    an unprotected route), it is
    the workspace MLflow serves the request from: the one ``WorkspaceContextMiddleware`` resolved
    from the same header, else MLflow's own fallback (its default workspace, or ``MLFLOW_WORKSPACE``
    with a workspace provider that has no default). So a grant is always recorded and looked up in
    the workspace MLflow reads and writes the resource in.

    Returns:
        The request's workspace, or ``default`` when none resolves or workspaces are disabled.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return DEFAULT_WORKSPACE_NAME
    from mlflow.utils.workspace_context import get_request_workspace as mlflow_request_workspace

    from mlflow_oidc_auth.bridge.user import get_auth_context

    try:
        named = get_auth_context().workspace
    except Exception:
        named = None
    return named or mlflow_request_workspace() or DEFAULT_WORKSPACE_NAME


def grant_workspace_condition(column) -> ColumnElement:
    """A filter on a grant table's ``workspace`` column for the current request.

    With workspaces disabled it matches the ``default`` workspace's grants and unassigned ones —
    every grant a deployment that never enabled workspaces has. With workspaces enabled it matches
    only the request's grant workspace, so a grant without a workspace matches nothing.

    Parameters:
        column: The grant model's ``workspace`` column.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return disabled_workspace_condition(column)
    return column == current_grant_workspace()


def disabled_workspace_condition(column) -> ColumnElement:
    """The grants that count while workspaces are disabled: ``default``'s and unassigned ones.

    With workspaces disabled MLflow serves only the default workspace, so a grant recorded for
    another workspace (on a deployment that had workspaces enabled before) must not count — it
    would authorize ``default``'s same-named resource, and two grants for one name would make the
    lookup ambiguous. Unassigned grants predate the column; on such a deployment every resource
    was in ``default``, and the startup backfill assigns them ``default``.
    """
    return or_(column.is_(None), column == DEFAULT_WORKSPACE_NAME)


def in_grant_workspace(grant) -> bool:
    """Whether an already-loaded grant entity belongs to the current request's grant workspace.

    For code that reads grants through a user's ORM relationships rather than a scoped query.
    With workspaces disabled, true for ``default``'s grants and unassigned ones.
    """
    workspace = getattr(grant, "workspace", None)
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return workspace is None or workspace == DEFAULT_WORKSPACE_NAME
    return workspace == current_grant_workspace()


def workspace_scoped_grant_tables():
    """Every grant table whose grants belong to one workspace.

    Returns:
        ``(model, resource column, principal column, resource kind)`` per table; ``kind`` names the
        MLflow resource type (prompts are registered models).
    """
    from mlflow_oidc_auth.db.models import (
        SqlGatewayEndpointGroupPermission,
        SqlGatewayEndpointPermission,
        SqlGatewayModelDefinitionGroupPermission,
        SqlGatewayModelDefinitionPermission,
        SqlGatewaySecretGroupPermission,
        SqlGatewaySecretPermission,
        SqlMCPServerGroupPermission,
        SqlMCPServerPermission,
        SqlRegisteredModelGroupPermission,
        SqlRegisteredModelPermission,
    )

    return (
        (SqlRegisteredModelPermission, "name", "user_id", "registered_model"),
        (SqlRegisteredModelGroupPermission, "name", "group_id", "registered_model"),
        (SqlGatewayEndpointPermission, "endpoint_id", "user_id", "gateway_endpoint"),
        (SqlGatewayEndpointGroupPermission, "endpoint_id", "group_id", "gateway_endpoint"),
        (SqlGatewaySecretPermission, "secret_id", "user_id", "gateway_secret"),
        (SqlGatewaySecretGroupPermission, "secret_id", "group_id", "gateway_secret"),
        (SqlGatewayModelDefinitionPermission, "model_definition_id", "user_id", "gateway_model_definition"),
        (SqlGatewayModelDefinitionGroupPermission, "model_definition_id", "group_id", "gateway_model_definition"),
        (SqlMCPServerPermission, "name", "user_id", "mcp_server"),
        (SqlMCPServerGroupPermission, "name", "group_id", "mcp_server"),
    )


def new_pattern_workspace() -> str:
    """The workspace a new resource pattern applies in.

    The one the request names (``X-MLFLOW-WORKSPACE``) — in the admin UI, the workspace selected in
    the picker — or every workspace when it names none ("All Workspaces") or workspaces are
    disabled. Patterns are created by administrators only.

    Returns:
        A workspace name, or :data:`EVERY_WORKSPACE`.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return EVERY_WORKSPACE
    from mlflow_oidc_auth.bridge.user import get_request_workspace

    return get_request_workspace() or EVERY_WORKSPACE


def pattern_in_scope(rule, workspace: str | None = None) -> bool:
    """Whether a resource pattern applies to a resource in ``workspace``.

    A pattern for every workspace always applies; one recorded for a workspace applies only to that
    workspace's resources. With workspaces disabled every resource is in ``default``, so a pattern
    recorded for another workspace (on a deployment that turns workspaces off again) does not apply.

    Parameters:
        rule: A pattern entity; one without a ``workspace`` (a workspace pattern) always applies.
        workspace: The resource's workspace; the current request's grant workspace when omitted.
            :data:`EVERY_WORKSPACE` stands for a resource whose workspace is not known, to which
            every pattern may apply.
    """
    rule_workspace = getattr(rule, "workspace", None)
    if not isinstance(rule_workspace, str) or rule_workspace == EVERY_WORKSPACE or workspace == EVERY_WORKSPACE:
        return True
    if workspace is None:
        workspace = current_grant_workspace()
    return rule_workspace == workspace


def workspace_scoped_pattern_tables():
    """Every resource pattern table, whose rows carry the workspace they apply in.

    Returns:
        The SQLAlchemy models of the user and group pattern tables of experiments, registered models
        and prompts, scorers and AI Gateway resources. Workspace patterns are not among them.
    """
    from mlflow_oidc_auth.db.models import (
        SqlExperimentGroupRegexPermission,
        SqlExperimentRegexPermission,
        SqlGatewayEndpointGroupRegexPermission,
        SqlGatewayEndpointRegexPermission,
        SqlGatewayModelDefinitionGroupRegexPermission,
        SqlGatewayModelDefinitionRegexPermission,
        SqlGatewaySecretGroupRegexPermission,
        SqlGatewaySecretRegexPermission,
        SqlRegisteredModelGroupRegexPermission,
        SqlRegisteredModelRegexPermission,
        SqlScorerGroupRegexPermission,
        SqlScorerRegexPermission,
    )

    return (
        SqlExperimentRegexPermission,
        SqlExperimentGroupRegexPermission,
        SqlRegisteredModelRegexPermission,
        SqlRegisteredModelGroupRegexPermission,
        SqlScorerRegexPermission,
        SqlScorerGroupRegexPermission,
        SqlGatewayEndpointRegexPermission,
        SqlGatewayEndpointGroupRegexPermission,
        SqlGatewaySecretRegexPermission,
        SqlGatewaySecretGroupRegexPermission,
        SqlGatewayModelDefinitionRegexPermission,
        SqlGatewayModelDefinitionGroupRegexPermission,
    )


def pattern_workspace_of(rule) -> str | None:
    """The workspace a pattern entity reports, for API responses: a name, ``*``, or None if unknown."""
    workspace = getattr(rule, "workspace", None)
    return workspace if isinstance(workspace, str) else None
