from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base
from mlflow_oidc_auth.entities import RegisteredModelGroupRegexPermission, RegisteredModelPermission, RegisteredModelRegexPermission


class SqlRegisteredModelPermission(Base):
    __tablename__ = "registered_model_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    # The workspace of the resource this grant names (see utils/grant_workspace.py). NULL only for
    # a grant from before the column existed, until the startup backfill assigns one.
    workspace: Mapped[Optional[str]] = mapped_column(String(63), nullable=True)
    __table_args__ = (UniqueConstraint("workspace", "name", "user_id", name="uq_rm_perm_workspace_name_user"),)

    def to_mlflow_entity(self):
        return RegisteredModelPermission(
            name=self.name,
            user_id=self.user_id,
            permission=self.permission,
            workspace=self.workspace,
        )


class SqlRegisteredModelGroupPermission(Base):
    __tablename__ = "registered_model_group_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    # The workspace of the resource this grant names (see utils/grant_workspace.py). NULL only for
    # a grant from before the column existed, until the startup backfill assigns one.
    workspace: Mapped[Optional[str]] = mapped_column(String(63), nullable=True)
    prompt: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("workspace", "name", "group_id", name="uq_rm_group_perm_workspace_name_group"),)

    def to_mlflow_entity(self):
        return RegisteredModelPermission(
            name=self.name,
            group_id=self.group_id,
            permission=self.permission,
            workspace=self.workspace,
            prompt=bool(self.prompt),
        )


class SqlRegisteredModelRegexPermission(Base):
    __tablename__ = "registered_model_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    prompt: Mapped[bool] = mapped_column(Boolean, default=False)
    # The workspace the pattern applies in, or "*" for every workspace (utils/grant_workspace.py).
    workspace: Mapped[str] = mapped_column(String(63), nullable=False, default="*", server_default="*")
    __table_args__ = (UniqueConstraint("regex", "user_id", "prompt", "workspace", name="uq_name_user_regex_ws"),)

    def to_mlflow_entity(self):
        entity = RegisteredModelRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            user_id=self.user_id,
            permission=self.permission,
            prompt=bool(self.prompt),
        )
        entity.workspace = self.workspace
        return entity


class SqlRegisteredModelGroupRegexPermission(Base):
    __tablename__ = "registered_model_group_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    prompt: Mapped[bool] = mapped_column(Boolean, default=False)
    # The workspace the pattern applies in, or "*" for every workspace (utils/grant_workspace.py).
    workspace: Mapped[str] = mapped_column(String(63), nullable=False, default="*", server_default="*")
    __table_args__ = (UniqueConstraint("regex", "group_id", "prompt", "workspace", name="uq_name_group_regex_ws"),)

    def to_mlflow_entity(self):
        entity = RegisteredModelGroupRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            group_id=self.group_id,
            permission=self.permission,
            prompt=bool(self.prompt),
        )
        entity.workspace = self.workspace
        return entity
