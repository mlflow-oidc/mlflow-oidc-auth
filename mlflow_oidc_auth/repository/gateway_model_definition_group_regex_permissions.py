"""Gateway model definition group regex permission repository."""

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.db.models import SqlGatewayModelDefinitionGroupRegexPermission
from mlflow_oidc_auth.entities import GatewayModelDefinitionGroupRegexPermission
from mlflow_oidc_auth.repository._base import BaseGroupRegexPermissionRepository


class GatewayModelDefinitionPermissionGroupRegexRepository(
    BaseGroupRegexPermissionRepository[
        SqlGatewayModelDefinitionGroupRegexPermission,
        GatewayModelDefinitionGroupRegexPermission,
    ]
):
    grant_kind = permission_kinds.GATEWAY_MODEL_DEFINITION
