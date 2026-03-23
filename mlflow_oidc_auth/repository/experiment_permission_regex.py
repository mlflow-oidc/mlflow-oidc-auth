"""Experiment regex permission repository."""

from mlflow_oidc_auth.db.models import SqlExperimentRegexPermission
from mlflow_oidc_auth.entities import ExperimentRegexPermission
from mlflow_oidc_auth.repository._base import BaseRegexPermissionRepository


class ExperimentPermissionRegexRepository(
    BaseRegexPermissionRepository[
        SqlExperimentRegexPermission, ExperimentRegexPermission
    ]
):
    model_class = SqlExperimentRegexPermission

    # -- Backward-compatible alias for the private helper ---------------------
    _get_experiment_regex_permission = (
        BaseRegexPermissionRepository._get_regex_permission
    )
