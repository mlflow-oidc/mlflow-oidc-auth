"""SQLAlchemy ORM models for workspace permission tables."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base


class SqlWorkspacePermission(Base):
    """User-level workspace permission. Composite PK: (workspace, user_id)."""

    __tablename__ = "workspace_permissions"

    workspace: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(255), nullable=False)


class SqlWorkspaceGroupPermission(Base):
    """Group-level workspace permission. Composite PK: (workspace, group_id)."""

    __tablename__ = "workspace_group_permissions"

    workspace: Mapped[str] = mapped_column(String(255), primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(255), nullable=False)
