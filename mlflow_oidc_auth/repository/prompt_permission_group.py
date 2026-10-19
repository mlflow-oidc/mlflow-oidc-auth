"""Group grants on prompts.

Prompts are registered models: their group grants live in the registered model group grant table,
flagged ``prompt=True``.
"""

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.db.models import SqlRegisteredModelGroupPermission
from mlflow_oidc_auth.entities import RegisteredModelPermission
from mlflow_oidc_auth.repository._base import BaseGroupPermissionRepository


class PromptPermissionGroupRepository(BaseGroupPermissionRepository[SqlRegisteredModelGroupPermission, RegisteredModelPermission]):
    resource_id_attr = "name"
    grant_kind = permission_kinds.PROMPT
