from __future__ import annotations

from datetime import datetime
from typing import Any
from mlflow_oidc_auth.entities import ExperimentPermission, RegisteredModelPermission, ScorerPermission, Group


def _parse_optional_datetime(value: Any) -> datetime | None:
    """Parse an optional datetime from JSON-ish inputs.

    Accepts:
    - None
    - datetime
    - ISO 8601 strings (optionally ending with 'Z')
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        candidate = value
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        return datetime.fromisoformat(candidate)
    raise TypeError(f"Unsupported datetime value type: {type(value).__name__}")


class User:
    def __init__(
        self,
        id_: int | None = None,
        username: str | None = None,
        password_hash: str | None = None,
        password_expiration=None,
        is_admin: bool = False,
        is_service_account: bool = False,
        display_name: str | None = None,
        experiment_permissions=None,
        registered_model_permissions=None,
        scorer_permissions=None,
        groups=None,
    ):
        # Provide sensible defaults so tests can construct User with partial data.
        self._id = id_
        self._username = username
        self._password_hash = password_hash
        self._password_expiration = password_expiration
        self._is_admin = is_admin
        self._is_service_account = is_service_account
        self._experiment_permissions = experiment_permissions or []
        self._registered_model_permissions = registered_model_permissions or []
        self._scorer_permissions = scorer_permissions or []
        self._display_name = display_name
        self._groups = groups or []

    @property
    def id(self):
        return self._id

    @property
    def username(self):
        return self._username

    @property
    def password_hash(self):
        return self._password_hash

    @property
    def password_expiration(self):
        return self._password_expiration

    @password_expiration.setter
    def password_expiration(self, password_expiration):
        self._password_expiration = password_expiration

    @property
    def is_admin(self):
        return self._is_admin

    @is_admin.setter
    def is_admin(self, is_admin):
        self._is_admin = is_admin

    @property
    def is_service_account(self):
        return self._is_service_account

    @is_service_account.setter
    def is_service_account(self, is_service_account):
        self._is_service_account = is_service_account

    @property
    def experiment_permissions(self):
        return self._experiment_permissions

    @experiment_permissions.setter
    def experiment_permissions(self, experiment_permissions):
        self._experiment_permissions = experiment_permissions

    @property
    def registered_model_permissions(self):
        return self._registered_model_permissions

    @registered_model_permissions.setter
    def registered_model_permissions(self, registered_model_permissions):
        self._registered_model_permissions = registered_model_permissions

    @property
    def scorer_permissions(self):
        return self._scorer_permissions

    @scorer_permissions.setter
    def scorer_permissions(self, scorer_permissions):
        self._scorer_permissions = scorer_permissions

    @property
    def display_name(self):
        return self._display_name

    @display_name.setter
    def display_name(self, display_name):
        self._display_name = display_name

    @property
    def groups(self):
        return self._groups

    @groups.setter
    def groups(self, groups):
        self._groups = groups

    def to_json(self):
        return {
            "id": self.id,
            "username": self.username,
            "is_admin": self.is_admin,
            "is_service_account": self.is_service_account,
            "experiment_permissions": [p.to_json() for p in self.experiment_permissions],
            "registered_model_permissions": [p.to_json() for p in self.registered_model_permissions],
            "scorer_permissions": [p.to_json() for p in self.scorer_permissions],
            "password_expiration": self.password_expiration.isoformat() if self.password_expiration else None,
            "display_name": self.display_name,
            "groups": [g.to_json() for g in self.groups] if self.groups else [],
        }

    def __delattr__(self, name: str) -> None:
        """Allow tests to delete certain runtime attributes (used in tests).

        If a test deletes a collection-like attribute (e.g. 'registered_model_permissions'),
        reset it to an empty list instead of raising AttributeError from the property.
        """
        if name in ("experiment_permissions", "registered_model_permissions", "groups"):
            # reset to empty list
            object.__setattr__(self, f"_{name}", [])
            return
        # allow deleting other attributes normally
        object.__delattr__(self, name)

    @classmethod
    def from_json(cls, dictionary):
        return cls(
            id_=dictionary.get("id"),
            username=dictionary.get("username"),
            display_name=dictionary.get("display_name"),
            password_hash="REDACTED",
            password_expiration=_parse_optional_datetime(dictionary.get("password_expiration")),
            is_admin=bool(dictionary.get("is_admin", False)),
            is_service_account=dictionary.get("is_service_account", False),
            experiment_permissions=[ExperimentPermission.from_json(p) for p in dictionary.get("experiment_permissions", [])],
            registered_model_permissions=[RegisteredModelPermission.from_json(p) for p in dictionary.get("registered_model_permissions", [])],
            scorer_permissions=[ScorerPermission.from_json(p) for p in dictionary.get("scorer_permissions", [])],
            groups=[Group.from_json(g) for g in dictionary.get("groups", [])],
        )


class UserGroup:
    def __init__(self, user_id, group_id):
        self._user_id = user_id
        self._group_id = group_id

    @property
    def user_id(self):
        return self._user_id

    @property
    def group_id(self):
        return self._group_id

    def to_json(self):
        return {
            "user_id": self.user_id,
            "group_id": self.group_id,
        }

    @classmethod
    def from_json(cls, dictionary):
        user_id = dictionary["user_id"]
        group_id = dictionary["group_id"]
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            raise ValueError("user_id must be an integer")
        try:
            group_id = int(group_id)
        except (TypeError, ValueError):
            raise ValueError("group_id must be an integer")
        return cls(
            user_id=user_id,
            group_id=group_id,
        )
