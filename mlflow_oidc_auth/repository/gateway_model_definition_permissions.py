"""Gateway model definition permission repository."""

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.db.models import SqlGatewayModelDefinitionPermission
from mlflow_oidc_auth.entities import GatewayModelDefinitionPermission
from mlflow_oidc_auth.repository._base import BaseUserPermissionRepository


class GatewayModelDefinitionPermissionRepository(BaseUserPermissionRepository[SqlGatewayModelDefinitionPermission, GatewayModelDefinitionPermission]):
    grant_kind = permission_kinds.GATEWAY_MODEL_DEFINITION
    resource_id_attr = "model_definition_id"
