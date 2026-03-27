"""Scorer group regex permission repository."""

from mlflow_oidc_auth.db.models import SqlScorerGroupRegexPermission
from mlflow_oidc_auth.entities import ScorerGroupRegexPermission
from mlflow_oidc_auth.repository._base import BaseGroupRegexPermissionRepository


class ScorerPermissionGroupRegexRepository(BaseGroupRegexPermissionRepository[SqlScorerGroupRegexPermission, ScorerGroupRegexPermission]):
    model_class = SqlScorerGroupRegexPermission
