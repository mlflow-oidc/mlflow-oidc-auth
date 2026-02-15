from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mlflow_oidc_auth.db.models._base import Base
from mlflow_oidc_auth.db.models.experiment import SqlExperimentPermission
from mlflow_oidc_auth.db.models.gateway_endpoint import SqlGatewayEndpointPermission
from mlflow_oidc_auth.db.models.gateway_model_definition import SqlGatewayModelDefinitionPermission
from mlflow_oidc_auth.db.models.gateway_secret import SqlGatewaySecretPermission
from mlflow_oidc_auth.db.models.registered_model import SqlRegisteredModelPermission
from mlflow_oidc_auth.db.models.scorer import SqlScorerPermission
from mlflow_oidc_auth.entities import Group, User, UserGroup


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
    scorer_permissions: Mapped[list["SqlScorerPermission"]] = relationship("SqlScorerPermission", backref="users")
    gateway_endpoint_permissions: Mapped[list["SqlGatewayEndpointPermission"]] = relationship("SqlGatewayEndpointPermission", backref="users")
    gateway_model_definition_permissions: Mapped[list["SqlGatewayModelDefinitionPermission"]] = relationship(
        "SqlGatewayModelDefinitionPermission", backref="users"
    )
    gateway_secret_permissions: Mapped[list["SqlGatewaySecretPermission"]] = relationship("SqlGatewaySecretPermission", backref="users")
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
            scorer_permissions=[p.to_mlflow_entity() for p in self.scorer_permissions],
            gateway_endpoint_permissions=[p.to_mlflow_entity() for p in self.gateway_endpoint_permissions],
            gateway_model_definition_permissions=[p.to_mlflow_entity() for p in self.gateway_model_definition_permissions],
            gateway_secret_permissions=[p.to_mlflow_entity() for p in self.gateway_secret_permissions],
            groups=[g.to_mlflow_entity() for g in self.groups],
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
