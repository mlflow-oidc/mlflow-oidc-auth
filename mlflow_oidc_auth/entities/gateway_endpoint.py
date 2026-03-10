from dataclasses import dataclass
from typing import Optional, Any, Dict

from ._base import PermissionBase, RegexPermissionBase


@dataclass
class GatewayEndpointPermission(PermissionBase):
    def __init__(self, endpoint_id: str, permission: str, user_id: Optional[int] = None, group_id: Optional[int] = None):
        super().__init__(instance=endpoint_id, permission=permission, user_id=user_id, group_id=group_id)

    @property
    def endpoint_id(self) -> str:
        return self.instance

    def to_json(self) -> Dict[str, Any]:
        d = super().to_json()
        d["endpoint_id"] = d.pop("instance")
        return d

    @classmethod
    def from_json(cls, d: Dict[str, Any]) -> "GatewayEndpointPermission":
        user_id = d.get("user_id")
        group_id = d.get("group_id")
        if user_id is not None:
            try:
                user_id = int(user_id)
            except (TypeError, ValueError):
                raise ValueError("user_id must be an integer")
        if group_id is not None:
            try:
                group_id = int(group_id)
            except (TypeError, ValueError):
                raise ValueError("group_id must be an integer")
        return cls(
            endpoint_id=d["endpoint_id"],
            permission=d["permission"],
            user_id=user_id,
            group_id=group_id,
        )


@dataclass(init=False)
class GatewayEndpointRegexPermission(RegexPermissionBase):
    def __init__(self, id_, regex, priority, user_id, permission):
        super().__init__(
            id=id_,
            regex=regex,
            priority=priority,
            permission=permission,
            user_id=user_id,
        )

    @classmethod
    def from_json(cls, d: Dict[str, Any]) -> "GatewayEndpointRegexPermission":
        user_id = d.get("user_id")
        if user_id is not None:
            try:
                user_id = int(user_id)
            except (TypeError, ValueError):
                raise ValueError("user_id must be an integer")
        return cls(
            id_=d["id"],
            regex=d["regex"],
            priority=d["priority"],
            user_id=user_id,
            permission=d.get("permission"),
        )


@dataclass(init=False)
class GatewayEndpointGroupRegexPermission(RegexPermissionBase):
    def __init__(self, id_, regex, priority, group_id, permission):
        super().__init__(
            id=id_,
            regex=regex,
            priority=priority,
            permission=permission,
            group_id=group_id,
        )

    @classmethod
    def from_json(cls, d: Dict[str, Any]) -> "GatewayEndpointGroupRegexPermission":
        group_id = d.get("group_id")
        if group_id is not None:
            try:
                group_id = int(group_id)
            except (TypeError, ValueError):
                raise ValueError("group_id must be an integer")
        return cls(
            id_=d["id"],
            regex=d["regex"],
            priority=d["priority"],
            group_id=group_id,
            permission=d.get("permission"),
        )
