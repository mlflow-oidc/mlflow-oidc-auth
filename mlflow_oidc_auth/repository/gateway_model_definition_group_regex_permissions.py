"""Gateway model definition group regex permission repository."""

from mlflow_oidc_auth.db.models import SqlGatewayModelDefinitionGroupRegexPermission
from mlflow_oidc_auth.entities import GatewayModelDefinitionGroupRegexPermission
from mlflow_oidc_auth.repository._base import BaseGroupRegexPermissionRepository


class GatewayModelDefinitionPermissionGroupRegexRepository(
    BaseGroupRegexPermissionRepository[
        SqlGatewayModelDefinitionGroupRegexPermission,
        GatewayModelDefinitionGroupRegexPermission,
    ]
):
    model_class = SqlGatewayModelDefinitionGroupRegexPermission
