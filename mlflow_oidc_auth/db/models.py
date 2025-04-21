from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

from mlflow_oidc_auth.entities import (
    ExperimentPermission,
    RegisteredModelPermission,
    User,
    Group,
    UserGroup,
)

Base = declarative_base()


class SqlUser(Base):
    __tablename__ = "users"
    id = Column(Integer(), primary_key=True)
    username = Column(String(255), unique=True)
    display_name = Column(String(255))
    password_hash = Column(String(255))
    is_admin = Column(Boolean, default=False)
    is_service_account = Column(Boolean, default=False)
    experiment_permissions = relationship("SqlExperimentPermission", backref="users")
    registered_model_permissions = relationship("SqlRegisteredModelPermission", backref="users")
    groups = relationship("SqlGroup", secondary="user_groups", backref="users")

    def to_mlflow_entity(self):
        return User(
            id_=self.id,
            username=self.username,
            display_name=self.display_name,
            password_hash=self.password_hash,
            is_admin=self.is_admin,
            is_service_account=self.is_service_account,
            experiment_permissions=[p.to_mlflow_entity() for p in self.experiment_permissions],
            registered_model_permissions=[p.to_mlflow_entity() for p in self.registered_model_permissions],
            groups=[g.to_mlflow_entity() for g in self.groups],
        )


class SqlExperimentPermission(Base):
    __tablename__ = "experiment_permissions"
    id = Column(Integer(), primary_key=True)
    experiment_id = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    permission = Column(String(255))
    __table_args__ = (UniqueConstraint("experiment_id", "user_id", name="unique_experiment_user"),)

    def to_mlflow_entity(self):
        return ExperimentPermission(
            experiment_id=self.experiment_id,
            user_id=self.user_id,
            permission=self.permission,
        )


class SqlRegisteredModelPermission(Base):
    __tablename__ = "registered_model_permissions"
    id = Column(Integer(), primary_key=True)
    name = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    permission = Column(String(255))
    __table_args__ = (UniqueConstraint("name", "user_id", name="unique_name_user"),)

    def to_mlflow_entity(self):
        return RegisteredModelPermission(
            name=self.name,
            user_id=self.user_id,
            permission=self.permission,
        )


class SqlGroup(Base):
    __tablename__ = "groups"
    id = Column(Integer(), primary_key=True)
    group_name = Column(String(255), nullable=False)
    __table_args__ = (UniqueConstraint("group_name"),)

    def to_mlflow_entity(self):
        return Group(
            id_=self.id,
            group_name=self.group_name,
        )


class SqlUserGroup(Base):
    __tablename__ = "user_groups"
    id = Column(Integer(), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="unique_user_group"),)

    def to_mlflow_entity(self):
        return UserGroup(
            user_id=self.user_id,
            group_id=self.group_id,
        )


class SqlExperimentGroupPermission(Base):
    __tablename__ = "experiment_group_permissions"
    id = Column(Integer(), primary_key=True)
    experiment_id = Column(String(255), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    permission = Column(String(255))
    __table_args__ = (UniqueConstraint("experiment_id", "group_id", name="unique_experiment_group"),)

    def to_mlflow_entity(self):
        return ExperimentPermission(
            experiment_id=self.experiment_id,
            group_id=self.group_id,
            permission=self.permission,
        )


class SqlRegisteredModelGroupPermission(Base):
    __tablename__ = "registered_model_group_permissions"
    id = Column(Integer(), primary_key=True)
    name = Column(String(255), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    permission = Column(String(255))
    prompt = Column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("name", "group_id", name="unique_name_group"),)

    def to_mlflow_entity(self):
        return RegisteredModelPermission(
            name=self.name,
            group_id=self.group_id,
            permission=self.permission,
            prompt=bool(self.prompt),
        )
