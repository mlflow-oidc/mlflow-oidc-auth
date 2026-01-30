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
    __table_args__ = (UniqueConstraint("name", "user_id", name="unique_name_user"),)

    def to_mlflow_entity(self):
        return RegisteredModelPermission(
            name=self.name,
            user_id=self.user_id,
            permission=self.permission,
        )


class SqlRegisteredModelGroupPermission(Base):
    __tablename__ = "registered_model_group_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    prompt: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("name", "group_id", name="unique_name_group"),)

    def to_mlflow_entity(self):
        return RegisteredModelPermission(
            name=self.name,
            group_id=self.group_id,
            permission=self.permission,
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
    __table_args__ = (UniqueConstraint("regex", "user_id", "prompt", name="unique_name_user_regex"),)

    def to_mlflow_entity(self):
        return RegisteredModelRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            user_id=self.user_id,
            permission=self.permission,
            prompt=bool(self.prompt),
        )


class SqlRegisteredModelGroupRegexPermission(Base):
    __tablename__ = "registered_model_group_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    prompt: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("regex", "group_id", "prompt", name="unique_name_group_regex"),)

    def to_mlflow_entity(self):
        return RegisteredModelGroupRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            group_id=self.group_id,
            permission=self.permission,
            prompt=bool(self.prompt),
        )
