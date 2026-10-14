"""Gateway endpoint group regex permission repository."""

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.db.models import SqlGatewayEndpointGroupRegexPermission
from mlflow_oidc_auth.entities import GatewayEndpointGroupRegexPermission
from mlflow_oidc_auth.repository._base import BaseGroupRegexPermissionRepository


class GatewayEndpointPermissionGroupRegexRepository(
    BaseGroupRegexPermissionRepository[SqlGatewayEndpointGroupRegexPermission, GatewayEndpointGroupRegexPermission]
):
    grant_kind = permission_kinds.GATEWAY_ENDPOINT
