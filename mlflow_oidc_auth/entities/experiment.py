from dataclasses import dataclass
from ._base import PermissionBase, RegexPermissionBase


class ExperimentPermission(PermissionBase):
    def __init__(self, experiment_id, permission, user_id=None, group_id=None):
        super().__init__(instance=experiment_id, permission=permission, user_id=user_id, group_id=group_id)

    @property
    def experiment_id(self):
        return self.instance

    def to_json(self):
        d = super().to_json()
        d["experiment_id"] = d.pop("instance")
        return d

    @classmethod
    def from_json(cls, d):
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
            experiment_id=d["experiment_id"],
            permission=d["permission"],
            user_id=user_id,
            group_id=group_id,
        )


@dataclass(init=False)
class ExperimentGroupRegexPermission(RegexPermissionBase):
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
    def from_json(cls, dictionary: dict) -> "ExperimentGroupRegexPermission":
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


@dataclass(init=False)
class ExperimentRegexPermission(RegexPermissionBase):
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
    def from_json(cls, dictionary: dict) -> "ExperimentRegexPermission":
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
