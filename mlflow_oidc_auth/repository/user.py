from typing import Callable, List, Optional

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import (
    RESOURCE_ALREADY_EXISTS,
    RESOURCE_DOES_NOT_EXIST,
)
from mlflow.utils.validation import _validate_username
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import load_only, noload, selectinload
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGroup, SqlUser
from mlflow_oidc_auth.entities import User
from mlflow_oidc_auth.repository.utils import get_user


class UserRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def create(
        self,
        username: str,
        display_name: str,
        is_admin: bool = False,
        is_service_account: bool = False,
    ) -> User:
        _validate_username(username)
        with self._Session() as session:
            try:
                u = SqlUser(
                    username=username,
                    display_name=display_name,
                    is_admin=is_admin,
                    is_service_account=is_service_account,
                )
                session.add(u)
                session.flush()
                return u.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(f"User '{username}' already exists: {e}", RESOURCE_ALREADY_EXISTS) from e

    def get(self, username: str) -> User:
        with self._Session() as session:
            u = session.query(SqlUser).filter(SqlUser.username == username).one_or_none()
            if u is None:
                raise MlflowException(f"User '{username}' not found", RESOURCE_DOES_NOT_EXIST)
            return u.to_mlflow_entity()

    def get_profile(self, username: str) -> User:
        """Fetch a lightweight user entity without loading permission relationships.

        This is intended for common operations (e.g. "who am I" and admin checks)
        where loading experiment/model/scorer permission collections would be
        unnecessarily expensive.

        Returns:
            User: A User entity with groups populated and permission lists empty.

        Raises:
            MlflowException: If the user does not exist.
        """

        with self._Session() as session:
            u = (
                session.query(SqlUser)
                .options(
                    load_only(
                        SqlUser.id,
                        SqlUser.username,
                        SqlUser.display_name,
                        SqlUser.is_admin,
                        SqlUser.is_service_account,
                    ),
                    selectinload(SqlUser.groups).load_only(SqlGroup.id, SqlGroup.group_name),
                    noload(SqlUser.experiment_permissions),
                    noload(SqlUser.registered_model_permissions),
                    noload(SqlUser.scorer_permissions),
                    noload(SqlUser.gateway_endpoint_permissions),
                    noload(SqlUser.gateway_model_definition_permissions),
                    noload(SqlUser.gateway_secret_permissions),
                )
                .filter(SqlUser.username == username)
                .one_or_none()
            )
            if u is None:
                raise MlflowException(f"User '{username}' not found", RESOURCE_DOES_NOT_EXIST)

            return User(
                id_=u.id,
                username=u.username,
                display_name=u.display_name,
                is_admin=u.is_admin,
                is_service_account=u.is_service_account,
                experiment_permissions=[],
                registered_model_permissions=[],
                scorer_permissions=[],
                groups=[g.to_mlflow_entity() for g in u.groups],
            )

    def exist(self, username: str) -> bool:
        with self._Session() as session:
            return session.query(SqlUser).filter(SqlUser.username == username).first() is not None

    def list(self, is_service_account: bool = False, all: bool = False) -> List[User]:
        with self._Session() as session:
            q = session.query(SqlUser)
            if not all:
                q = q.filter(SqlUser.is_service_account == is_service_account)
            return [u.to_mlflow_entity() for u in q.all()]

    def list_usernames(self, is_service_account: bool = False) -> List[str]:
        """Return only usernames without loading any relationships.

        This is much cheaper than ``list()`` because it avoids loading
        experiment/model/scorer/gateway permission collections and groups
        for every user row.
        """
        with self._Session() as session:
            rows = session.query(SqlUser.username).filter(SqlUser.is_service_account == is_service_account).all()
            return [r[0] for r in rows]

    def update(
        self,
        username: str,
        is_admin: Optional[bool] = False,
        is_service_account: Optional[bool] = False,
    ) -> User:
        with self._Session() as session:
            user = get_user(session, username)
            if is_admin is not None:
                user.is_admin = is_admin
            if is_service_account is not None:
                user.is_service_account = is_service_account
            session.flush()
            return user.to_mlflow_entity()

    def delete(self, username: str) -> None:
        with self._Session() as session:
            user = get_user(session, username)
            if user is None:
                raise MlflowException(f"User '{username}' not found.")

            # Delete dependent rows first.
            # Without this, SQLAlchemy may try to NULL-out non-nullable FKs
            # (e.g. experiment_permissions.user_id), causing IntegrityError.
            from mlflow_oidc_auth.db.models import (
                SqlExperimentPermission,
                SqlExperimentRegexPermission,
                SqlGatewayEndpointPermission,
                SqlGatewayEndpointRegexPermission,
                SqlGatewayModelDefinitionPermission,
                SqlGatewayModelDefinitionRegexPermission,
                SqlGatewaySecretPermission,
                SqlGatewaySecretRegexPermission,
                SqlRegisteredModelPermission,
                SqlRegisteredModelRegexPermission,
                SqlScorerPermission,
                SqlScorerRegexPermission,
                SqlUserGroup,
                SqlUserToken,
                SqlWorkspacePermission,
                SqlWorkspaceRegexPermission,
            )

            user_id = user.id

            # Experiment permissions
            session.query(SqlExperimentPermission).filter(SqlExperimentPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlExperimentRegexPermission).filter(SqlExperimentRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Registered model permissions
            session.query(SqlRegisteredModelPermission).filter(SqlRegisteredModelPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlRegisteredModelRegexPermission).filter(SqlRegisteredModelRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Scorer permissions
            session.query(SqlScorerPermission).filter(SqlScorerPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlScorerRegexPermission).filter(SqlScorerRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Gateway endpoint permissions
            session.query(SqlGatewayEndpointPermission).filter(SqlGatewayEndpointPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlGatewayEndpointRegexPermission).filter(SqlGatewayEndpointRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Gateway secret permissions
            session.query(SqlGatewaySecretPermission).filter(SqlGatewaySecretPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlGatewaySecretRegexPermission).filter(SqlGatewaySecretRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Gateway model definition permissions
            session.query(SqlGatewayModelDefinitionPermission).filter(SqlGatewayModelDefinitionPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlGatewayModelDefinitionRegexPermission).filter(SqlGatewayModelDefinitionRegexPermission.user_id == user_id).delete(
                synchronize_session=False
            )

            # Workspace permissions
            session.query(SqlWorkspacePermission).filter(SqlWorkspacePermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlWorkspaceRegexPermission).filter(SqlWorkspaceRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # User tokens
            session.query(SqlUserToken).filter(SqlUserToken.user_id == user_id).delete(synchronize_session=False)

            # Group memberships
            session.query(SqlUserGroup).filter(SqlUserGroup.user_id == user_id).delete(synchronize_session=False)

            session.delete(user)
            session.flush()
