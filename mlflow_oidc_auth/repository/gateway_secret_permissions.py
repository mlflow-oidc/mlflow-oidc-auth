"""Gateway secret permission repository."""

from mlflow_oidc_auth.db.models import SqlGatewaySecretPermission
from mlflow_oidc_auth.entities import GatewaySecretPermission
from mlflow_oidc_auth.repository._base import BaseUserPermissionRepository


class GatewaySecretPermissionRepository(
    BaseUserPermissionRepository[SqlGatewaySecretPermission, GatewaySecretPermission]
):
    model_class = SqlGatewaySecretPermission
    resource_id_attr = "secret_id"
