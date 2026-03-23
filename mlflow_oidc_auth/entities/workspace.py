"""Workspace permission entity classes.

These entities represent workspace-level permissions for users and groups.
Unlike resource permissions (experiments, models), workspace permissions are
tenant boundaries — they do NOT extend PermissionBase.
"""


class WorkspacePermission:
    """User-level workspace permission entity."""

    def __init__(
        self, workspace: str, user_id: int, permission: str, username: str | None = None
    ):
        self._workspace = workspace
        self._user_id = user_id
        self._permission = permission
        self._username = username

    @property
    def workspace(self) -> str:
        return self._workspace

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def permission(self) -> str:
        return self._permission

    @property
    def username(self) -> str | None:
        return self._username

    def to_json(self) -> dict:
        return {
            "workspace": self._workspace,
            "user_id": self._user_id,
            "permission": self._permission,
            "username": self._username,
        }


class WorkspaceGroupPermission:
    """Group-level workspace permission entity."""

    def __init__(
        self,
        workspace: str,
        group_id: int,
        permission: str,
        group_name: str | None = None,
    ):
        self._workspace = workspace
        self._group_id = group_id
        self._permission = permission
        self._group_name = group_name

    @property
    def workspace(self) -> str:
        return self._workspace

    @property
    def group_id(self) -> int:
        return self._group_id

    @property
    def permission(self) -> str:
        return self._permission

    @property
    def group_name(self) -> str | None:
        return self._group_name

    def to_json(self) -> dict:
        return {
            "workspace": self._workspace,
            "group_id": self._group_id,
            "permission": self._permission,
            "group_name": self._group_name,
        }
