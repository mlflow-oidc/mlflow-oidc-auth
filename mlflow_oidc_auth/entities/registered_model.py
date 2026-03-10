from dataclasses import dataclass
from typing import Optional, Any, Dict

from ._base import RegexPermissionBase


@dataclass
class RegisteredModelPermission:
    """Represents a registered-model level permission with optional prompt flag."""

    name: str
    permission: str
    user_id: Optional[int] = None
    group_id: Optional[int] = None
    prompt: bool = False

    def to_json(self) -> Dict[str, Any]:
        # Keep explicit None for user_id/group_id for backward compatibility
        return {
            "name": self.name,
            "user_id": self.user_id,
            "permission": self.permission,
            "group_id": self.group_id,
            "prompt": bool(self.prompt),
        }

    @classmethod
    def from_json(cls, dictionary: Dict[str, Any]) -> "RegisteredModelPermission":
        user_id = dictionary.get("user_id")
        group_id = dictionary.get("group_id")
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
            name=dictionary["name"],
            permission=dictionary["permission"],
            user_id=user_id,
            group_id=group_id,
            prompt=bool(dictionary.get("prompt", False)),
        )


from dataclasses import dataclass


@dataclass(init=False)
class RegisteredModelGroupRegexPermission(RegexPermissionBase):
    def __init__(
        self,
        id_,
        regex,
        priority,
        group_id,
        permission,
        prompt=False,
    ):
        super().__init__(
            id=id_,
            regex=regex,
            priority=priority,
            permission=permission,
            group_id=group_id,
        )
        self._prompt = bool(prompt)

    @property
    def prompt(self):
        return self._prompt

    def to_json(self):
        data = super().to_json()
        data["prompt"] = self.prompt
        return data

    @classmethod
    def from_json(cls, dictionary):
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
            prompt=bool(dictionary.get("prompt", False)),
        )


@dataclass(init=False)
class RegisteredModelRegexPermission(RegexPermissionBase):
    def __init__(
        self,
        id_,
        regex,
        priority,
        user_id,
        permission,
        prompt=False,
    ):
        super().__init__(
            id=id_,
            regex=regex,
            priority=priority,
            permission=permission,
            user_id=user_id,
        )
        self._prompt = bool(prompt)

    @property
    def prompt(self):
        return self._prompt

    @prompt.setter
    def prompt(self, prompt):
        self._prompt = prompt

    def to_json(self):
        data = super().to_json()
        data["prompt"] = self.prompt
        return data

    @classmethod
    def from_json(cls, dictionary):
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
            permission=dictionary["permission"],
            prompt=bool(dictionary.get("prompt", False)),
        )
