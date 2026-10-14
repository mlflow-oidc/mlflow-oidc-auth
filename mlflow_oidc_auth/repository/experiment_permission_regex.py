"""Experiment regex permission repository."""

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.db.models import SqlExperimentRegexPermission
from mlflow_oidc_auth.entities import ExperimentRegexPermission
from mlflow_oidc_auth.repository._base import BaseRegexPermissionRepository


class ExperimentPermissionRegexRepository(BaseRegexPermissionRepository[SqlExperimentRegexPermission, ExperimentRegexPermission]):
    grant_kind = permission_kinds.EXPERIMENT

    # -- Backward-compatible alias for the private helper ---------------------
    _get_experiment_regex_permission = BaseRegexPermissionRepository._get_regex_permission
