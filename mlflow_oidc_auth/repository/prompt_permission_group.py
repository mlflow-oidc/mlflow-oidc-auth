from typing import List, Callable
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlRegisteredModelGroupPermission
from mlflow_oidc_auth.entities import RegisteredModelPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_group


class PromptPermissionGroupRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def grant_prompt_permission_to_group(self, group_name: str, name: str, permission: str) -> RegisteredModelPermission:
        """
        Create a new prompt permission for a group.
        :param group_name: The name of the group.
        :param name: The name of the prompt.
        :param permission: The permission to be granted to the group.
        :return: The created prompt permission.
        """
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = SqlRegisteredModelGroupPermission(name=name, group_id=group.id, permission=permission, prompt=True)
            session.add(perm)
            session.flush()
            return perm.to_mlflow_entity()

    def list_prompt_permissions_for_group(self, group_name: str) -> List[RegisteredModelPermission]:
        """
        List all prompt permissions for a given group.
        :param group_name: The name of the group.
        :return: A list of prompt permissions for the group.
        """
        with self._Session() as session:
            group = get_group(session, group_name)
            perms = (
                session.query(SqlRegisteredModelGroupPermission)
                .filter(
                    SqlRegisteredModelGroupPermission.group_id == group.id, SqlRegisteredModelGroupPermission.prompt == True
                )
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def update_prompt_permission_for_group(self, group_name: str, name: str, permission: str):
        """
        Update an existing prompt permission for a group.
        :param group_name: The name of the group.
        :param name: The name of the prompt.
        :param permission: The new permission to be granted to the group.
        :return: The updated prompt permission.
        """
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = (
                session.query(SqlRegisteredModelGroupPermission)
                .filter(
                    SqlRegisteredModelGroupPermission.name == name,
                    SqlRegisteredModelGroupPermission.group_id == group.id,
                    SqlRegisteredModelGroupPermission.prompt == True,
                )
                .one()
            )
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke_prompt_permission_from_group(self, group_name: str, name: str):
        """
        Revoke a prompt permission from a group.
        :param group_name: The name of the group.
        :param name: The name of the prompt.
        """
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = (
                session.query(SqlRegisteredModelGroupPermission)
                .filter(
                    SqlRegisteredModelGroupPermission.name == name,
                    SqlRegisteredModelGroupPermission.group_id == group.id,
                    SqlRegisteredModelGroupPermission.prompt == True,
                )
                .one()
            )
            session.delete(perm)
            session.flush()
