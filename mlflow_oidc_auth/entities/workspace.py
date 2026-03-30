"""Workspace permission entity classes.

These entities represent workspace-level permissions for users and groups.
Unlike resource permissions (experiments, models), workspace permissions are
tenant boundaries — they do NOT extend PermissionBase.

Regex variants (WorkspaceRegexPermission, WorkspaceGroupRegexPermission) extend
RegexPermissionBase for pattern-based workspace access rules.
"""

from dataclasses import dataclass

from mlflow_oidc_auth.entities._base import RegexPermissionBase


class WorkspacePermission:
    """User-level workspace permission entity."""

    def __init__(self, workspace: str, user_id: int, permission: str, username: str | None = None):
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


@dataclass(init=False)
class WorkspaceRegexPermission(RegexPermissionBase):
    """User-level regex-based workspace permission entity."""

    def __init__(self, id_, regex, priority, user_id=None, permission=None):
        super().__init__(
            id=id_,
            regex=regex,
            priority=priority,
            permission=permission,
            user_id=user_id,
        )

    def to_json(self) -> dict:
        return super().to_json()

    @classmethod
    def from_json(cls, dictionary: dict) -> "WorkspaceRegexPermission":
        user_id = dictionary.get("user_id")
        if user_id is not None:
            try:
                user_id = int(user_id)
            except (TypeError, ValueError):
                raise ValueError("user_id must be an integer")
        return cls(
            id_=dictionary["id"],
            regex=dictionary["regex"],
            priority=dictionary["priority"],
            user_id=user_id,
            permission=dictionary.get("permission"),
        )


@dataclass(init=False)
class WorkspaceGroupRegexPermission(RegexPermissionBase):
    """Group-level regex-based workspace permission entity."""

    def __init__(self, id_, regex, priority, group_id, permission):
        super().__init__(
            id=id_,
            regex=regex,
            priority=priority,
            permission=permission,
            group_id=group_id,
        )

    def to_json(self) -> dict:
        return super().to_json()

    @classmethod
    def from_json(cls, dictionary: dict) -> "WorkspaceGroupRegexPermission":
        group_id = dictionary.get("group_id")
        if group_id is not None:
            try:
                group_id = int(group_id)
            except (TypeError, ValueError):
                raise ValueError("group_id must be an integer")
        return cls(
            id_=dictionary["id"],
            regex=dictionary["regex"],
            priority=dictionary["priority"],
            group_id=group_id,
            permission=dictionary["permission"],
        )
