from datetime import datetime

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mlflow_oidc_auth.db.models._base import Base
from mlflow_oidc_auth.entities import User


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
            groups=[g.to_mlflow_entity() for g in self.groups],
        )
