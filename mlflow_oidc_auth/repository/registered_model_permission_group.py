from typing import List, Optional, Callable
from sqlalchemy.orm import Session

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.db.models import SqlGroup, SqlRegisteredModelGroupPermission
from mlflow_oidc_auth.entities import RegisteredModelPermission
from mlflow_oidc_auth.permissions import _validate_permission, compare_permissions
from mlflow_oidc_auth.repository import GroupRepository
from mlflow_oidc_auth.repository.utils import get_user, get_group, list_user_groups


class RegisteredModelPermissionGroupRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker
        self._group_repo = GroupRepository(session_maker)

    def _get_registered_model_group_permission(self, session: Session, name: str, group_name: str) -> Optional[SqlRegisteredModelGroupPermission]:
        group = session.query(SqlGroup).filter(SqlGroup.group_name == group_name).one_or_none()
        if group is None:
            return None
        return (
            session.query(SqlRegisteredModelGroupPermission)
            .filter(
                SqlRegisteredModelGroupPermission.name == name,
                SqlRegisteredModelGroupPermission.group_id == group.id,
            )
            .one_or_none()
        )

    def create(self, group_name: str, name: str, permission: str):
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = SqlRegisteredModelGroupPermission(name=name, group_id=group.id, permission=permission)
            session.add(perm)
            session.flush()
            return perm.to_mlflow_entity()

    def get(self, group_name: str) -> List[RegisteredModelPermission]:
        with self._Session() as session:
            group = get_group(session, group_name)
            perms = session.query(SqlRegisteredModelGroupPermission).filter(SqlRegisteredModelGroupPermission.group_id == group.id).all()
            return [p.to_mlflow_entity() for p in perms]

    def get_for_user(self, name: str, username: str) -> RegisteredModelPermission:
        with self._Session() as session:
            user_groups = self._group_repo.list_groups_for_user(username)
            user_perms: Optional[SqlRegisteredModelGroupPermission] = None
            for ug in user_groups:
                perms = self._get_registered_model_group_permission(session, name, ug)
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

    def list_for_user(self, username: str) -> List[RegisteredModelPermission]:
        with self._Session() as session:
            user = get_user(session, username=username)
            user_groups = list_user_groups(session, user)
            perms = (
                session.query(SqlRegisteredModelGroupPermission)
                .filter(SqlRegisteredModelGroupPermission.group_id.in_([ug.group_id for ug in user_groups]))
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def update(self, group_name: str, name: str, permission: str):
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = (
                session.query(SqlRegisteredModelGroupPermission)
                .filter(SqlRegisteredModelGroupPermission.name == name, SqlRegisteredModelGroupPermission.group_id == group.id)
                .one()
            )
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def delete(self, group_name: str, name: str):
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = (
                session.query(SqlRegisteredModelGroupPermission)
                .filter(SqlRegisteredModelGroupPermission.name == name, SqlRegisteredModelGroupPermission.group_id == group.id)
                .one()
            )
            session.delete(perm)
            session.flush()

    def wipe(self, name: str):
        with self._Session() as session:
            perms = session.query(SqlRegisteredModelGroupPermission).filter(SqlRegisteredModelGroupPermission.name == name).all()
            for p in perms:
                session.delete(p)
            session.flush()
