"""User pattern grants on registered models and on prompts, which share one table."""

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.db.models import SqlRegisteredModelRegexPermission
from mlflow_oidc_auth.entities import RegisteredModelRegexPermission
from mlflow_oidc_auth.repository._base import BaseRegexPermissionRepository


class RegisteredModelPermissionRegexRepository(BaseRegexPermissionRepository[SqlRegisteredModelRegexPermission, RegisteredModelRegexPermission]):
    grant_kind = permission_kinds.REGISTERED_MODEL


class PromptPermissionRegexRepository(RegisteredModelPermissionRegexRepository):
    grant_kind = permission_kinds.PROMPT
