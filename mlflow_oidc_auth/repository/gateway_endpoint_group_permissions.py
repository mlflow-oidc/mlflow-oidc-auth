"""Gateway endpoint group permission repository."""

from typing import List

from mlflow_oidc_auth.db.models import SqlGatewayEndpointGroupPermission
from mlflow_oidc_auth.entities import GatewayEndpointPermission
from mlflow_oidc_auth.repository._base import BaseGroupPermissionRepository


class GatewayEndpointGroupPermissionRepository(
    BaseGroupPermissionRepository[
        SqlGatewayEndpointGroupPermission, GatewayEndpointPermission
    ]
):
    model_class = SqlGatewayEndpointGroupPermission
    resource_id_attr = "endpoint_id"

    # -- Custom methods matching original API ---------------------------------

    def get_group_permission_for_user(
        self, endpoint_id: str, group_name: str
    ) -> GatewayEndpointPermission:
        with self._Session() as session:
            perm = self._get_group_permission(session, endpoint_id, group_name)
            return perm.to_mlflow_entity()

    def list_groups_for_endpoint(self, endpoint_id: str) -> List[tuple[str, str]]:
        return self.list_groups_for_resource(endpoint_id)
