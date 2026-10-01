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
from sqlalchemy import and_, case, true
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGroup, SqlUser, SqlUserGroup
from mlflow_oidc_auth.permissions import _validate_permission, compare_permissions
from mlflow_oidc_auth.repository.utils import (
    get_group,
    get_user,
    validate_regex,
)
from mlflow.utils.workspace_utils import DEFAULT_WORKSPACE_NAME

from mlflow_oidc_auth.utils.grant_workspace import current_grant_workspace, grant_workspace_condition, new_pattern_workspace

ModelT = TypeVar("ModelT")
EntityT = TypeVar("EntityT")


class _GrantWorkspaceScope:
    """Workspace scoping for grants on name-keyed resources (see utils/grant_workspace.py).

    Subclasses whose resources MLflow keeps unique per ``(workspace, name)`` — registered models
    and prompts, gateway endpoints, secrets and model definitions — set ``workspace_scoped``: every
    lookup by resource and every per-principal list then matches only the request's grant
    workspace, and every new grant records it. Experiments (globally unique ids) and scorers leave
    it unset and are unaffected. Deleting all of one principal's grants stays global.
    """

    workspace_scoped: bool = False
    model_class: Type

    def _in_scope(self):
        if not self.workspace_scoped:
            return true()
        return grant_workspace_condition(self.model_class.workspace)

    def _resource_is(self, resource_id):
        condition = getattr(self.model_class, self.resource_id_attr) == resource_id
        return and_(condition, self._in_scope()) if self.workspace_scoped else condition

    def _new_row_fields(self) -> dict:
        return {"workspace": current_grant_workspace()} if self.workspace_scoped else {}

    def _one_in_scope(self, query, *, required: bool = True):
        """The single grant ``query`` finds for one resource and principal.

        The unique constraint allows one grant per workspace, resource and principal, but not among
        unassigned rows (``workspace IS NULL``): a replica still on a release before the column
        existed can add one beside an existing grant during a rolling upgrade. Those rows match only
        with workspaces disabled, alongside ``default``'s, and the startup backfill merges them.
        Until then the lookup picks the one the backfill will keep — the ``default`` grant, else the
        oldest — instead of failing the request.

        Parameters:
            query: A query on ``model_class`` filtered to one resource and principal.
            required: Raise ``NoResultFound`` when there is none (like ``Query.one``), else return None.

        Returns:
            The grant, or None when there is none and ``required`` is false.

        Raises:
            NoResultFound: When there is no grant and ``required`` is true.
            MultipleResultsFound: For a repository that is not workspace-scoped, with more than one match.
        """
        try:
            return query.one() if required else query.one_or_none()
        except MultipleResultsFound:
            if not self.workspace_scoped:
                raise
        column = self.model_class.workspace
        return query.order_by(case((column == DEFAULT_WORKSPACE_NAME, 0), else_=1), self.model_class.id).first()

    def _same_grant(self, session: Session, row) -> list:
        """``row`` and any unassigned duplicate of it (see :meth:`_one_in_scope`).

        Changing or revoking a grant applies to all of them, so a duplicate can never keep granting
        what was just lowered or revoked.

        Parameters:
            session: The session ``row`` was loaded in.
            row: A grant this repository found.

        Returns:
            The rows that make up this grant, ``row`` included.
        """
        if not self.workspace_scoped:
            return [row]
        model = self.model_class
        principal = "user_id" if hasattr(model, "user_id") else "group_id"
        query = session.query(model).filter(
            model.id != row.id,
            getattr(model, self.resource_id_attr) == getattr(row, self.resource_id_attr),
            getattr(model, principal) == getattr(row, principal),
            self._in_scope(),
        )
        # No ``prompt`` filter: permission checks count every row of the principal on this name,
        # whatever its ``prompt`` flag, so every such row is the same grant.
        return [row, *query.all()]


class BaseUserPermissionRepository(_GrantWorkspaceScope, Generic[ModelT, EntityT]):
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

    def _get_permission(self, session: Session, resource_id: str, username: str) -> ModelT:
        """Get the permission record for a given resource and user.

        :param session: SQLAlchemy session
        :param resource_id: The resource identifier value.
        :param username: The username of the user.
        :return: The permission model instance.
        :raises MlflowException: If no or multiple results found.
        """
        try:
            return self._one_in_scope(
                session.query(self.model_class)
                .join(SqlUser, self.model_class.user_id == SqlUser.id)
                .filter(
                    self._resource_is(resource_id),
                    SqlUser.username == username,
                )
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

    def grant_permission(self, resource_id: str, username: str, permission: str) -> EntityT:
        """Create a new permission for a user on a resource.

        :param resource_id: The resource identifier value.
        :param username: The username of the user.
        :param permission: The permission to grant.
        :return: The created permission entity.
        """
        _validate_permission(permission)
        with self._Session(read_only=False) as session:
            try:
                user = get_user(session, username)
                perm = self.model_class(
                    **{
                        self.resource_id_attr: resource_id,
                        "user_id": user.id,
                        "permission": permission,
                        **self._new_row_fields(),
                    }
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Permission already exists ({resource_id}, {username})",
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
            # Single JOIN rather than resolving the user first: this is called once per
            # resource type when building a permission context, so the redundant user
            # lookups added up (issue #253).
            rows = (
                session.query(self.model_class)
                .join(SqlUser, SqlUser.id == self.model_class.user_id)
                .filter(SqlUser.username == username, self._in_scope())
                .all()
            )
            return [r.to_mlflow_entity() for r in rows]

    def list_permissions_for_resource(self, resource_id: str) -> List[EntityT]:
        """List all permissions for a given resource.

        :param resource_id: The resource identifier value.
        :return: A list of permission entities for the resource.
        """
        with self._Session() as session:
            rows = session.query(self.model_class).filter(self._resource_is(resource_id)).all()
            return [r.to_mlflow_entity() for r in rows]

    def update_permission(self, resource_id: str, username: str, permission: str) -> EntityT:
        """Update the permission for a given resource and user.

        :param resource_id: The resource identifier value.
        :param username: The username of the user.
        :param permission: The new permission to set.
        :return: The updated permission entity.
        """
        _validate_permission(permission)
        with self._Session(read_only=False) as session:
            perm = self._get_permission(session, resource_id, username)
            for row in self._same_grant(session, perm):
                row.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke_permission(self, resource_id: str, username: str) -> None:
        """Delete the permission for a given resource and user.

        :param resource_id: The resource identifier value.
        :param username: The username of the user.
        """
        with self._Session(read_only=False) as session:
            perm = self._get_permission(session, resource_id, username)
            for row in self._same_grant(session, perm):
                session.delete(row)
            session.flush()

    def rename(self, old_name: str, new_name: str) -> None:
        """Update all permissions from old_name to new_name."""
        with self._Session(read_only=False) as session:
            perms = session.query(self.model_class).filter(self._resource_is(old_name)).all()
            for perm in perms:
                setattr(perm, self.resource_id_attr, new_name)
            session.flush()

    def wipe(self, resource_id: str) -> None:
        """Delete all permissions for a resource."""
        with self._Session(read_only=False) as session:
            perms = session.query(self.model_class).filter(self._resource_is(resource_id)).all()
            for p in perms:
                session.delete(p)
            session.flush()


class BaseGroupPermissionRepository(_GrantWorkspaceScope, Generic[ModelT, EntityT]):
    """Base class for group-level permission repositories.

    Subclasses must set:
        model_class: The SQLAlchemy model class (e.g. SqlExperimentGroupPermission)
        resource_id_attr: The column name on the model for the resource identifier
    """

    model_class: Type[ModelT]
    resource_id_attr: str

    def __init__(self, session_maker: Callable[[], Session]):
        self._Session: Callable[[], Session] = session_maker

    def _get_group_permission(self, session: Session, resource_id: str, group_name: str) -> ModelT:
        """Get the group permission for a given resource and group.

        :param session: SQLAlchemy session
        :param resource_id: The resource identifier value.
        :param group_name: The name of the group.
        :return: The group permission model instance.
        :raises MlflowException: If no or multiple results found.
        """
        try:
            return self._one_in_scope(
                session.query(self.model_class)
                .join(SqlGroup, self.model_class.group_id == SqlGroup.id)
                .filter(
                    self._resource_is(resource_id),
                    SqlGroup.group_name == group_name,
                )
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

    def _get_group_permission_or_none(self, session: Session, resource_id: str, group_name: str) -> ModelT | None:
        """Get the group permission or None if group/permission doesn't exist.

        :param session: SQLAlchemy session
        :param resource_id: The resource identifier value.
        :param group_name: The name of the group.
        :return: The group permission model instance, or None.
        """
        group = session.query(SqlGroup).filter(SqlGroup.group_name == group_name).one_or_none()
        if group is None:
            return None
        return self._one_in_scope(
            session.query(self.model_class).filter(
                self._resource_is(resource_id),
                self.model_class.group_id == group.id,
            ),
            required=False,
        )

    def _list_user_groups(self, username: str) -> List[str]:
        """List all group names for a given user.

        :param username: The username of the user.
        :return: A list of group names the user belongs to.

        Resolved in a single JOIN rather than user -> user_groups -> groups; this runs
        on every group-scoped permission check (issue #253).
        """
        with self._Session() as session:
            rows = (
                session.query(SqlGroup.group_name)
                .join(SqlUserGroup, SqlGroup.id == SqlUserGroup.group_id)
                .join(SqlUser, SqlUser.id == SqlUserGroup.user_id)
                .filter(SqlUser.username == username)
                .order_by(SqlGroup.id)
                .all()
            )
            return [r[0] for r in rows]

    def grant_group_permission(self, group_name: str, resource_id: str, permission: str) -> EntityT:
        """Create a new group permission for a resource.

        :param group_name: The name of the group.
        :param resource_id: The resource identifier value.
        :param permission: The permission to grant.
        :return: The created permission entity.
        """
        _validate_permission(permission)
        with self._Session(read_only=False) as session:
            try:
                group = get_group(session, group_name)
                perm = self.model_class(
                    **{
                        self.resource_id_attr: resource_id,
                        "group_id": group.id,
                        "permission": permission,
                        **self._new_row_fields(),
                    }
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Group permission already exists ({resource_id}, {group_name})",
                    RESOURCE_ALREADY_EXISTS,
                ) from e

    def list_permissions_for_group(self, group_name: str) -> List[EntityT]:
        """List all permissions for a given group.

        :param group_name: The name of the group.
        :return: A list of permission entities for the group.
        """
        with self._Session() as session:
            group = get_group(session, group_name)
            perms = session.query(self.model_class).filter(self.model_class.group_id == group.id, self._in_scope()).all()
            return [p.to_mlflow_entity() for p in perms]

    def list_permissions_for_group_id(self, group_id: int) -> List[EntityT]:
        """List all permissions for a given group ID.

        :param group_id: The ID of the group.
        :return: A list of permission entities for the group.
        """
        with self._Session() as session:
            perms = session.query(self.model_class).filter(self.model_class.group_id == group_id, self._in_scope()).all()
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
                .filter(self._resource_is(resource_id))
                .all()
            )
            return [(str(group_name), str(permission)) for group_name, permission in rows]

    def get_group_permission_for_user_resource(self, resource_id: str, username: str) -> EntityT:
        """Get the highest group permission for a user on a resource.

        Iterates through user's groups and finds the highest permission level.

        :param resource_id: The resource identifier value.
        :param username: The username of the user.
        :return: The permission entity with the highest permission level.
        :raises MlflowException: If no group permission found.
        """
        with self._Session() as session:
            # One query for every group the user belongs to, rather than a lookup per
            # group (which was 3 + 2G statements — 19 for a user in 8 groups). This is
            # the hottest path in the resolver: a search-filter pass runs it once per
            # resource. See issue #253.
            candidates = (
                session.query(self.model_class)
                .join(SqlUserGroup, SqlUserGroup.group_id == self.model_class.group_id)
                .join(SqlUser, SqlUser.id == SqlUserGroup.user_id)
                .filter(
                    SqlUser.username == username,
                    self._resource_is(resource_id),
                )
                .order_by(self.model_class.group_id)
                .all()
            )
            user_perms = None
            for perms in candidates:
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
            # Single JOIN across users -> user_groups -> permissions, rather than three
            # round-trips resolving the user and their memberships first (issue #253).
            perms = (
                session.query(self.model_class)
                .join(SqlUserGroup, SqlUserGroup.group_id == self.model_class.group_id)
                .join(SqlUser, SqlUser.id == SqlUserGroup.user_id)
                .filter(SqlUser.username == username, self._in_scope())
                .order_by(self.model_class.group_id)
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def update_group_permission(self, group_name: str, resource_id: str, permission: str) -> EntityT:
        """Update the group permission for a given resource and group.

        :param group_name: The name of the group.
        :param resource_id: The resource identifier value.
        :param permission: The new permission to set.
        :return: The updated permission entity.
        """
        _validate_permission(permission)
        with self._Session(read_only=False) as session:
            group = get_group(session, group_name)
            perm = self._one_in_scope(
                session.query(self.model_class).filter(
                    self._resource_is(resource_id),
                    self.model_class.group_id == group.id,
                )
            )
            for row in self._same_grant(session, perm):
                row.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke_group_permission(self, group_name: str, resource_id: str) -> None:
        """Delete the group permission for a given resource and group.

        :param group_name: The name of the group.
        :param resource_id: The resource identifier value.
        """
        with self._Session(read_only=False) as session:
            group = get_group(session, group_name)
            perm = self._one_in_scope(
                session.query(self.model_class).filter(
                    self._resource_is(resource_id),
                    self.model_class.group_id == group.id,
                )
            )
            for row in self._same_grant(session, perm):
                session.delete(row)
            session.flush()

    def rename(self, old_name: str, new_name: str) -> None:
        """Update all group permissions from old_name to new_name."""
        with self._Session(read_only=False) as session:
            perms = session.query(self.model_class).filter(self._resource_is(old_name)).all()
            for perm in perms:
                setattr(perm, self.resource_id_attr, new_name)
            session.flush()

    def wipe(self, resource_id: str) -> None:
        """Delete all group permissions for a resource."""
        with self._Session(read_only=False) as session:
            perms = session.query(self.model_class).filter(self._resource_is(resource_id)).all()
            for p in perms:
                session.delete(p)
            session.flush()


def _pattern_workspace_fields(model_class) -> dict:
    """The workspace a new pattern records, for resource pattern tables (utils/grant_workspace.py).

    Workspace pattern tables match workspace names and have no workspace of their own.
    """
    return {"workspace": new_pattern_workspace()} if hasattr(model_class, "workspace") else {}


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

    def grant(self, regex: str, priority: int, permission: str, username: str) -> EntityT:
        """Create a new regex permission for a user.

        :param regex: The regex pattern.
        :param priority: The priority of the permission.
        :param permission: The permission to grant.
        :param username: The username of the user.
        :return: The created permission entity.
        """
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session(read_only=False) as session:
            try:
                user = get_user(session, username)
                perm = self.model_class(
                    regex=regex,
                    priority=priority,
                    user_id=user.id,
                    permission=permission,
                    **_pattern_workspace_fields(self.model_class),
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Regex perm exists ({regex},{username})",
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
            # Single JOIN rather than resolving the user first — building a permission
            # context calls this once per resource type (issue #253).
            rows = (
                session.query(self.model_class)
                .join(SqlUser, SqlUser.id == self.model_class.user_id)
                .filter(SqlUser.username == username)
                .order_by(self.model_class.priority)
                .all()
            )
            return [r.to_mlflow_entity() for r in rows]

    def update(self, regex: str, priority: int, permission: str, username: str, id: int) -> EntityT:
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
        with self._Session(read_only=False) as session:
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
        with self._Session(read_only=False) as session:
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

    def _get_group_regex_permission(self, session: Session, id: int, group_id: int) -> ModelT:
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
        return session.query(self.model_class).filter(self.model_class.group_id.in_(groups)).order_by(self.model_class.priority).all()

    def grant(self, group_name: str, regex: str, priority: int, permission: str) -> EntityT:
        """Create a new group regex permission.

        :param group_name: The name of the group.
        :param regex: The regex pattern.
        :param priority: The priority of the permission.
        :param permission: The permission to grant.
        :return: The created permission entity.
        """
        _validate_permission(permission)
        validate_regex(regex)
        with self._Session(read_only=False) as session:
            try:
                group = get_group(session, group_name)
                perm = self.model_class(
                    regex=regex,
                    group_id=group.id,
                    permission=permission,
                    priority=priority,
                    **_pattern_workspace_fields(self.model_class),
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Group regex perm exists ({regex},{group_name})",
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

    def update(self, id: int, group_name: str, regex: str, priority: int, permission: str) -> EntityT:
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
        with self._Session(read_only=False) as session:
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
        with self._Session(read_only=False) as session:
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
            group_ids = [get_group(session, group_name).id for group_name in group_names]
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
            # Resolve the user's group ids in one JOIN.
            #
            # NOTE: this previously read ``group.id`` off the rows returned by
            # list_user_groups, which are SqlUserGroup (join-table) rows — so it used the
            # membership row's PK as if it were a group id and resolved permissions for
            # the wrong groups. It is not reachable in production today (only the
            # non-regex BaseGroupPermissionRepository variant is called), but every
            # regex-group repository inherits this, so the latent bug is removed here
            # rather than left for the first caller to hit.
            group_ids = [
                row[0]
                for row in session.query(SqlUserGroup.group_id).join(SqlUser, SqlUser.id == SqlUserGroup.user_id).filter(SqlUser.username == username).all()
            ]
            permissions = self._list_group_permissions(session, group_ids)
            return [p.to_mlflow_entity() for p in permissions]
