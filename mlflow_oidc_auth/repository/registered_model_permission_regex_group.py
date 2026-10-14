"""Group pattern grants on registered models and on prompts, which share one table."""

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.db.models import SqlRegisteredModelGroupRegexPermission
from mlflow_oidc_auth.entities import RegisteredModelGroupRegexPermission
from mlflow_oidc_auth.repository._base import BaseGroupRegexPermissionRepository


class RegisteredModelGroupRegexPermissionRepository(
    BaseGroupRegexPermissionRepository[SqlRegisteredModelGroupRegexPermission, RegisteredModelGroupRegexPermission]
):
    model_class = SqlRegisteredModelGroupRegexPermission
    extra_filter = permission_kinds.REGISTERED_MODEL.extra_filter


class PromptGroupRegexPermissionRepository(RegisteredModelGroupRegexPermissionRepository):
    extra_filter = permission_kinds.PROMPT.extra_filter
