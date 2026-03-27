"""Experiment group permission repository."""

from typing import List

from mlflow_oidc_auth.db.models import SqlExperimentGroupPermission
from mlflow_oidc_auth.entities import ExperimentPermission
from mlflow_oidc_auth.repository._base import BaseGroupPermissionRepository


class ExperimentPermissionGroupRepository(BaseGroupPermissionRepository[SqlExperimentGroupPermission, ExperimentPermission]):
    model_class = SqlExperimentGroupPermission
    resource_id_attr = "experiment_id"

    # -- Backward-compatible alias for the private helper ---------------------
    _get_experiment_group_permission = BaseGroupPermissionRepository._get_group_permission_or_none

    # -- Alias matching original method name ----------------------------------

    def get_group_permission_for_user_experiment(self, experiment_id: str, username: str) -> ExperimentPermission:
        """Get the highest group permission for a user on an experiment."""
        return self.get_group_permission_for_user_resource(experiment_id, username)

    def list_groups_for_experiment(self, experiment_id: str) -> List[tuple[str, str]]:
        """List groups that have explicit permissions for an experiment."""
        return self.list_groups_for_resource(experiment_id)
