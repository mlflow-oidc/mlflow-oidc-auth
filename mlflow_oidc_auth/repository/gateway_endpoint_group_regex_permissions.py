"""Gateway endpoint group regex permission repository."""

from mlflow_oidc_auth.db.models import SqlGatewayEndpointGroupRegexPermission
from mlflow_oidc_auth.entities import GatewayEndpointGroupRegexPermission
from mlflow_oidc_auth.repository._base import BaseGroupRegexPermissionRepository


class GatewayEndpointPermissionGroupRegexRepository(
    BaseGroupRegexPermissionRepository[SqlGatewayEndpointGroupRegexPermission, GatewayEndpointGroupRegexPermission]
):
    model_class = SqlGatewayEndpointGroupRegexPermission
