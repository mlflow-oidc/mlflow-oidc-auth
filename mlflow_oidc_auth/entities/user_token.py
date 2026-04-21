from __future__ import annotations

from datetime import datetime


class UserToken:
    def __init__(
        self,
        id_: int | None = None,
        user_id: int | None = None,
        name: str | None = None,
        token_hash: str | None = None,
        created_at: datetime | None = None,
        expires_at: datetime | None = None,
        last_used_at: datetime | None = None,
    ):
        self._id = id_
        self._user_id = user_id
        self._name = name
        self._token_hash = token_hash
        self._created_at = created_at
        self._expires_at = expires_at
        self._last_used_at = last_used_at

    @property
    def id(self):
        return self._id

    @property
    def user_id(self):
        return self._user_id

    @property
    def name(self):
        return self._name

    @property
    def token_hash(self):
        return self._token_hash

    @property
    def created_at(self):
        return self._created_at

    @property
    def expires_at(self):
        return self._expires_at

    @expires_at.setter
    def expires_at(self, expires_at):
        self._expires_at = expires_at

    @property
    def last_used_at(self):
        return self._last_used_at

    @last_used_at.setter
    def last_used_at(self, last_used_at):
        self._last_used_at = last_used_at

    def to_json(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }

    @classmethod
    def from_json(cls, dictionary):
        from mlflow_oidc_auth.entities.user import _parse_optional_datetime

        return cls(
            id_=dictionary.get("id"),
            user_id=dictionary.get("user_id"),
            name=dictionary.get("name"),
            token_hash=dictionary.get("token_hash"),
            created_at=_parse_optional_datetime(dictionary.get("created_at")),
            expires_at=_parse_optional_datetime(dictionary.get("expires_at")),
            last_used_at=_parse_optional_datetime(dictionary.get("last_used_at")),
        )
