"""Generic base classes for permission repositories.

Provides common CRUD patterns for:
- BaseUserPermissionRepository: user-level permissions (resource_id + username)
- BaseGroupPermissionRepository: group-level permissions (resource_id + group_name)
- BaseRegexPermissionRepository: regex-based user permissions (regex + priority + username)
- BaseGroupRegexPermissionRepository: regex-based group permissions (regex + priority + group_id)
"""

from typing import Callable, Generic, List, Type, TypeVar

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import (
    INVALID_STATE,
    RESOURCE_ALREADY_EXISTS,
    RESOURCE_DOES_NOT_EXIST,
)
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGroup, SqlUser
from mlflow_oidc_auth.permissions import _validate_permission, compare_permissions
from mlflow_oidc_auth.repository.utils import (
    get_group,
    get_user,
    list_user_groups,
    validate_regex,
)

ModelT = TypeVar("ModelT")
EntityT = TypeVar("EntityT")


class BaseUserPermissionRepository(Generic[ModelT, EntityT]):
    """Base class for user-level permission repositories.

    Subclasses must set:
        model_class: The SQLAlchemy model class (e.g. SqlExperimentPermission)
        resource_id_attr: The column name on the model for the resource identifier
                          (e.g. "experiment_id", "name", "endpoint_id")
    """

    model_class: Type[ModelT]
    resource_id_attr: str

    def __init__(self, session_maker: Callable[[], Session]):
        self._Session: Callable[[], Session] = session_maker

    def _get_permission(
        self, session: Session, resource_id: str, username: str
    ) -> ModelT:
        """Get the permission record for a given resource and user.

        :param session: SQLAlchemy session
        :param resource_id: The resource identifier value.
        :param username: The username of the user.
        :return: The permission model instance.
        :raises MlflowException: If no or multiple results found.
        """
        try:
            return (
                session.query(self.model_class)
                .join(SqlUser, self.model_class.user_id == SqlUser.id)
                .filter(
                    getattr(self.model_class, self.resource_id_attr) == resource_id,
                    SqlUser.username == username,
                )
                .one()
            )
        except NoResultFound:
            raise MlflowException(
                f"No permission for {self.resource_id_attr}={resource_id}, user={username}",
                RESOURCE_DOES_NOT_EXIST,
            )
        except MultipleResultsFound:
            raise MlflowException(
                f"Multiple perms for {self.resource_id_attr}={resource_id}, user={username}",
                INVALID_STATE,
            )

    def grant_permission(
        self, resource_id: str, username: str, permission: str
    ) -> EntityT:
        """Create a new permission for a user on a resource.

        :param resource_id: The resource identifier value.
        :param username: The username of the user.
        :param permission: The permission to grant.
        :return: The created permission entity.
        """
        _validate_permission(permission)
        with self._Session() as session:
            try:
                user = get_user(session, username)
                perm = self.model_class(
                    **{
                        self.resource_id_attr: resource_id,
                        "user_id": user.id,
                        "permission": permission,
                    }
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Permission already exists ({resource_id}, {username}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                ) from e

    def get_permission(self, resource_id: str, username: str) -> EntityT:
        """Get the permission for a given resource and user.

        :param resource_id: The resource identifier value.
        :param username: The username of the user.
        :return: The permission entity.
        """
        with self._Session() as session:
            perm = self._get_permission(session, resource_id, username)
            return perm.to_mlflow_entity()

    def list_permissions_for_user(self, username: str) -> List[EntityT]:
        """List all permissions for a given user.

        :param username: The username of the user.
        :return: A list of permission entities for the user.
        """
        with self._Session() as session:
            user = get_user(session, username)
            rows = (
                session.query(self.model_class)
                .filter(self.model_class.user_id == user.id)
                .all()
            )
            return [r.to_mlflow_entity() for r in rows]

    def list_permissions_for_resource(self, resource_id: str) -> List[EntityT]:
        """List all permissions for a given resource.

        :param resource_id: The resource identifier value.
        :return: A list of permission entities for the resource.
        """
        with self._Session() as session:
            rows = (
                session.query(self.model_class)
                .filter(getattr(self.model_class, self.resource_id_attr) == resource_id)
                .all()
            )
            return [r.to_mlflow_entity() for r in rows]

    def update_permission(
        self, resource_id: str, username: str, permission: str
    ) -> EntityT:
        """Update the permission for a given resource and user.

        :param resource_id: The resource identifier value.
        :param username: The username of the user.
        :param permission: The new permission to set.
        :return: The updated permission entity.
        """
        _validate_permission(permission)
        with self._Session() as session:
            perm = self._get_permission(session, resource_id, username)
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke_permission(self, resource_id: str, username: str) -> None:
        """Delete the permission for a given resource and user.

        :param resource_id: The resource identifier value.
        :param username: The username of the user.
        """
        with self._Session() as session:
            perm = self._get_permission(session, resource_id, username)
            session.delete(perm)
            session.flush()

    def rename(self, old_name: str, new_name: str) -> None:
        """Update all permissions from old_name to new_name."""
        with self._Session() as session:
            perms = (
                session.query(self.model_class)
                .filter(getattr(self.model_class, self.resource_id_attr) == old_name)
                .all()
            )
            for perm in perms:
                setattr(perm, self.resource_id_attr, new_name)
            session.flush()

    def wipe(self, resource_id: str) -> None:
        """Delete all permissions for a resource."""
        with self._Session() as session:
            perms = (
                session.query(self.model_class)
                .filter(getattr(self.model_class, self.resource_id_attr) == resource_id)
                .all()
            )
            for p in perms:
                session.delete(p)
            session.flush()


class BaseGroupPermissionRepository(Generic[ModelT, EntityT]):
    """Base class for group-level permission repositories.

    Subclasses must set:
        model_class: The SQLAlchemy model class (e.g. SqlExperimentGroupPermission)
        resource_id_attr: The column name on the model for the resource identifier
    """

    model_class: Type[ModelT]
    resource_id_attr: str

    def __init__(self, session_maker: Callable[[], Session]):
        self._Session: Callable[[], Session] = session_maker

    def _get_group_permission(
        self, session: Session, resource_id: str, group_name: str
    ) -> ModelT:
        """Get the group permission for a given resource and group.

        :param session: SQLAlchemy session
        :param resource_id: The resource identifier value.
        :param group_name: The name of the group.
        :return: The group permission model instance.
        :raises MlflowException: If no or multiple results found.
        """
        try:
            return (
                session.query(self.model_class)
                .join(SqlGroup, self.model_class.group_id == SqlGroup.id)
                .filter(
                    getattr(self.model_class, self.resource_id_attr) == resource_id,
                    SqlGroup.group_name == group_name,
                )
                .one()
            )
        except NoResultFound:
            raise MlflowException(
                f"No group permission for {self.resource_id_attr}={resource_id}, group={group_name}",
                RESOURCE_DOES_NOT_EXIST,
            )
        except MultipleResultsFound:
            raise MlflowException(
                f"Multiple group perms for {self.resource_id_attr}={resource_id}, group={group_name}",
                INVALID_STATE,
            )

    def _get_group_permission_or_none(
        self, session: Session, resource_id: str, group_name: str
    ) -> ModelT | None:
        """Get the group permission or None if group/permission doesn't exist.

        :param session: SQLAlchemy session
        :param resource_id: The resource identifier value.
        :param group_name: The name of the group.
        :return: The group permission model instance, or None.
        """
        group = (
            session.query(SqlGroup)
            .filter(SqlGroup.group_name == group_name)
            .one_or_none()
        )
        if group is None:
            return None
        return (
            session.query(self.model_class)
            .filter(
                getattr(self.model_class, self.resource_id_attr) == resource_id,
                self.model_class.group_id == group.id,
            )
            .one_or_none()
        )

    def _list_user_groups(self, username: str) -> List[str]:
        """List all group names for a given user.

        :param username: The username of the user.
        :return: A list of group names the user belongs to.
        """
        with self._Session() as session:
            user = get_user(session, username)
            user_groups_ids = list_user_groups(session, user)
            user_groups = (
                session.query(SqlGroup)
                .filter(SqlGroup.id.in_([ug.group_id for ug in user_groups_ids]))
                .all()
            )
            return [ug.group_name for ug in user_groups]

    def grant_group_permission(
        self, group_name: str, resource_id: str, permission: str
    ) -> EntityT:
        """Create a new group permission for a resource.

        :param group_name: The name of the group.
        :param resource_id: The resource identifier value.
        :param permission: The permission to grant.
        :return: The created permission entity.
        """
        _validate_permission(permission)
        with self._Session() as session:
            try:
                group = get_group(session, group_name)
                perm = self.model_class(
                    **{
                        self.resource_id_attr: resource_id,
                        "group_id": group.id,
                        "permission": permission,
                    }
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Group permission already exists ({resource_id}, {group_name}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                ) from e

    def list_permissions_for_group(self, group_name: str) -> List[EntityT]:
        """List all permissions for a given group.

        :param group_name: The name of the group.
        :return: A list of permission entities for the group.
        """
        with self._Session() as session:
            group = get_group(session, group_name)
            perms = (
                session.query(self.model_class)
                .filter(self.model_class.group_id == group.id)
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def list_permissions_for_group_id(self, group_id: int) -> List[EntityT]:
        """List all permissions for a given group ID.

        :param group_id: The ID of the group.
        :return: A list of permission entities for the group.
        """
        with self._Session() as session:
            perms = (
                session.query(self.model_class)
                .filter(self.model_class.group_id == group_id)
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def list_groups_for_resource(self, resource_id: str) -> List[tuple[str, str]]:
        """List groups that have explicit permissions for a resource.

        :param resource_id: The resource identifier value.
        :return: Pairs of (group_name, permission).
        """
        with self._Session() as session:
            rows = (
                session.query(SqlGroup.group_name, self.model_class.permission)
                .join(self.model_class, self.model_class.group_id == SqlGroup.id)
                .filter(getattr(self.model_class, self.resource_id_attr) == resource_id)
                .all()
            )
            return [
                (str(group_name), str(permission)) for group_name, permission in rows
            ]

    def get_group_permission_for_user_resource(
        self, resource_id: str, username: str
    ) -> EntityT:
        """Get the highest group permission for a user on a resource.

        Iterates through user's groups and finds the highest permission level.

        :param resource_id: The resource identifier value.
        :param username: The username of the user.
        :return: The permission entity with the highest permission level.
        :raises MlflowException: If no group permission found.
        """
        with self._Session() as session:
            user_groups = self._list_user_groups(username)
            user_perms = None
            for ug in user_groups:
                perms = self._get_group_permission_or_none(session, resource_id, ug)
                if perms is None:
                    continue
                if user_perms is None:
                    user_perms = perms
                    continue
                try:
                    if compare_permissions(
                        str(user_perms.permission), str(perms.permission)
                    ):
                        user_perms = perms
                except AttributeError:
                    user_perms = perms
            try:
                if user_perms is not None:
                    return user_perms.to_mlflow_entity()
                else:
                    raise MlflowException(
                        f"Group permission with {self.resource_id_attr}={resource_id} and username={username} not found",
                        RESOURCE_DOES_NOT_EXIST,
                    )
            except AttributeError:
                raise MlflowException(
                    f"Group permission with {self.resource_id_attr}={resource_id} and username={username} not found",
                    RESOURCE_DOES_NOT_EXIST,
                )

    def list_permissions_for_user_groups(self, username: str) -> List[EntityT]:
        """List all permissions for groups that a user belongs to.

        :param username: The username of the user.
        :return: A list of permission entities.
        """
        with self._Session() as session:
            user = get_user(session, username=username)
            user_groups = list_user_groups(session, user)
            perms = (
                session.query(self.model_class)
                .filter(
                    self.model_class.group_id.in_([ug.group_id for ug in user_groups])
                )
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def update_group_permission(
        self, group_name: str, resource_id: str, permission: str
    ) -> EntityT:
        """Update the group permission for a given resource and group.

        :param group_name: The name of the group.
        :param resource_id: The resource identifier value.
        :param permission: The new permission to set.
        :return: The updated permission entity.
        """
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = (
                session.query(self.model_class)
                .filter(
                    getattr(self.model_class, self.resource_id_attr) == resource_id,
                    self.model_class.group_id == group.id,
                )
                .one()
            )
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke_group_permission(self, group_name: str, resource_id: str) -> None:
        """Delete the group permission for a given resource and group.

        :param group_name: The name of the group.
        :param resource_id: The resource identifier value.
        """
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = (
                session.query(self.model_class)
                .filter(
                    getattr(self.model_class, self.resource_id_attr) == resource_id,
                    self.model_class.group_id == group.id,
                )
                .one()
            )
            session.delete(perm)
            session.flush()

    def rename(self, old_name: str, new_name: str) -> None:
        """Update all group permissions from old_name to new_name."""
        with self._Session() as session:
            perms = (
                session.query(self.model_class)
                .filter(getattr(self.model_class, self.resource_id_attr) == old_name)
                .all()
            )
            for perm in perms:
                setattr(perm, self.resource_id_attr, new_name)
            session.flush()

    def wipe(self, resource_id: str) -> None:
        """Delete all group permissions for a resource."""
        with self._Session() as session:
            perms = (
                session.query(self.model_class)
                .filter(getattr(self.model_class, self.resource_id_attr) == resource_id)
                .all()
            )
            for p in perms:
                session.delete(p)
            session.flush()


class BaseRegexPermissionRepository(Generic[ModelT, EntityT]):
    """Base class for regex-based user permission repositories.

    Subclasses must set:
        model_class: The SQLAlchemy model class (e.g. SqlExperimentRegexPermission)
    """

    model_class: Type[ModelT]

    def __init__(self, session_maker: Callable[[], Session]):
        self._Session: Callable[[], Session] = session_maker

    def _get_regex_permission(self, session: Session, user_id: int, id: int) -> ModelT:
        """Get the regex permission for a given user ID and permission ID.

        :param session: SQLAlchemy session
        :param user_id: The ID of the user.
        :param id: The ID of the permission record.
        :return: The regex permission model instance.
        :raises MlflowException: If no or multiple results found.
        """
        try:
            return (
                session.query(self.model_class)
                .filter(
                    self.model_class.user_id == user_id,
                    self.model_class.id == id,
                )
                .one()
            )
        except NoResultFound:
            raise MlflowException(
                f"Permission not found for user_id: {user_id}, and id: {id}",
                RESOURCE_DOES_NOT_EXIST,
            )
        except MultipleResultsFound:
            raise MlflowException(
                f"Multiple Permissions found for user_id: {user_id}, and id: {id}",
                INVALID_STATE,
            )

    def grant(
        self, regex: str, priority: int, permission: str, username: str
    ) -> EntityT:
        """Create a new regex permission for a user.

        :param regex: The regex pattern.
        :param priority: The priority of the permission.
        :param permission: The permission to grant.
        :param username: The username of the user.
        :return: The created permission entity.
        """
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            try:
                user = get_user(session, username)
                perm = self.model_class(
                    regex=regex,
                    priority=priority,
                    user_id=user.id,
                    permission=permission,
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Regex perm exists ({regex},{username}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                ) from e

    def get(self, username: str, id: int) -> EntityT:
        """Get the regex permission by username and ID.

        :param username: The username of the user.
        :param id: The ID of the permission record.
        :return: The permission entity.
        """
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_regex_permission(session=session, user_id=user.id, id=id)
            return perm.to_mlflow_entity()

    def list(self) -> List[EntityT]:
        """List all regex permissions.

        :return: A list of all permission entities.
        """
        with self._Session() as session:
            rows = session.query(self.model_class).all()
            return [r.to_mlflow_entity() for r in rows]

    def list_regex_for_user(self, username: str) -> List[EntityT]:
        """List all regex permissions for a user, ordered by priority.

        :param username: The username of the user.
        :return: A list of permission entities.
        """
        with self._Session() as session:
            user = get_user(session, username)
            rows = (
                session.query(self.model_class)
                .filter(self.model_class.user_id == user.id)
                .order_by(self.model_class.priority)
                .all()
            )
            return [r.to_mlflow_entity() for r in rows]

    def update(
        self, regex: str, priority: int, permission: str, username: str, id: int
    ) -> EntityT:
        """Update a regex permission.

        :param regex: The new regex pattern.
        :param priority: The new priority.
        :param permission: The new permission.
        :param username: The username of the user.
        :param id: The ID of the permission record.
        :return: The updated permission entity.
        """
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_regex_permission(session, user.id, id)
            perm.priority = priority
            perm.permission = permission
            perm.regex = regex
            session.flush()
            return perm.to_mlflow_entity()

    def revoke(self, username: str, id: int) -> None:
        """Delete a regex permission.

        :param username: The username of the user.
        :param id: The ID of the permission record.
        """
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_regex_permission(session=session, user_id=user.id, id=id)
            session.delete(perm)
            session.commit()
            return None


class BaseGroupRegexPermissionRepository(Generic[ModelT, EntityT]):
    """Base class for regex-based group permission repositories.

    Subclasses must set:
        model_class: The SQLAlchemy model class (e.g. SqlExperimentGroupRegexPermission)
    """

    model_class: Type[ModelT]

    def __init__(self, session_maker: Callable[[], Session]):
        self._Session: Callable[[], Session] = session_maker

    def _get_group_regex_permission(
        self, session: Session, id: int, group_id: int
    ) -> ModelT:
        """Get the group regex permission for a given ID and group ID.

        :param session: SQLAlchemy session
        :param id: The ID of the permission record.
        :param group_id: The ID of the group.
        :return: The group regex permission model instance.
        :raises MlflowException: If no or multiple results found.
        """
        try:
            return (
                session.query(self.model_class)
                .filter(
                    self.model_class.id == id,
                    self.model_class.group_id == group_id,
                )
                .one()
            )
        except NoResultFound:
            raise MlflowException(
                f"Permission not found for group_id: {group_id} and id: {id}",
                RESOURCE_DOES_NOT_EXIST,
            )
        except MultipleResultsFound:
            raise MlflowException(
                f"Multiple Permissions found for group_id: {group_id} and id: {id}",
                INVALID_STATE,
            )

    def _list_group_permissions(self, session: Session, groups: List[int]) -> list:
        """List all permissions for a list of group IDs, ordered by priority.

        :param session: SQLAlchemy session
        :param groups: A list of group IDs.
        :return: A list of permission model instances.
        """
        return (
            session.query(self.model_class)
            .filter(self.model_class.group_id.in_(groups))
            .order_by(self.model_class.priority)
            .all()
        )

    def grant(
        self, group_name: str, regex: str, priority: int, permission: str
    ) -> EntityT:
        """Create a new group regex permission.

        :param group_name: The name of the group.
        :param regex: The regex pattern.
        :param priority: The priority of the permission.
        :param permission: The permission to grant.
        :return: The created permission entity.
        """
        _validate_permission(permission)
        validate_regex(regex)
        with self._Session() as session:
            try:
                group = get_group(session, group_name)
                perm = self.model_class(
                    regex=regex,
                    group_id=group.id,
                    permission=permission,
                    priority=priority,
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Group regex perm exists ({regex},{group_name}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                ) from e

    def get(self, group_name: str, id: int) -> EntityT:
        """Get a group regex permission by group name and ID.

        :param group_name: The name of the group.
        :param id: The ID of the permission record.
        :return: The permission entity.
        """
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_group_regex_permission(session, id, group.id)
            return perm.to_mlflow_entity()

    def update(
        self, id: int, group_name: str, regex: str, priority: int, permission: str
    ) -> EntityT:
        """Update a group regex permission.

        :param id: The ID of the permission record.
        :param group_name: The name of the group.
        :param regex: The new regex pattern.
        :param priority: The new priority.
        :param permission: The new permission.
        :return: The updated permission entity.
        """
        _validate_permission(permission)
        validate_regex(regex)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_group_regex_permission(session, id, group.id)
            perm.permission = permission
            perm.regex = regex
            perm.priority = priority
            session.commit()
            return perm.to_mlflow_entity()

    def revoke(self, group_name: str, id: int) -> None:
        """Delete a group regex permission.

        :param group_name: The name of the group.
        :param id: The ID of the permission record.
        """
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_group_regex_permission(session, id, group.id)
            session.delete(perm)
            session.commit()
            return None

    def list_permissions_for_group(self, group_name: str) -> List[EntityT]:
        """List all permissions for a given group.

        :param group_name: The name of the group.
        :return: A list of permission entities.
        """
        with self._Session() as session:
            group = get_group(session, group_name)
            permissions = self._list_group_permissions(session, [group.id])
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_groups(self, group_names: List[str]) -> List[EntityT]:
        """List all permissions for a list of groups.

        :param group_names: The names of the groups.
        :return: A list of permission entities.
        """
        with self._Session() as session:
            group_ids = [
                get_group(session, group_name).id for group_name in group_names
            ]
            permissions = self._list_group_permissions(session, group_ids)
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_group_id(self, group_id: int) -> List[EntityT]:
        """List all permissions for a given group ID.

        :param group_id: The ID of the group.
        :return: A list of permission entities.
        """
        with self._Session() as session:
            permissions = self._list_group_permissions(session, [group_id])
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_groups_ids(self, group_ids: List[int]) -> List[EntityT]:
        """List all permissions for a list of group IDs.

        :param group_ids: The IDs of the groups.
        :return: A list of permission entities.
        """
        with self._Session() as session:
            permissions = self._list_group_permissions(session, group_ids)
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_user_groups(self, username: str) -> List[EntityT]:
        """List all permissions for groups that a user belongs to.

        :param username: The username of the user.
        :return: A list of permission entities.
        """
        with self._Session() as session:
            user = get_user(session, username)
            user_groups = list_user_groups(session, user)
            group_ids = [group.id for group in user_groups]
            permissions = self._list_group_permissions(session, group_ids)
            return [p.to_mlflow_entity() for p in permissions]
