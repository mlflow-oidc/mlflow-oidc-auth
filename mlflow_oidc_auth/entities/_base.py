from dataclasses import dataclass, asdict
from typing import Optional, Any, Dict


@dataclass
class RegexPermissionBase:
    id: Any
    regex: str
    priority: int
    permission: str
    user_id: Optional[int] = None
    group_id: Optional[int] = None

    def to_json(self) -> Dict[str, Any]:
        data = asdict(self)
        # Omit None values to keep JSON compact and backward compatible
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_json(cls, dictionary: dict):
        """
        Construct from a dict. Normalizes types and fills defaults for optional fields.
        Raises ValueError if any required field is missing.
        """
        try:
            id_ = dictionary["id"]
            regex = dictionary["regex"]
            priority = dictionary["priority"]
            permission = dictionary["permission"]
        except KeyError as e:
            raise ValueError(f"Missing required field: {e.args[0]}")
        user_id = dictionary.get("user_id")
        group_id = dictionary.get("group_id")
        # Cast user_id/group_id to int when provided (accept numeric strings too)
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
            id=id_,
            regex=regex,
            priority=priority,
            permission=permission,
            user_id=user_id,
            group_id=group_id,
        )


@dataclass
class PermissionBase:
    instance: str
    permission: str
    user_id: Optional[int] = None
    group_id: Optional[int] = None

    def to_json(self) -> dict:
        # Include explicit None values for user_id/group_id for backward compatibility
        return {
            "instance": self.instance,
            "permission": self.permission,
            "user_id": self.user_id,
            "group_id": self.group_id,
        }
    