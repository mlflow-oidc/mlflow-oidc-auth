"""The workspace a name-keyed grant belongs to.

MLflow keeps registered models (and prompts, which are registered models), gateway endpoints,
gateway secrets and gateway model definitions unique per ``(workspace, name)``. A grant on one of
them names the resource by name, so it must also say which workspace's resource it is — otherwise
a grant on ``churn`` in one workspace would apply to another workspace's ``churn``.

The grant workspace is always the one MLflow serves the request from: the workspace the request
names, or the default workspace when it names none. With ``MLFLOW_ENABLE_WORKSPACES`` off every
resource lives in the default workspace, new grants record it, and lookups do not filter on the
workspace at all — so a deployment that has never enabled workspaces behaves exactly as before,
including for grants written before the column existed (``workspace IS NULL``).

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


def current_grant_workspace() -> str:
    """The workspace grants are read and written in for the current request.

    The request's ``AuthContext`` names it where one is available — Flask routes, and the FastAPI
    routes the permission middleware bridges. Elsewhere (this plugin's own permission API routes)
    it is the workspace MLflow resolved for the request, which ``WorkspaceContextMiddleware`` sets
    for every request from the same header. Both treat a missing header as the default workspace.

    Returns:
        The request's workspace, or ``default`` when it names none or workspaces are disabled.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return DEFAULT_WORKSPACE_NAME
    from mlflow_oidc_auth.bridge.user import get_auth_context

    try:
        return get_auth_context().workspace or DEFAULT_WORKSPACE_NAME
    except Exception:
        pass
    from mlflow.utils.workspace_context import get_request_workspace as mlflow_request_workspace
    from mlflow.utils.workspace_context import is_request_workspace_resolved

    if is_request_workspace_resolved():
        return mlflow_request_workspace() or DEFAULT_WORKSPACE_NAME
    return DEFAULT_WORKSPACE_NAME


def grant_workspace_condition(column) -> ColumnElement:
    """A filter on a grant table's ``workspace`` column for the current request.

    With workspaces disabled nothing is filtered, as before the column existed — except grants the
    backfill marked unresolved. With workspaces enabled it matches only the request's grant
    workspace, so a grant without a workspace matches nothing.

    Parameters:
        column: The grant model's ``workspace`` column.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return or_(column.is_(None), column != UNRESOLVED_WORKSPACE)
    return column == current_grant_workspace()


def in_grant_workspace(grant) -> bool:
    """Whether an already-loaded grant entity belongs to the current request's grant workspace.

    For code that reads grants through a user's ORM relationships rather than a scoped query.
    Always true with workspaces disabled.
    """
    workspace = getattr(grant, "workspace", None)
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return workspace != UNRESOLVED_WORKSPACE
    return workspace == current_grant_workspace()
