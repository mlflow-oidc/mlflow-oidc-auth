"""Which users, service accounts and groups a caller may see listed.

With ``RESTRICT_USER_AND_GROUP_LISTING`` on, a non-admin sees only principals it can already
see elsewhere: itself, the groups it belongs to, and the members of the workspaces it manages
(which the workspace member lists show it anyway). Admins, and every caller when the setting
is off, see everyone.
"""

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached


def listing_restricted(is_admin: bool) -> bool:
    """Whether the caller's user and group listings are restricted.

    Parameters:
        is_admin: Whether the caller is a global admin.

    Returns:
        True when ``RESTRICT_USER_AND_GROUP_LISTING`` is on and the caller is not an admin.
    """
    return bool(config.RESTRICT_USER_AND_GROUP_LISTING) and not is_admin


def _managed_workspaces(username: str) -> list[str]:
    """The workspaces holding grants on which ``username`` has MANAGE (empty without workspaces).

    A workspace with no grant has no members to show, so only those holding one are checked.
    The lookup fails closed: a workspace whose permission cannot be resolved is left out.
    """
    if not config.MLFLOW_ENABLE_WORKSPACES:
        return []
    from mlflow_oidc_auth.store import store

    managed = []
    for workspace in store.list_workspaces_with_grants():
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
