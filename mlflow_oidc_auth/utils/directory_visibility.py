"""Which users, service accounts and groups a caller may see listed.

With ``RESTRICT_USER_AND_GROUP_LISTING`` on, a non-admin sees only principals it can already
see elsewhere: itself, the groups it belongs to, and the members of the workspaces it manages
(which the workspace member lists show it anyway). Admins, and every caller when the setting
is off, see everyone.
"""

from fastapi import Request
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.utils.request_helpers_fastapi import get_is_admin
from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached


async def listing_restricted(request: Request) -> bool:
    """Whether the caller's user and group listings are restricted.

    The caller's admin flag is looked up only when the setting is on, so a default deployment
    pays nothing for it.

    Parameters:
        request: The incoming request.

    Returns:
        True when ``RESTRICT_USER_AND_GROUP_LISTING`` is on and the caller is not an admin.
    """
    if not config.RESTRICT_USER_AND_GROUP_LISTING:
        return False
    return not await get_is_admin(request=request)


def _managed_workspaces(username: str) -> list[str]:
    """The workspaces ``username`` has MANAGE on, among those it is granted directly or through a group.

    Only those workspaces are checked, so the cost follows the caller's own grants rather than
    the deployment's size. MANAGE that comes only from a regex grant is not looked for: the
    caller then types the names. Every lookup fails closed: a workspace whose permission cannot
    be resolved is left out, as is everything when the caller's own grants cannot be read.

    Parameters:
        username: The caller.

    Returns:
        The managed workspace names; empty when workspaces are disabled.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return []
    from mlflow_oidc_auth.store import store

    try:
        candidates = store.list_workspaces_granted_to_user(username)
    except MlflowException:
        return []
    managed = []
    for workspace in candidates:
        permission = get_workspace_permission_cached(username, workspace)
        if permission is not None and permission.can_manage:
            managed.append(workspace)
    return managed


def visible_usernames(username: str) -> set[str]:
    """The user and service account names a restricted caller may see listed.

    Parameters:
        username: The caller.

    Returns:
        The caller and every user holding a direct grant in a workspace the caller manages.
    """
    from mlflow_oidc_auth.store import store

    visible = {username}
    for workspace in _managed_workspaces(username):
        visible.update(p.username for p in store.list_workspace_permissions(workspace) if p.username)
    return visible


def visible_group_names(username: str) -> set[str]:
    """The group names a restricted caller may see listed.

    Parameters:
        username: The caller.

    Returns:
        The caller's groups and every group holding a grant in a workspace the caller manages.
    """
    from mlflow_oidc_auth.store import store

    visible = set(store.get_groups_for_user(username))
    for workspace in _managed_workspaces(username):
        visible.update(p.group_name for p in store.list_workspace_group_permissions(workspace) if p.group_name)
    return visible
