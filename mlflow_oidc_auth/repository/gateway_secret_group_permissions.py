"""Gateway secret group permission repository."""

from typing import List

from mlflow_oidc_auth.db.models import SqlGatewaySecretGroupPermission
from mlflow_oidc_auth.entities import GatewaySecretPermission
from mlflow_oidc_auth.repository._base import BaseGroupPermissionRepository


class GatewaySecretGroupPermissionRepository(
    BaseGroupPermissionRepository[
        SqlGatewaySecretGroupPermission, GatewaySecretPermission
    ]
):
    model_class = SqlGatewaySecretGroupPermission
    resource_id_attr = "secret_id"

    # -- Custom methods matching original API ---------------------------------

    def get_group_permission_for_user(
        self, secret_id: str, group_name: str
    ) -> GatewaySecretPermission:
        with self._Session() as session:
            perm = self._get_group_permission(session, secret_id, group_name)
            return perm.to_mlflow_entity()

    def list_groups_for_secret(self, secret_id: str) -> List[tuple[str, str]]:
        return self.list_groups_for_resource(secret_id)
