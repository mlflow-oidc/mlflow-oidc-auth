"""Gateway secret group regex permission repository."""

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.db.models import SqlGatewaySecretGroupRegexPermission
from mlflow_oidc_auth.entities import GatewaySecretGroupRegexPermission
from mlflow_oidc_auth.repository._base import BaseGroupRegexPermissionRepository


class GatewaySecretPermissionGroupRegexRepository(BaseGroupRegexPermissionRepository[SqlGatewaySecretGroupRegexPermission, GatewaySecretGroupRegexPermission]):
    grant_kind = permission_kinds.GATEWAY_VAULT
