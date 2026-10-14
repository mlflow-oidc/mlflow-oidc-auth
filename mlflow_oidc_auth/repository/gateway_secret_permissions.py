"""Gateway secret permission repository."""

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.db.models import SqlGatewaySecretPermission
from mlflow_oidc_auth.entities import GatewaySecretPermission
from mlflow_oidc_auth.repository._base import BaseUserPermissionRepository


class GatewaySecretPermissionRepository(BaseUserPermissionRepository[SqlGatewaySecretPermission, GatewaySecretPermission]):
    grant_kind = permission_kinds.GATEWAY_VAULT
    resource_id_attr = "secret_id"
