"""Registered model group permission repository.

Uses custom method names (create/get/get_for_user/list_for_user/update/delete)
and relies on GroupRepository for user-group listing, so methods are individually
delegated or overridden rather than simply inherited.
"""

from typing import List, Optional

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGroup, SqlRegisteredModelGroupPermission
from mlflow_oidc_auth.entities import RegisteredModelPermission
from mlflow_oidc_auth.permissions import _validate_permission, compare_permissions
from mlflow_oidc_auth.repository._base import BaseGroupPermissionRepository
from mlflow_oidc_auth.repository import GroupRepository
from mlflow_oidc_auth.repository.utils import get_group, get_user, list_user_groups


class RegisteredModelPermissionGroupRepository(BaseGroupPermissionRepository[SqlRegisteredModelGroupPermission, RegisteredModelPermission]):
    model_class = SqlRegisteredModelGroupPermission
    resource_id_attr = "name"

    def __init__(self, session_maker):
        super().__init__(session_maker)
        self._group_repo = GroupRepository(session_maker)

    # -- Aliases mapping custom names → base names ----------------------------

    def create(self, group_name: str, name: str, permission: str):
        return self.grant_group_permission(group_name, name, permission)

    def get(self, group_name: str) -> List[RegisteredModelPermission]:
        return self.list_permissions_for_group(group_name)

    def update(self, group_name: str, name: str, permission: str):
        return self.update_group_permission(group_name, name, permission)

    def delete(self, group_name: str, name: str):
        return self.revoke_group_permission(group_name, name)

    # -- Custom rename: raises when nothing is found --------------------------

    def rename(self, old_name: str, new_name: str):
        with self._Session() as session:
            perms = session.query(self.model_class).filter(self.model_class.name == old_name).all()
            if not perms:
                raise MlflowException(
                    f"No registered model group permissions found for name: {old_name}",
                    RESOURCE_DOES_NOT_EXIST,
                )
            for perm in perms:
                perm.name = new_name
            session.flush()

    # -- list_groups_for_model: prompt=False filter ----------------------------

    def list_groups_for_model(self, name: str) -> List[tuple[str, str]]:
        """List groups that have explicit permissions for a registered model.

        Returns pairs of (group_name, permission).
        """
        with self._Session() as session:
            rows = (
                session.query(SqlGroup.group_name, self.model_class.permission)
                .join(self.model_class, self.model_class.group_id == SqlGroup.id)
                .filter(self.model_class.name == name)
                .filter(self.model_class.prompt == False)
                .all()
            )
            return [(str(group_name), str(permission)) for group_name, permission in rows]

    # -- get_for_user uses GroupRepository ------------------------------------

    def get_for_user(self, name: str, username: str) -> RegisteredModelPermission:
        with self._Session() as session:
            user_groups = self._group_repo.list_groups_for_user(username)
            user_perms: Optional[SqlRegisteredModelGroupPermission] = None
            for ug in user_groups:
                perms = self._get_group_permission_or_none(session, name, ug)
                if perms is None:
                    continue
                if user_perms is None:
                    user_perms = perms
                    continue
                try:
                    if compare_permissions(str(user_perms.permission), str(perms.permission)):
                        user_perms = perms
                except AttributeError:
                    user_perms = perms
            try:
                if user_perms is not None:
                    return user_perms.to_mlflow_entity()
                else:
                    raise MlflowException(
                        f"Registered model permission with name={name} and username={username} not found",
                        RESOURCE_DOES_NOT_EXIST,
                    )
            except AttributeError:
                raise MlflowException(
                    f"Registered model permission with name={name} and username={username} not found",
                    RESOURCE_DOES_NOT_EXIST,
                )

    # -- list_for_user uses list_user_groups directly -------------------------

    def list_for_user(self, username: str) -> List[RegisteredModelPermission]:
        with self._Session() as session:
            user = get_user(session, username=username)
            user_groups = list_user_groups(session, user)
            perms = session.query(self.model_class).filter(self.model_class.group_id.in_([ug.group_id for ug in user_groups])).all()
            return [p.to_mlflow_entity() for p in perms]
