from dataclasses import dataclass
from typing import Optional, Any, Dict

from ._base import PermissionBase, RegexPermissionBase


@dataclass
class GatewayModelDefinitionPermission(PermissionBase):
    def __init__(self, model_definition_id: str, permission: str, user_id: Optional[int] = None, group_id: Optional[int] = None):
        super().__init__(instance=model_definition_id, permission=permission, user_id=user_id, group_id=group_id)

    @property
    def model_definition_id(self) -> str:
        return self.instance

    def to_json(self) -> Dict[str, Any]:
        d = super().to_json()
        d["model_definition_id"] = d.pop("instance")
        return d

    @classmethod
    def from_json(cls, d: Dict[str, Any]) -> "GatewayModelDefinitionPermission":
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
            model_definition_id=d["model_definition_id"],
            permission=d["permission"],
            user_id=user_id,
            group_id=group_id,
        )


@dataclass(init=False)
class GatewayModelDefinitionRegexPermission(RegexPermissionBase):
    def __init__(self, id_, regex, priority, user_id, permission):
        super().__init__(
            id=id_,
            regex=regex,
            priority=priority,
            permission=permission,
            user_id=user_id,
        )

    @classmethod
    def from_json(cls, d: Dict[str, Any]) -> "GatewayModelDefinitionRegexPermission":
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
class GatewayModelDefinitionGroupRegexPermission(RegexPermissionBase):
    def __init__(self, id_, regex, priority, group_id, permission):
        super().__init__(
            id=id_,
            regex=regex,
            priority=priority,
            permission=permission,
            group_id=group_id,
        )

    @classmethod
    def from_json(cls, d: Dict[str, Any]) -> "GatewayModelDefinitionGroupRegexPermission":
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
