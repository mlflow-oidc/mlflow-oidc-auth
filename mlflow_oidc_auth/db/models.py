from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from mlflow_oidc_auth.entities import (
    ExperimentGroupRegexPermission,
    ExperimentPermission,
    ExperimentRegexPermission,
    Group,
    RegisteredModelGroupRegexPermission,
    RegisteredModelPermission,
    RegisteredModelRegexPermission,
    User,
    UserGroup,
)


class Base(DeclarativeBase):
    pass


class SqlUser(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_expiration: Mapped[datetime] = mapped_column(nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_service_account: Mapped[bool] = mapped_column(Boolean, default=False)
    experiment_permissions: Mapped[list["SqlExperimentPermission"]] = relationship("SqlExperimentPermission", backref="users")
    registered_model_permissions: Mapped[list["SqlRegisteredModelPermission"]] = relationship("SqlRegisteredModelPermission", backref="users")
    groups: Mapped[list["SqlGroup"]] = relationship(
        "SqlGroup",
        secondary="user_groups",
        back_populates="users",
    )

    def to_mlflow_entity(self):
        return User(
            id_=self.id,
            username=self.username,
            display_name=self.display_name,
            password_hash=self.password_hash,
            password_expiration=self.password_expiration,
            is_admin=self.is_admin,
            is_service_account=self.is_service_account,
            experiment_permissions=[p.to_mlflow_entity() for p in self.experiment_permissions],
            registered_model_permissions=[p.to_mlflow_entity() for p in self.registered_model_permissions],
            groups=[g.to_mlflow_entity() for g in self.groups],
        )


class SqlExperimentPermission(Base):
    __tablename__ = "experiment_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("experiment_id", "user_id", name="unique_experiment_user"),)

    def to_mlflow_entity(self):
        return ExperimentPermission(
            experiment_id=self.experiment_id,
            user_id=self.user_id,
            permission=self.permission,
        )


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


class SqlGroup(Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    __table_args__ = (UniqueConstraint("group_name"),)
    users: Mapped[list["SqlUser"]] = relationship(
        "SqlUser",
        secondary="user_groups",
        back_populates="groups",
    )

    def to_mlflow_entity(self):
        return Group(
            id_=self.id,
            group_name=self.group_name,
        )


class SqlUserGroup(Base):
    __tablename__ = "user_groups"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="unique_user_group"),)

    def to_mlflow_entity(self):
        return UserGroup(
            user_id=self.user_id,
            group_id=self.group_id,
        )


class SqlExperimentGroupPermission(Base):
    __tablename__ = "experiment_group_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("experiment_id", "group_id", name="unique_experiment_group"),)

    def to_mlflow_entity(self):
        return ExperimentPermission(
            experiment_id=self.experiment_id,
            group_id=self.group_id,
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


class SqlExperimentRegexPermission(Base):
    __tablename__ = "experiment_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("regex", "user_id", name="unique_experiment_user_regex"),)

    def to_mlflow_entity(self):
        return ExperimentRegexPermission(
            regex=self.regex,
            priority=self.priority,
            user_id=self.user_id,
            permission=self.permission,
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
            regex=self.regex,
            priority=self.priority,
            user_id=self.user_id,
            permission=self.permission,
            prompt=bool(self.prompt),
        )


class SqlExperimentGroupRegexPermission(Base):
    __tablename__ = "experiment_group_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("regex", "group_id", name="unique_experiment_group_regex"),)

    def to_mlflow_entity(self):
        return ExperimentGroupRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            group_id=self.group_id,
            permission=self.permission,
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
