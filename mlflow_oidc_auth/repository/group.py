from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST, INVALID_STATE
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGroup, SqlUser, SqlUserGroup
from mlflow_oidc_auth.entities import User
from mlflow_oidc_auth.repository.utils import get_group, get_user, list_user_groups


class GroupRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def create_group(self, group_name: str) -> None:
        """
        Create a new group.
        :param group_name: The name of the group to be created.
        :raises MlflowException: If the group already exists.
        """
        with self._Session() as session:
            try:
                grp = SqlGroup(group_name=group_name)
                session.add(grp)
                session.flush()
            except IntegrityError as e:
                raise MlflowException(f"Group '{group_name}' exists: {e}", RESOURCE_ALREADY_EXISTS)

    def create_groups(self, group_names: List[str]) -> None:
        """
        Create multiple groups.
        :param group_names: A list of group names to be created.
        """
        with self._Session() as session:
            for group_name in group_names:
                group = session.query(SqlGroup).filter(SqlGroup.group_name == group_name).first()
                if group is None:
                    group = SqlGroup(group_name=group_name)
                    session.add(group)
            session.flush()

    def list_groups(self) -> List[str]:
        """
        List all groups.
        :return: A list of group names.
        """
        with self._Session() as session:
            return [g.group_name for g in session.query(SqlGroup).all()]

    def delete_group(self, group_name: str) -> None:
        """
        Delete a group by its name.
        :param group_name: The name of the group to be deleted.
        :raises MlflowException: If the group does not exist or if multiple groups with the same name exist.
        """
        with self._Session() as session:
            try:
                grp = session.query(SqlGroup).filter(SqlGroup.group_name == group_name).one()
                session.delete(grp)
                session.flush()
            except NoResultFound:
                raise MlflowException(f"Group '{group_name}' not found", RESOURCE_DOES_NOT_EXIST)
            except MultipleResultsFound:
                raise MlflowException(f"Multiple groups named '{group_name}'", INVALID_STATE)

    def add_user_to_group(self, username: str, group_name: str) -> None:
        """
        Add a user to a group.
        :param username: The username of the user to be added.
        :param group_name: The name of the group to which the user will be added.
        """
        with self._Session() as session:
            user = get_user(session, username)
            grp = get_group(session, group_name)
            link = SqlUserGroup(user_id=user.id, group_id=grp.id)
            session.add(link)
            session.flush()

    def remove_user_from_group(self, username: str, group_name: str) -> None:
        """
        Remove a user from a group.
        :param username: The username of the user to be removed.
        :param group_name: The name of the group from which the user will be removed.
        """
        with self._Session() as session:
            user = get_user(session, username)
            grp = get_group(session, group_name)
            ug = session.query(SqlUserGroup).filter(SqlUserGroup.user_id == user.id, SqlUserGroup.group_id == grp.id).one()
            session.delete(ug)
            session.flush()

    def list_group_members(self, group_name: str) -> List[User]:
        """
        List all users in a group.
        :param group_name: The name of the group.
        :return: A list of users in the group.
        """
        with self._Session() as session:
            grp = get_group(session, group_name)
            user_ids = [ug.user_id for ug in session.query(SqlUserGroup).filter(SqlUserGroup.group_id == grp.id)]
            users = session.query(SqlUser).filter(SqlUser.id.in_(user_ids)).all()
            return [user.to_mlflow_entity() for user in users]

    def list_groups_for_user(self, username: str) -> List[str]:
        """
        List all groups for a user.
        :param username: The username of the user.
        :return: A list of group names for the user.
        """
        with self._Session() as session:
            user = get_user(session, username)
            user_groups_ids = list_user_groups(session, user)
            user_groups = session.query(SqlGroup).filter(SqlGroup.id.in_([ug.group_id for ug in user_groups_ids])).all()
            return [ug.group_name for ug in user_groups]

    def list_group_ids_for_user(self, username: str) -> List[int]:
        """
        List all group IDs for a user.
        :param username: The username of the user.
        :return: A list of group IDs for the user.
        """
        with self._Session() as session:
            user = get_user(session, username)
            user_groups_ids = list_user_groups(session, user)
            return [ug.group_id for ug in user_groups_ids]

    def set_groups_for_user(self, username: str, group_names: List[str]) -> None:
        """
        Set the groups for a user.
        :param username: The username of the user.
        :param group_names: A list of group names to be set for the user.
        """
        with self._Session() as session:
            user = get_user(session, username)
            user_groups = list_user_groups(session, user)
            for ug in user_groups:
                session.delete(ug)
            for group_name in group_names:
                group = get_group(session, group_name)
                user_group = SqlUserGroup(user_id=user.id, group_id=group.id)
                session.add(user_group)
            session.flush()
