"""Gateway endpoint regex permission repository.

Parameter order differs from the base class (``id`` comes first in
``get``, ``update`` and ``revoke``), so those methods are overridden.
"""

from mlflow_oidc_auth.db.models import SqlGatewayEndpointRegexPermission
from mlflow_oidc_auth.entities import GatewayEndpointRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository._base import BaseRegexPermissionRepository
from mlflow_oidc_auth.repository.utils import get_user, validate_regex


class GatewayEndpointPermissionRegexRepository(BaseRegexPermissionRepository[SqlGatewayEndpointRegexPermission, GatewayEndpointRegexPermission]):
    model_class = SqlGatewayEndpointRegexPermission

    # -- Parameter-order overrides --------------------------------------------

    def get(self, id: int, username: str) -> GatewayEndpointRegexPermission:  # type: ignore[override]
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_regex_permission(session, user.id, id)
            return perm.to_mlflow_entity()

    def update(self, id: int, regex: str, priority: int, permission: str, username: str) -> GatewayEndpointRegexPermission:  # type: ignore[override]
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_regex_permission(session, user.id, id)
            perm.priority = priority
            perm.permission = permission
            session.commit()
            return perm.to_mlflow_entity()

    def revoke(self, id: int, username: str) -> None:  # type: ignore[override]
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_regex_permission(session, user.id, id)
            session.delete(perm)
            session.commit()
            return None
