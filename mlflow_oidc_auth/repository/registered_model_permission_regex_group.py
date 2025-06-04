from typing import Callable, List, Optional

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlRegisteredModelGroupRegexPermission
from mlflow_oidc_auth.entities import RegisteredModelGroupRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository import GroupRepository
from mlflow_oidc_auth.repository.utils import get_group


class RegisteredModelGroupRegexPermissionRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker
        self._group_repo = GroupRepository(session_maker)

    def _get_registered_model_group_regex_permission(
        self, session: Session, id: int, group_id: int, prompt: bool = False
    ) -> SqlRegisteredModelGroupRegexPermission:
        """
        Get the registered model group regex permission for a given regex and group ID.
        :param session: SQLAlchemy session
        :param regex: The regex pattern for the registered model name.
        :param group_id: The ID of the group.
        :param prompt: Whether the permission is a prompt permission.
        :return: The registered model group regex permission if it exists, otherwise raises an exception.
        """
        try:
            return (
                session.query(SqlRegisteredModelGroupRegexPermission)
                .filter(
                    SqlRegisteredModelGroupRegexPermission.id == id,
                    SqlRegisteredModelGroupRegexPermission.group_id == group_id,
                    SqlRegisteredModelGroupRegexPermission.prompt == prompt,
                )
                .one()
            )
        except NoResultFound:
            raise MlflowException(
                f"No model perm for id={id}, group_id={group_id}, prompt={prompt}",
                RESOURCE_DOES_NOT_EXIST,
            )
        except MultipleResultsFound:
            raise MlflowException(
                f"Multiple model perms for id={id}, group_id={group_id}, prompt={prompt}",
                INVALID_STATE,
            )

    def grant(self, group_name: str, regex: str, permission: str, priority: int = 0, prompt: bool = False) -> RegisteredModelGroupRegexPermission:
        """
        Create a new registered model group permission with regex.
        :param group_name: The name of the group.
        :param regex: The regex pattern for the registered model name.
        :param permission: The permission to be granted to the group.
        :return: The created registered model group permission.
        """
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = SqlRegisteredModelGroupRegexPermission(
                regex=regex,
                priority=priority,
                group_id=group.id,
                permission=permission,
                prompt=prompt,
            )
            session.add(perm)
            session.flush()
            return perm.to_mlflow_entity()

    def get(self, id: int, group_name: str, prompt: bool = False) -> RegisteredModelGroupRegexPermission:
        """
        Get a registered model group permission by ID and group name.
        :param id: The ID of the registered model group permission.
        :param group_name: The name of the group.
        :return: The registered model group permission.
        """
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_registered_model_group_regex_permission(session, id, group.id, prompt=prompt)
            return perm.to_mlflow_entity()

    def list_permissions_for_group(self, group_name: str, prompt: bool = False) -> List[RegisteredModelGroupRegexPermission]:
        """
        List all registered model group permissions for a given group.
        :param group_name: The name of the group.
        :return: A list of registered model group permissions.
        """
        with self._Session() as session:
            group = get_group(session, group_name)
            permissions = (
                session.query(SqlRegisteredModelGroupRegexPermission)
                .filter(
                    SqlRegisteredModelGroupRegexPermission.group_id == group.id,
                    SqlRegisteredModelGroupRegexPermission.prompt == prompt,
                )
                .order_by(SqlRegisteredModelGroupRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_groups(self, group_names: List[str], prompt: bool = False) -> List[RegisteredModelGroupRegexPermission]:
        """
        List all registered model group permissions for a list of groups.
        :param group_names: The names of the groups.
        :return: A list of registered model group permissions.
        """
        with self._Session() as session:
            groups = [get_group(session, name) for name in group_names]
            permissions = (
                session.query(SqlRegisteredModelGroupRegexPermission)
                .filter(
                    SqlRegisteredModelGroupRegexPermission.group_id.in_([g.id for g in groups]),
                    SqlRegisteredModelGroupRegexPermission.prompt == prompt,
                )
                .order_by(SqlRegisteredModelGroupRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_groups_ids(self, group_ids: List[int], prompt: bool = False) -> List[RegisteredModelGroupRegexPermission]:
        """
        List all registered model group permissions for a list of groups.
        :param group_ids: The IDs of the groups.
        :return: A list of registered model group permissions.
        """
        with self._Session() as session:
            permissions = (
                session.query(SqlRegisteredModelGroupRegexPermission)
                .filter(
                    SqlRegisteredModelGroupRegexPermission.group_id.in_(group_ids),
                    SqlRegisteredModelGroupRegexPermission.prompt == prompt,
                )
                .order_by(SqlRegisteredModelGroupRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in permissions]

    def update(self, id: int, regex: str, group_name: str, permission: str, priority: int = 0, prompt: bool = False) -> RegisteredModelGroupRegexPermission:
        """
        Update a registered model group permission.
        :param regex: The regex pattern for the registered model name.
        :param group_name: The name of the group.
        :param permission: The new permission to be granted to the group.
        :param priority: The new priority of the permission.
        :return: The updated registered model group permission.
        """
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_registered_model_group_regex_permission(session, id, group.id, prompt=prompt)
            perm.permission = permission
            perm.priority = priority
            perm.prompt = prompt
            perm.regex = regex
            session.flush()
            return perm.to_mlflow_entity()

    def revoke(self, id: int, group_name: str, prompt: bool = False) -> None:
        """
        Revoke a registered model group permission.
        :param id: The ID of the registered model group permission.
        :param group_name: The name of the group.
        """
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_registered_model_group_regex_permission(session, id, group.id, prompt=prompt)
            session.delete(perm)
            session.flush()
