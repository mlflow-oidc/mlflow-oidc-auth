"""Admin-managed rules that attach a group to a workspace by the group's name (issue #418).

A rule's ``pattern`` is matched with ``re.fullmatch`` against a local group name; its named group
``ws`` is the workspace. The grants a rule creates live in ``workspace_group_permissions`` with
``rule_id`` pointing back here, which is how a rule knows the rows it may change and a manual grant
(``rule_id IS NULL``) is never one of them.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base
from mlflow_oidc_auth.entities.workspace_rule import WorkspaceGroupRule


class SqlWorkspaceGroupRule(Base):
    """One group → workspace rule."""

    __tablename__ = "workspace_group_rules"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    pattern: Mapped[str] = mapped_column(String(256), nullable=False)
    permission: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean(), nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    __table_args__ = (UniqueConstraint("name", name="uq_workspace_group_rules_name"),)

    def to_mlflow_entity(self) -> WorkspaceGroupRule:
        return WorkspaceGroupRule(
            id=self.id,
            name=self.name,
            pattern=self.pattern,
            permission=self.permission,
            mode=self.mode,
            enabled=self.enabled,
            created_by=self.created_by,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
