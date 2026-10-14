"""User pattern grants on registered models and on prompts, which share one table."""

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.db.models import SqlRegisteredModelRegexPermission
from mlflow_oidc_auth.entities import RegisteredModelRegexPermission
from mlflow_oidc_auth.repository._base import BaseRegexPermissionRepository


class RegisteredModelPermissionRegexRepository(BaseRegexPermissionRepository[SqlRegisteredModelRegexPermission, RegisteredModelRegexPermission]):
    model_class = SqlRegisteredModelRegexPermission
    extra_filter = permission_kinds.REGISTERED_MODEL.extra_filter


class PromptPermissionRegexRepository(RegisteredModelPermissionRegexRepository):
    extra_filter = permission_kinds.PROMPT.extra_filter
