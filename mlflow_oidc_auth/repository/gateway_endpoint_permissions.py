"""Gateway endpoint permission repository."""

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.db.models import SqlGatewayEndpointPermission
from mlflow_oidc_auth.entities import GatewayEndpointPermission
from mlflow_oidc_auth.repository._base import BaseUserPermissionRepository


class GatewayEndpointPermissionRepository(BaseUserPermissionRepository[SqlGatewayEndpointPermission, GatewayEndpointPermission]):
    grant_kind = permission_kinds.GATEWAY_ENDPOINT
    resource_id_attr = "endpoint_id"
