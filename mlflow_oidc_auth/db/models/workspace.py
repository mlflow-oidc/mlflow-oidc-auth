"""SQLAlchemy ORM models for workspace permission tables."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mlflow_oidc_auth.db.models._base import Base
from mlflow_oidc_auth.entities.workspace import (
    WorkspaceGroupPermission,
    WorkspacePermission,
)


class SqlWorkspacePermission(Base):
    """User-level workspace permission. Composite PK: (workspace, user_id)."""

    __tablename__ = "workspace_permissions"

    workspace: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(255), nullable=False)

    user = relationship("SqlUser")

    def to_mlflow_entity(self) -> WorkspacePermission:
        return WorkspacePermission(
            workspace=self.workspace,
            user_id=self.user_id,
            permission=self.permission,
            username=self.user.username if self.user else None,
        )


class SqlWorkspaceGroupPermission(Base):
    """Group-level workspace permission. Composite PK: (workspace, group_id)."""

    __tablename__ = "workspace_group_permissions"

    workspace: Mapped[str] = mapped_column(String(255), primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(255), nullable=False)

    group = relationship("SqlGroup")

    def to_mlflow_entity(self) -> WorkspaceGroupPermission:
        return WorkspaceGroupPermission(
            workspace=self.workspace,
            group_id=self.group_id,
            permission=self.permission,
            group_name=self.group.group_name if self.group else None,
        )
