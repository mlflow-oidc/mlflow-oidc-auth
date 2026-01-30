from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mlflow_oidc_auth.db.models import SqlUser
from mlflow_oidc_auth.db.models._base import Base
from mlflow_oidc_auth.entities import Group, UserGroup


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
