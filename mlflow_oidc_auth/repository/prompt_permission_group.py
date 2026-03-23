"""Prompt group permission repository.

Prompt permissions are stored in the same table as registered model group
permissions (SqlRegisteredModelGroupPermission) but flagged with ``prompt=True``.
The method names and query filters are entirely custom, so we inherit only the
constructor / session wiring from BaseGroupPermissionRepository.
"""

from typing import List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGroup, SqlRegisteredModelGroupPermission
from mlflow_oidc_auth.entities import RegisteredModelPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository._base import BaseGroupPermissionRepository
from mlflow_oidc_auth.repository.utils import get_group


class PromptPermissionGroupRepository(
    BaseGroupPermissionRepository[
        SqlRegisteredModelGroupPermission, RegisteredModelPermission
    ]
):
    model_class = SqlRegisteredModelGroupPermission
    resource_id_attr = "name"

    # -- private helper: prompt=True filter -----------------------------------

    def _get_prompt_group_permission(
        self, session: Session, name: str, group_id: int
    ) -> SqlRegisteredModelGroupPermission:
        """
        Get the prompt permission for a given prompt and group ID.
        :param session: SQLAlchemy session
        :param name: The name of the prompt.
        :param group_id: The ID of the group.
        :return: The prompt permission if it exists, otherwise raises an exception.
        """
        try:
            return (
                session.query(SqlRegisteredModelGroupPermission)
                .filter(
                    SqlRegisteredModelGroupPermission.name == name,
                    SqlRegisteredModelGroupPermission.group_id == group_id,
                    SqlRegisteredModelGroupPermission.prompt == True,
                )
                .one()
            )
        except NoResultFound:
            raise MlflowException(
                f"No permission for prompt={name}, group={group_id}",
                RESOURCE_DOES_NOT_EXIST,
            )
        except MultipleResultsFound:
            raise MlflowException(
                f"Multiple perms for prompt={name}, group={group_id}",
                INVALID_STATE,
            )

    # -- public CRUD (custom names, prompt=True) ------------------------------

    def grant_prompt_permission_to_group(
        self, group_name: str, name: str, permission: str
    ) -> RegisteredModelPermission:
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = SqlRegisteredModelGroupPermission(
                name=name, group_id=group.id, permission=permission, prompt=True
            )
            session.add(perm)
            session.flush()
            return perm.to_mlflow_entity()

    def list_prompt_permissions_for_group(
        self, group_name: str
    ) -> List[RegisteredModelPermission]:
        with self._Session() as session:
            group = get_group(session, group_name)
            perms = (
                session.query(SqlRegisteredModelGroupPermission)
                .filter(
                    SqlRegisteredModelGroupPermission.group_id == group.id,
                    SqlRegisteredModelGroupPermission.prompt == True,
                )
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def list_groups_for_prompt(self, name: str) -> List[tuple[str, str]]:
        """List groups that have explicit permissions for a prompt.

        Returns pairs of (group_name, permission).
        """
        with self._Session() as session:
            rows = (
                session.query(
                    SqlGroup.group_name, SqlRegisteredModelGroupPermission.permission
                )
                .join(
                    SqlRegisteredModelGroupPermission,
                    SqlRegisteredModelGroupPermission.group_id == SqlGroup.id,
                )
                .filter(SqlRegisteredModelGroupPermission.name == name)
                .filter(SqlRegisteredModelGroupPermission.prompt == True)
                .all()
            )
            return [
                (str(group_name), str(permission)) for group_name, permission in rows
            ]

    def update_prompt_permission_for_group(
        self, group_name: str, name: str, permission: str
    ):
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_prompt_group_permission(session, name, group.id)
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke_prompt_permission_from_group(self, group_name: str, name: str):
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_prompt_group_permission(session, name, group.id)
            session.delete(perm)
            session.flush()
