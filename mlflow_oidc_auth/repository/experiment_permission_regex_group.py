"""Experiment group regex permission repository."""

from mlflow_oidc_auth.db.models import SqlExperimentGroupRegexPermission
from mlflow_oidc_auth.entities import ExperimentGroupRegexPermission
from mlflow_oidc_auth.repository._base import BaseGroupRegexPermissionRepository


class ExperimentPermissionGroupRegexRepository(
    BaseGroupRegexPermissionRepository[
        SqlExperimentGroupRegexPermission, ExperimentGroupRegexPermission
    ]
):
    model_class = SqlExperimentGroupRegexPermission

    # -- Backward-compatible alias for the private helper ---------------------
    _get_experiment_group_regex_permission = (
        BaseGroupRegexPermissionRepository._get_group_regex_permission
    )
