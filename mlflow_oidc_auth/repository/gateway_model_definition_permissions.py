"""Gateway model definition permission repository."""

from mlflow_oidc_auth.db.models import SqlGatewayModelDefinitionPermission
from mlflow_oidc_auth.entities import GatewayModelDefinitionPermission
from mlflow_oidc_auth.repository._base import BaseUserPermissionRepository


class GatewayModelDefinitionPermissionRepository(
    BaseUserPermissionRepository[
        SqlGatewayModelDefinitionPermission, GatewayModelDefinitionPermission
    ]
):
    model_class = SqlGatewayModelDefinitionPermission
    resource_id_attr = "model_definition_id"
