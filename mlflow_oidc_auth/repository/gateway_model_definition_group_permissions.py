"""Gateway model definition group permission repository."""

from typing import List

from mlflow_oidc_auth.db.models import SqlGatewayModelDefinitionGroupPermission
from mlflow_oidc_auth.entities import GatewayModelDefinitionPermission
from mlflow_oidc_auth.repository._base import BaseGroupPermissionRepository


class GatewayModelDefinitionGroupPermissionRepository(
    BaseGroupPermissionRepository[SqlGatewayModelDefinitionGroupPermission, GatewayModelDefinitionPermission]
):
    model_class = SqlGatewayModelDefinitionGroupPermission
    resource_id_attr = "model_definition_id"

    # -- Custom methods matching original API ---------------------------------

    def get_group_permission_for_user(self, model_definition_id: str, group_name: str) -> GatewayModelDefinitionPermission:
        with self._Session() as session:
            perm = self._get_group_permission(session, model_definition_id, group_name)
            return perm.to_mlflow_entity()

    def list_groups_for_model_definition(self, model_definition_id: str) -> List[tuple[str, str]]:
        return self.list_groups_for_resource(model_definition_id)
