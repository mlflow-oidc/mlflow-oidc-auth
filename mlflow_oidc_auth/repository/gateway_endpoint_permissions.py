"""Gateway endpoint permission repository."""

from mlflow_oidc_auth.db.models import SqlGatewayEndpointPermission
from mlflow_oidc_auth.entities import GatewayEndpointPermission
from mlflow_oidc_auth.repository._base import BaseUserPermissionRepository


class GatewayEndpointPermissionRepository(
    BaseUserPermissionRepository[
        SqlGatewayEndpointPermission, GatewayEndpointPermission
    ]
):
    model_class = SqlGatewayEndpointPermission
    resource_id_attr = "endpoint_id"
