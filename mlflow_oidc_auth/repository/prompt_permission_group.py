"""Group grants on prompts.

Prompts are registered models: their group grants live in the registered model group grant table,
flagged ``prompt=True``.
"""

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.db.models import SqlRegisteredModelGroupPermission
from mlflow_oidc_auth.entities import RegisteredModelPermission
from mlflow_oidc_auth.repository._base import BaseGroupPermissionRepository


class PromptPermissionGroupRepository(BaseGroupPermissionRepository[SqlRegisteredModelGroupPermission, RegisteredModelPermission]):
    model_class = SqlRegisteredModelGroupPermission
    resource_id_attr = "name"
    workspace_scoped = True  # MLflow keeps these resources unique per (workspace, name)
    extra_filter = permission_kinds.PROMPT.extra_filter
