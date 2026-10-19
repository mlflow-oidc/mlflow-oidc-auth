"""Experiment permission repository."""

from mlflow_oidc_auth import permission_kinds
from mlflow_oidc_auth.db.models import SqlExperimentPermission
from mlflow_oidc_auth.entities import ExperimentPermission
from mlflow_oidc_auth.repository._base import BaseUserPermissionRepository


class ExperimentPermissionRepository(BaseUserPermissionRepository[SqlExperimentPermission, ExperimentPermission]):
    grant_kind = permission_kinds.EXPERIMENT
    resource_id_attr = "experiment_id"

    # -- Backward-compatible alias for the private helper ---------------------
    _get_experiment_permission = BaseUserPermissionRepository._get_permission

    def list_permissions_for_experiment(self, experiment_id: str):
        """List all experiment permissions for a given experiment."""
        return self.list_permissions_for_resource(experiment_id)
