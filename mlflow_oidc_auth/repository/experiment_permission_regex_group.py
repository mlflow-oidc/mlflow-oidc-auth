"""Experiment group regex permission repository."""

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.db.models import SqlExperimentGroupRegexPermission
from mlflow_oidc_auth.entities import ExperimentGroupRegexPermission
from mlflow_oidc_auth.repository._base import BaseGroupRegexPermissionRepository


class ExperimentPermissionGroupRegexRepository(BaseGroupRegexPermissionRepository[SqlExperimentGroupRegexPermission, ExperimentGroupRegexPermission]):
    grant_kind = permission_kinds.EXPERIMENT

    # -- Backward-compatible alias for the private helper ---------------------
    _get_experiment_group_regex_permission = BaseGroupRegexPermissionRepository._get_group_regex_permission
