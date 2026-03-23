"""Scorer regex permission repository.

Parameter order differs from the base class (``id`` comes first in
``update`` and ``revoke``), so those methods are overridden.
"""

from typing import List

from mlflow_oidc_auth.db.models import SqlScorerRegexPermission
from mlflow_oidc_auth.entities import ScorerRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository._base import BaseRegexPermissionRepository
from mlflow_oidc_auth.repository.utils import get_user, validate_regex


class ScorerPermissionRegexRepository(
    BaseRegexPermissionRepository[SqlScorerRegexPermission, ScorerRegexPermission]
):
    model_class = SqlScorerRegexPermission

    # -- Parameter-order overrides --------------------------------------------

    def update(
        self, id: int, regex: str, priority: int, permission: str, username: str
    ) -> ScorerRegexPermission:  # type: ignore[override]
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_regex_permission(session, user.id, id)
            perm.regex = regex
            perm.priority = priority
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke(self, id: int, username: str) -> None:  # type: ignore[override]
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_regex_permission(session, user.id, id)
            session.delete(perm)
            session.commit()
