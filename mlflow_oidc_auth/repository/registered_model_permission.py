"""Registered model permission repository."""

from typing import List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.db.models import SqlRegisteredModelPermission
from mlflow_oidc_auth.entities import RegisteredModelPermission
from mlflow_oidc_auth.repository._base import BaseUserPermissionRepository


class RegisteredModelPermissionRepository(
    BaseUserPermissionRepository[
        SqlRegisteredModelPermission, RegisteredModelPermission
    ]
):
    model_class = SqlRegisteredModelPermission
    resource_id_attr = "name"

    # --- Aliases preserving backward-compatible method names -----------------

    def create(
        self, name: str, username: str, permission: str
    ) -> RegisteredModelPermission:
        return self.grant_permission(name, username, permission)

    def get(self, name: str, username: str) -> RegisteredModelPermission:
        return self.get_permission(name, username)

    def list_for_user(self, username: str) -> List[RegisteredModelPermission]:
        return self.list_permissions_for_user(username)

    def update(
        self, name: str, username: str, permission: str
    ) -> RegisteredModelPermission:
        return self.update_permission(name, username, permission)

    def delete(self, name: str, username: str) -> None:
        return self.revoke_permission(name, username)

    # --- Custom rename: raises when nothing is found -------------------------

    def rename(self, old_name: str, new_name: str) -> None:
        with self._Session() as session:
            perms = (
                session.query(self.model_class)
                .filter(self.model_class.name == old_name)
                .all()
            )
            if not perms:
                raise MlflowException(
                    f"No registered model permissions found for name: {old_name}",
                    RESOURCE_DOES_NOT_EXIST,
                )
            for perm in perms:
                perm.name = new_name
            session.flush()
