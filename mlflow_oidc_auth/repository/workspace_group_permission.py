"""Standalone repository for group-level workspace permissions.

Per decision WSAUTH-B: This is a standalone repository — NOT extending base classes.
Workspace is a tenant boundary, not a resource.
"""

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import (
    RESOURCE_ALREADY_EXISTS,
    RESOURCE_DOES_NOT_EXIST,
)
from sqlalchemy.exc import IntegrityError, NoResultFound

from mlflow_oidc_auth.db.models.user import SqlUserGroup
from mlflow_oidc_auth.db.models.workspace import SqlWorkspaceGroupPermission
from mlflow_oidc_auth.entities.workspace import WorkspaceGroupPermission
from mlflow_oidc_auth.permissions import compare_permissions


class WorkspaceGroupPermissionRepository:
    """CRUD operations for group-level workspace permissions."""

    def __init__(self, session_maker):
        self.ManagedSessionMaker = session_maker

    def get(self, workspace: str, group_id: int) -> WorkspaceGroupPermission:
        """Get a group's workspace permission.

        Parameters:
            workspace: The workspace name.
            group_id: The group's ID.

        Returns:
            WorkspaceGroupPermission entity.

        Raises:
            MlflowException: If the permission does not exist.
        """
        with self.ManagedSessionMaker() as session:
            try:
                perm = (
                    session.query(SqlWorkspaceGroupPermission)
                    .filter(
                        SqlWorkspaceGroupPermission.workspace == workspace,
                        SqlWorkspaceGroupPermission.group_id == group_id,
                    )
                    .one()
                )
                return perm.to_mlflow_entity()
            except NoResultFound:
                raise MlflowException(
                    f"Workspace group permission not found for workspace={workspace}, group_id={group_id}",
                    RESOURCE_DOES_NOT_EXIST,
                )

    def create(
        self, workspace: str, group_id: int, permission: str
    ) -> WorkspaceGroupPermission:
        """Create a workspace permission for a group.

        Parameters:
            workspace: The workspace name.
            group_id: The group's ID.
            permission: The permission level.

        Returns:
            WorkspaceGroupPermission entity.

        Raises:
            MlflowException: If a permission already exists for this workspace+group.
        """
        with self.ManagedSessionMaker() as session:
            try:
                perm = SqlWorkspaceGroupPermission(
                    workspace=workspace, group_id=group_id, permission=permission
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError:
                raise MlflowException(
                    f"Workspace group permission already exists for workspace={workspace}, group_id={group_id}",
                    RESOURCE_ALREADY_EXISTS,
                )

    def update(
        self, workspace: str, group_id: int, permission: str
    ) -> WorkspaceGroupPermission:
        """Update a group's workspace permission.

        Parameters:
            workspace: The workspace name.
            group_id: The group's ID.
            permission: The new permission level.

        Returns:
            Updated WorkspaceGroupPermission entity.

        Raises:
            MlflowException: If the permission does not exist.
        """
        with self.ManagedSessionMaker() as session:
            try:
                perm = (
                    session.query(SqlWorkspaceGroupPermission)
                    .filter(
                        SqlWorkspaceGroupPermission.workspace == workspace,
                        SqlWorkspaceGroupPermission.group_id == group_id,
                    )
                    .one()
                )
                perm.permission = permission
                session.flush()
                return perm.to_mlflow_entity()
            except NoResultFound:
                raise MlflowException(
                    f"Workspace group permission not found for workspace={workspace}, group_id={group_id}",
                    RESOURCE_DOES_NOT_EXIST,
                )

    def delete(self, workspace: str, group_id: int) -> None:
        """Delete a group's workspace permission.

        Parameters:
            workspace: The workspace name.
            group_id: The group's ID.

        Raises:
            MlflowException: If the permission does not exist.
        """
        with self.ManagedSessionMaker() as session:
            try:
                perm = (
                    session.query(SqlWorkspaceGroupPermission)
                    .filter(
                        SqlWorkspaceGroupPermission.workspace == workspace,
                        SqlWorkspaceGroupPermission.group_id == group_id,
                    )
                    .one()
                )
                session.delete(perm)
                session.flush()
            except NoResultFound:
                raise MlflowException(
                    f"Workspace group permission not found for workspace={workspace}, group_id={group_id}",
                    RESOURCE_DOES_NOT_EXIST,
                )

    def list_for_group(self, group_id: int) -> list[WorkspaceGroupPermission]:
        """List all workspace permissions for a group.

        Parameters:
            group_id: The group's ID.

        Returns:
            List of WorkspaceGroupPermission entities.
        """
        with self.ManagedSessionMaker() as session:
            perms = (
                session.query(SqlWorkspaceGroupPermission)
                .filter(SqlWorkspaceGroupPermission.group_id == group_id)
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def list_for_workspace(self, workspace: str) -> list[WorkspaceGroupPermission]:
        """List all group permissions in a workspace.

        Parameters:
            workspace: The workspace name.

        Returns:
            List of WorkspaceGroupPermission entities.
        """
        with self.ManagedSessionMaker() as session:
            perms = (
                session.query(SqlWorkspaceGroupPermission)
                .filter(SqlWorkspaceGroupPermission.workspace == workspace)
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def delete_all_for_workspace(self, workspace: str) -> int:
        """Delete all group permissions for a workspace.

        Parameters:
            workspace: The workspace name.

        Returns:
            Number of permission rows deleted.
        """
        with self.ManagedSessionMaker() as session:
            count = (
                session.query(SqlWorkspaceGroupPermission)
                .filter(SqlWorkspaceGroupPermission.workspace == workspace)
                .delete()
            )
            session.flush()
            return count

    def get_highest_for_user(
        self, workspace: str, user_id: int
    ) -> WorkspaceGroupPermission:
        """Get the highest-priority workspace permission across all groups the user belongs to.

        Joins user_groups table to find all groups for the user, then returns the
        highest-priority permission (lowest priority number = highest privilege).

        Parameters:
            workspace: The workspace name.
            user_id: The user's ID.

        Returns:
            WorkspaceGroupPermission with the highest permission level.

        Raises:
            MlflowException: If no group permission exists for this user in this workspace.
        """
        with self.ManagedSessionMaker() as session:
            perms = (
                session.query(SqlWorkspaceGroupPermission)
                .join(
                    SqlUserGroup,
                    SqlWorkspaceGroupPermission.group_id == SqlUserGroup.group_id,
                )
                .filter(
                    SqlWorkspaceGroupPermission.workspace == workspace,
                    SqlUserGroup.user_id == user_id,
                )
                .all()
            )

            if not perms:
                raise MlflowException(
                    f"No workspace group permission found for workspace={workspace}, user_id={user_id}",
                    RESOURCE_DOES_NOT_EXIST,
                )

            # Find highest priority (compare_permissions returns True if p1 <= p2)
            highest = perms[0]
            for p in perms[1:]:
                if compare_permissions(highest.permission, p.permission):
                    highest = p

            return highest.to_mlflow_entity()
