import functools
from datetime import datetime
from typing import List, Optional

import sqlalchemy
from mlflow.store.db.utils import (
    _get_managed_session_maker,
    _make_parent_dirs_if_sqlite,
)
from mlflow.utils.uri import extract_db_type_from_uri
from sqlalchemy.orm import sessionmaker

from mlflow_oidc_auth.db import utils as dbutils
from mlflow_oidc_auth.entities import (
    ExperimentGroupRegexPermission,
    ExperimentPermission,
    ExperimentRegexPermission,
    RegisteredModelGroupRegexPermission,
    RegisteredModelPermission,
    RegisteredModelRegexPermission,
    ScorerGroupRegexPermission,
    ScorerPermission,
    ScorerRegexPermission,
    User,
    UserToken,
    WorkspaceGroupPermission,
    WorkspaceGroupRegexPermission,
    WorkspacePermission,
    WorkspaceRegexPermission,
)
from mlflow_oidc_auth.entities.gateway_endpoint import (
    GatewayEndpointGroupRegexPermission,
)
from mlflow_oidc_auth.entities.gateway_model_definition import (
    GatewayModelDefinitionGroupRegexPermission,
)
from mlflow_oidc_auth.entities.gateway_secret import GatewaySecretGroupRegexPermission
from mlflow_oidc_auth.repository import (
    ExperimentPermissionGroupRegexRepository,
    ExperimentPermissionGroupRepository,
    ExperimentPermissionRegexRepository,
    ExperimentPermissionRepository,
    GroupRepository,
    PromptPermissionGroupRepository,
    RegisteredModelGroupRegexPermissionRepository,
    RegisteredModelPermissionGroupRepository,
    RegisteredModelPermissionRegexRepository,
    RegisteredModelPermissionRepository,
    ScorerPermissionGroupRegexRepository,
    ScorerPermissionGroupRepository,
    ScorerPermissionRegexRepository,
    ScorerPermissionRepository,
    GatewaySecretPermissionRepository,
    GatewaySecretPermissionRegexRepository,
    GatewaySecretGroupPermissionRepository,
    GatewaySecretPermissionGroupRegexRepository,
    GatewayEndpointPermissionRepository,
    GatewayEndpointPermissionRegexRepository,
    GatewayEndpointGroupPermissionRepository,
    GatewayEndpointPermissionGroupRegexRepository,
    GatewayModelDefinitionPermissionRepository,
    GatewayModelDefinitionPermissionRegexRepository,
    GatewayModelDefinitionGroupPermissionRepository,
    GatewayModelDefinitionPermissionGroupRegexRepository,
    UserRepository,
    UserTokenRepository,
    WorkspacePermissionRepository,
    WorkspaceGroupPermissionRepository,
)
from mlflow_oidc_auth.repository.workspace_regex_permission import (
    WorkspaceRegexPermissionRepository,
)
from mlflow_oidc_auth.repository.workspace_group_regex_permission import (
    WorkspaceGroupRegexPermissionRepository,
)


class SqlAlchemyStore:
    def init_db(self, db_uri):
        self.db_uri = db_uri
        self.db_type = extract_db_type_from_uri(db_uri)
        self.engine = self._create_engine(db_uri)
        dbutils.migrate_if_needed(self.engine, "head")
        SessionMaker = sessionmaker(bind=self.engine)
        self.ManagedSessionMaker = _get_managed_session_maker(SessionMaker, self.db_type)
        self.user_repo = UserRepository(self.ManagedSessionMaker)
        self.experiment_repo = ExperimentPermissionRepository(self.ManagedSessionMaker)
        self.experiment_group_repo = ExperimentPermissionGroupRepository(self.ManagedSessionMaker)
        self.group_repo = GroupRepository(self.ManagedSessionMaker)
        self.registered_model_repo = RegisteredModelPermissionRepository(self.ManagedSessionMaker)
        self.registered_model_group_repo = RegisteredModelPermissionGroupRepository(self.ManagedSessionMaker)
        self.prompt_group_repo = PromptPermissionGroupRepository(self.ManagedSessionMaker)
        self.experiment_regex_repo = ExperimentPermissionRegexRepository(self.ManagedSessionMaker)
        self.experiment_group_regex_repo = ExperimentPermissionGroupRegexRepository(self.ManagedSessionMaker)
        self.registered_model_regex_repo = RegisteredModelPermissionRegexRepository(self.ManagedSessionMaker)
        self.registered_model_group_regex_repo = RegisteredModelGroupRegexPermissionRepository(self.ManagedSessionMaker)
        self.prompt_group_regex_repo = RegisteredModelGroupRegexPermissionRepository(self.ManagedSessionMaker)
        self.prompt_regex_repo = RegisteredModelPermissionRegexRepository(self.ManagedSessionMaker)

        # Scorer permissions
        self.scorer_repo = ScorerPermissionRepository(self.ManagedSessionMaker)
        self.scorer_group_repo = ScorerPermissionGroupRepository(self.ManagedSessionMaker)
        self.scorer_regex_repo = ScorerPermissionRegexRepository(self.ManagedSessionMaker)
        self.scorer_group_regex_repo = ScorerPermissionGroupRegexRepository(self.ManagedSessionMaker)

        # Gateway permissions
        self.gateway_secret_repo = GatewaySecretPermissionRepository(self.ManagedSessionMaker)
        self.gateway_secret_group_repo = GatewaySecretGroupPermissionRepository(self.ManagedSessionMaker)
        self.gateway_secret_regex_repo = GatewaySecretPermissionRegexRepository(self.ManagedSessionMaker)
        self.gateway_secret_group_regex_repo = GatewaySecretPermissionGroupRegexRepository(self.ManagedSessionMaker)

        self.gateway_endpoint_repo = GatewayEndpointPermissionRepository(self.ManagedSessionMaker)
        self.gateway_endpoint_group_repo = GatewayEndpointGroupPermissionRepository(self.ManagedSessionMaker)
        self.gateway_endpoint_regex_repo = GatewayEndpointPermissionRegexRepository(self.ManagedSessionMaker)
        self.gateway_endpoint_group_regex_repo = GatewayEndpointPermissionGroupRegexRepository(self.ManagedSessionMaker)

        self.gateway_model_definition_repo = GatewayModelDefinitionPermissionRepository(self.ManagedSessionMaker)
        self.gateway_model_definition_group_repo = GatewayModelDefinitionGroupPermissionRepository(self.ManagedSessionMaker)
        self.gateway_model_definition_regex_repo = GatewayModelDefinitionPermissionRegexRepository(self.ManagedSessionMaker)
        self.gateway_model_definition_group_regex_repo = GatewayModelDefinitionPermissionGroupRegexRepository(self.ManagedSessionMaker)

        # User tokens
        self.user_token_repo = UserTokenRepository(self.ManagedSessionMaker)

        # Workspace permissions
        self.workspace_permission_repo = WorkspacePermissionRepository(self.ManagedSessionMaker)
        self.workspace_group_permission_repo = WorkspaceGroupPermissionRepository(self.ManagedSessionMaker)
        self.workspace_regex_permission_repo = WorkspaceRegexPermissionRepository(self.ManagedSessionMaker)
        self.workspace_group_regex_permission_repo = WorkspaceGroupRegexPermissionRepository(self.ManagedSessionMaker)

    @staticmethod
    def _create_engine(db_uri):
        """Create a SQLAlchemy engine with connection pool configuration.

        Uses OIDC_DB_POOL_SIZE, OIDC_DB_POOL_MAX_OVERFLOW, and
        OIDC_DB_POOL_RECYCLE_SECONDS from AppConfig. When a setting is 0
        (default), SQLAlchemy's built-in defaults are used.  SQLite ignores
        pool_size and max_overflow.

        Includes retry logic matching MLflow's create_sqlalchemy_engine_with_retry.
        """
        import time

        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.logger import get_logger

        _logger = get_logger()
        _make_parent_dirs_if_sqlite(db_uri)

        kwargs = {"pool_pre_ping": True}
        if not db_uri.startswith("sqlite"):
            pool_size = getattr(config, "DB_POOL_SIZE", 0)
            max_overflow = getattr(config, "DB_POOL_MAX_OVERFLOW", 0)
            pool_recycle = getattr(config, "DB_POOL_RECYCLE_SECONDS", 0)
            if pool_size:
                kwargs["pool_size"] = pool_size
            if max_overflow:
                kwargs["max_overflow"] = max_overflow
            if pool_recycle:
                kwargs["pool_recycle"] = pool_recycle
            if pool_size or max_overflow or pool_recycle:
                _logger.info(
                    "Auth DB engine pool options: pool_size=%s, max_overflow=%s, pool_recycle=%s",
                    pool_size or "default",
                    max_overflow or "default",
                    pool_recycle or "default",
                )

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            engine = sqlalchemy.create_engine(db_uri, **kwargs)
            try:
                sqlalchemy.inspect(engine)
                return engine
            except Exception as exc:
                if attempt < max_retries:
                    sleep_duration = 0.1 * ((2**attempt) - 1)
                    _logger.warning(
                        "Auth DB engine creation failed (attempt %d/%d): %s. " "Retrying in %.1fs",
                        attempt,
                        max_retries,
                        exc,
                        sleep_duration,
                    )
                    time.sleep(sleep_duration)
                else:
                    raise

    def ping(self) -> bool:
        """Lightweight database connectivity check for health probes.

        Returns:
            True if database is reachable, False otherwise.
        """
        from sqlalchemy import text

        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    # Scorer CRUD (user-scoped)
    def create_scorer_permission(self, experiment_id: str, scorer_name: str, username: str, permission: str) -> ScorerPermission:
        return self.scorer_repo.grant_permission(experiment_id, scorer_name, username, permission)

    def get_scorer_permission(self, experiment_id: str, scorer_name: str, username: str) -> ScorerPermission:
        return self.scorer_repo.get_permission(experiment_id, scorer_name, username)

    def list_scorer_permissions(self, username: str) -> List[ScorerPermission]:
        return self.scorer_repo.list_permissions_for_user(username)

    def update_scorer_permission(self, experiment_id: str, scorer_name: str, username: str, permission: str) -> ScorerPermission:
        return self.scorer_repo.update_permission(experiment_id, scorer_name, username, permission)

    def delete_scorer_permission(self, experiment_id: str, scorer_name: str, username: str) -> None:
        return self.scorer_repo.revoke_permission(experiment_id, scorer_name, username)

    def delete_scorer_permissions_for_scorer(self, experiment_id: str, scorer_name: str) -> None:
        """Delete all stored permissions for a scorer.

        This is used when a scorer is deleted. Unlike experiment permissions (keyed by UUID),
        scorer permissions are keyed by (experiment_id, scorer_name, subject). If the scorer
        is later recreated with the same name, stale permission rows could either conflict
        with inserts or unintentionally grant access.

        Args:
            experiment_id: The experiment ID owning the scorer.
            scorer_name: The scorer name.
        """

        from mlflow_oidc_auth.db.models import (
            SqlScorerGroupPermission,
            SqlScorerPermission,
        )

        with self.ManagedSessionMaker() as session:
            session.query(SqlScorerPermission).filter(
                SqlScorerPermission.experiment_id == experiment_id,
                SqlScorerPermission.scorer_name == scorer_name,
            ).delete(synchronize_session=False)
            session.query(SqlScorerGroupPermission).filter(
                SqlScorerGroupPermission.experiment_id == experiment_id,
                SqlScorerGroupPermission.scorer_name == scorer_name,
            ).delete(synchronize_session=False)
            session.flush()

    # Scorer permissions (group-scoped)
    def create_group_scorer_permission(self, group_name: str, experiment_id: str, scorer_name: str, permission: str):
        return self.scorer_group_repo.grant_group_permission(group_name, experiment_id, scorer_name, permission)

    def update_group_scorer_permission(self, group_name: str, experiment_id: str, scorer_name: str, permission: str) -> ScorerGroupRegexPermission:
        return self.scorer_group_repo.update_group_permission(group_name, experiment_id, scorer_name, permission)

    def delete_group_scorer_permission(self, group_name: str, experiment_id: str, scorer_name: str) -> None:
        return self.scorer_group_repo.revoke_group_permission(group_name, experiment_id, scorer_name)

    def list_group_scorer_permissions(self, group_name: str):
        return self.scorer_group_repo.list_permissions_for_group(group_name)

    def get_user_groups_scorer_permission(self, experiment_id: str, scorer_name: str, username: str):
        return self.scorer_group_repo.get_group_permission_for_user_scorer(experiment_id, scorer_name, username)

    # Scorer regex (user-scoped)
    def create_scorer_regex_permission(self, regex: str, priority: int, permission: str, username: str) -> ScorerRegexPermission:
        return self.scorer_regex_repo.grant(regex=regex, priority=priority, permission=permission, username=username)

    def list_scorer_regex_permissions(self, username: str) -> List[ScorerRegexPermission]:
        return self.scorer_regex_repo.list_regex_for_user(username)

    def get_scorer_regex_permission(self, username: str, id: int) -> ScorerRegexPermission:
        return self.scorer_regex_repo.get(username=username, id=id)

    def update_scorer_regex_permission(self, id: int, regex: str, priority: int, permission: str, username: str) -> ScorerRegexPermission:
        return self.scorer_regex_repo.update(
            id=id,
            regex=regex,
            priority=priority,
            permission=permission,
            username=username,
        )

    def delete_scorer_regex_permission(self, id: int, username: str) -> None:
        return self.scorer_regex_repo.revoke(id=id, username=username)

    # Scorer regex (group-scoped)
    def create_group_scorer_regex_permission(self, group_name: str, regex: str, priority: int, permission: str) -> ScorerGroupRegexPermission:
        return self.scorer_group_regex_repo.grant(group_name=group_name, regex=regex, priority=priority, permission=permission)

    def list_group_scorer_regex_permissions_for_groups_ids(self, group_ids: List[int]) -> List[ScorerGroupRegexPermission]:
        return self.scorer_group_regex_repo.list_permissions_for_groups_ids(group_ids)

    def list_group_scorer_regex_permissions(self, group_name: str) -> List[ScorerGroupRegexPermission]:
        from mlflow_oidc_auth.db.models import SqlGroup

        with self.ManagedSessionMaker() as session:
            group = session.query(SqlGroup).filter(SqlGroup.group_name == group_name).one_or_none()
            if group is None:
                return []
            return self.scorer_group_regex_repo.list_permissions_for_groups_ids([group.id])

    def get_group_scorer_regex_permission(self, group_name: str, id: int) -> ScorerGroupRegexPermission:
        return self.scorer_group_regex_repo.get(group_name=group_name, id=id)

    def update_group_scorer_regex_permission(self, id: int, group_name: str, regex: str, priority: int, permission: str) -> ScorerGroupRegexPermission:
        return self.scorer_group_regex_repo.update(
            id=id,
            group_name=group_name,
            regex=regex,
            priority=priority,
            permission=permission,
        )

    def delete_group_scorer_regex_permission(self, id: int, group_name: str) -> None:
        return self.scorer_group_regex_repo.revoke(id=id, group_name=group_name)

    def authenticate_user(self, username: str, password: str) -> bool:
        """Authenticate a user via the tokens table.

        Checks the provided token against all non-expired tokens for the user.
        Updates last_used_at timestamp on successful authentication.

        Note: Legacy password_hash tokens are migrated to the tokens table
        during database migration, so all authentication goes through this path.
        """
        return self.user_token_repo.authenticate(username, password)

    def authenticate_user_token(self, username: str, token: str) -> bool:
        """Alias for authenticate_user for clarity in token-based auth contexts."""
        return self.user_token_repo.authenticate(username, token)

    def create_user(self, username: str, display_name: str, is_admin: bool = False, is_service_account=False):
        return self.user_repo.create(username, display_name, is_admin, is_service_account)

    def has_user(self, username: str) -> bool:
        return self.user_repo.exist(username)

    def get_user(self, username: str) -> User:
        return self.user_repo.get(username)

    def get_user_profile(self, username: str) -> User:
        """Return a lightweight user entity for UI/admin checks.

        Unlike `get_user`, this method avoids loading permission collections.
        It is suitable for endpoints that only need basic user metadata.
        """

        return self.user_repo.get_profile(username)

    def list_users(self, is_service_account: bool = False, all: bool = False) -> List[User]:
        return self.user_repo.list(is_service_account, all)

    def list_usernames(self, is_service_account: bool = False) -> List[str]:
        """Return only usernames without loading permission relationships."""
        return self.user_repo.list_usernames(is_service_account)

    def update_user(
        self,
        username: str,
        is_admin: Optional[bool] = None,
        is_service_account: Optional[bool] = None,
    ) -> User:
        return self.user_repo.update(
            username=username,
            is_admin=is_admin,
            is_service_account=is_service_account,
        )

    def delete_user(self, username: str):
        return self.user_repo.delete(username)

    # User Token methods
    def create_user_token(
        self,
        username: str,
        name: str,
        token: str,
        expires_at: datetime,
    ) -> UserToken:
        return self.user_token_repo.create(username, name, token, expires_at)

    def list_user_tokens(self, username: str) -> List[UserToken]:
        return self.user_token_repo.list_for_user(username)

    def get_user_token(self, token_id: int, username: str) -> UserToken:
        return self.user_token_repo.get(token_id, username)

    def delete_user_token(self, token_id: int, username: str) -> None:
        return self.user_token_repo.delete(token_id, username)

    def delete_all_user_tokens(self, username: str) -> int:
        return self.user_token_repo.delete_all_for_user(username)

    def create_experiment_permission(self, experiment_id: str, username: str, permission: str) -> ExperimentPermission:
        return self.experiment_repo.grant_permission(experiment_id, username, permission)

    def get_experiment_permission(self, experiment_id: str, username: str) -> ExperimentPermission:
        return self.experiment_repo.get_permission(experiment_id, username)

    def get_user_groups_experiment_permission(self, experiment_id: str, username: str) -> ExperimentPermission:
        return self.experiment_group_repo.get_group_permission_for_user_experiment(experiment_id, username)

    def list_experiment_permissions(self, username: str) -> List[ExperimentPermission]:
        return self.experiment_repo.list_permissions_for_user(username)

    def list_group_experiment_permissions(self, group_name: str) -> List[ExperimentPermission]:
        return self.experiment_group_repo.list_permissions_for_group(group_name)

    def list_group_id_experiment_permissions(self, group_id: int) -> List[ExperimentPermission]:
        return self.experiment_group_repo.list_permissions_for_group_id(group_id)

    def list_user_groups_experiment_permissions(self, username: str) -> List[ExperimentPermission]:
        return self.experiment_group_repo.list_permissions_for_user_groups(username)

    def update_experiment_permission(self, experiment_id: str, username: str, permission: str) -> ExperimentPermission:
        return self.experiment_repo.update_permission(experiment_id, username, permission)

    def delete_experiment_permission(self, experiment_id: str, username: str):
        return self.experiment_repo.revoke_permission(experiment_id, username)

    def create_registered_model_permission(self, name: str, username: str, permission: str) -> RegisteredModelPermission:
        return self.registered_model_repo.create(name, username, permission)

    def get_registered_model_permission(self, name: str, username: str) -> RegisteredModelPermission:
        return self.registered_model_repo.get(name, username)

    def get_user_groups_registered_model_permission(self, name: str, username: str) -> RegisteredModelPermission:
        return self.registered_model_group_repo.get_for_user(name, username)

    def list_registered_model_permissions(self, username: str) -> List[RegisteredModelPermission]:
        return self.registered_model_repo.list_for_user(username)

    def list_user_groups_registered_model_permissions(self, username: str) -> List[RegisteredModelPermission]:
        return self.registered_model_group_repo.list_for_user(username)

    def update_registered_model_permission(self, name: str, username: str, permission: str) -> RegisteredModelPermission:
        return self.registered_model_repo.update(name, username, permission)

    def rename_registered_model_permissions(self, old_name: str, new_name: str):
        return self.registered_model_repo.rename(old_name, new_name)

    def delete_registered_model_permission(self, name: str, username: str):
        return self.registered_model_repo.delete(name, username)

    def wipe_registered_model_permissions(self, name: str):
        return self.registered_model_repo.wipe(name)

    def list_experiment_permissions_for_experiment(self, experiment_id: str) -> List[ExperimentPermission]:
        return self.experiment_repo.list_permissions_for_experiment(experiment_id)

    def populate_groups(self, group_names: List[str]):
        return self.group_repo.create_groups(group_names)

    def get_groups(self) -> List[str]:
        return self.group_repo.list_groups()

    def get_group_users(self, group_name: str) -> List[User]:
        return self.group_repo.list_group_members(group_name)

    def add_user_to_group(self, username: str, group_name: str) -> None:
        return self.group_repo.add_user_to_group(username, group_name)

    def remove_user_from_group(self, username: str, group_name: str) -> None:
        return self.group_repo.remove_user_from_group(username, group_name)

    def get_groups_for_user(self, username: str) -> List[str]:
        return self.group_repo.list_groups_for_user(username)

    def get_groups_ids_for_user(self, username: str) -> List[int]:
        return self.group_repo.list_group_ids_for_user(username)

    def set_user_groups(self, username: str, group_names: List[str]) -> None:
        return self.group_repo.set_groups_for_user(username, group_names)

    def get_group_experiments(self, group_name: str) -> List[ExperimentPermission]:
        return self.experiment_group_repo.list_permissions_for_group(group_name)

    def create_group_experiment_permission(self, group_name: str, experiment_id: str, permission: str) -> ExperimentPermission:
        return self.experiment_group_repo.grant_group_permission(group_name, experiment_id, permission)

    def delete_group_experiment_permission(self, group_name: str, experiment_id: str) -> None:
        return self.experiment_group_repo.revoke_group_permission(group_name, experiment_id)

    def update_group_experiment_permission(self, group_name: str, experiment_id: str, permission: str) -> ExperimentPermission:
        return self.experiment_group_repo.update_group_permission(group_name, experiment_id, permission)

    def get_group_models(self, group_name: str) -> List[RegisteredModelPermission]:
        return self.registered_model_group_repo.get(group_name)

    def create_group_model_permission(self, group_name: str, name: str, permission: str):
        return self.registered_model_group_repo.create(group_name, name, permission)

    def rename_group_model_permissions(self, old_name: str, new_name: str):
        return self.registered_model_group_repo.rename(old_name, new_name)

    def delete_group_model_permission(self, group_name: str, name: str):
        return self.registered_model_group_repo.delete(group_name, name)

    def wipe_group_model_permissions(self, name: str):
        return self.registered_model_group_repo.wipe(name)

    def update_group_model_permission(self, group_name: str, name: str, permission: str):
        return self.registered_model_group_repo.update(group_name, name, permission)

    # Prompt CRUD
    def create_group_prompt_permission(self, group_name: str, name: str, permission: str):
        return self.prompt_group_repo.grant_prompt_permission_to_group(group_name, name, permission)

    def get_group_prompts(self, group_name: str) -> List[RegisteredModelPermission]:
        return self.prompt_group_repo.list_prompt_permissions_for_group(group_name)

    def update_group_prompt_permission(self, group_name: str, name: str, permission: str):
        return self.prompt_group_repo.update_prompt_permission_for_group(group_name, name, permission)

    def delete_group_prompt_permission(self, group_name: str, name: str):
        return self.prompt_group_repo.revoke_prompt_permission_from_group(group_name, name)

    # Experiment regex CRUD
    def create_experiment_regex_permission(self, regex: str, priority: int, permission: str, username: str):
        return self.experiment_regex_repo.grant(regex, priority, permission, username)

    def get_experiment_regex_permission(self, username: str, id: int) -> ExperimentRegexPermission:
        return self.experiment_regex_repo.get(username=username, id=id)

    def list_experiment_regex_permissions(self, username: str) -> List[ExperimentRegexPermission]:
        return self.experiment_regex_repo.list_regex_for_user(username)

    def update_experiment_regex_permission(self, regex: str, priority: int, permission: str, username: str, id: int) -> ExperimentRegexPermission:
        return self.experiment_regex_repo.update(
            regex=regex,
            priority=priority,
            permission=permission,
            username=username,
            id=id,
        )

    def delete_experiment_regex_permission(self, username: str, id: int) -> None:
        return self.experiment_regex_repo.revoke(username=username, id=id)

    # Experiment regex group CRUD
    def create_group_experiment_regex_permission(self, group_name: str, regex: str, priority: int, permission: str) -> ExperimentGroupRegexPermission:
        return self.experiment_group_regex_repo.grant(group_name, regex, priority, permission)

    def get_group_experiment_regex_permission(self, group_name: str, id: int) -> ExperimentGroupRegexPermission:
        return self.experiment_group_regex_repo.get(group_name, id)

    def list_group_experiment_regex_permissions(self, group_name: str) -> List[ExperimentGroupRegexPermission]:
        return self.experiment_group_regex_repo.list_permissions_for_group(group_name)

    def list_group_experiment_regex_permissions_for_groups(self, group_names: List[str]) -> List[ExperimentGroupRegexPermission]:
        return self.experiment_group_regex_repo.list_permissions_for_groups(group_names)

    def list_group_experiment_regex_permissions_for_groups_ids(self, group_ids: List[int]) -> List[ExperimentGroupRegexPermission]:
        return self.experiment_group_regex_repo.list_permissions_for_groups_ids(group_ids)

    def update_group_experiment_regex_permission(self, id: int, group_name: str, regex: str, priority: int, permission: str) -> ExperimentGroupRegexPermission:
        return self.experiment_group_regex_repo.update(id, group_name, regex, priority, permission)

    def delete_group_experiment_regex_permission(self, group_name: str, id: int) -> None:
        return self.experiment_group_regex_repo.revoke(group_name, id)

    # Registered model regex CRUD
    def create_registered_model_regex_permission(self, regex: str, priority: int, permission: str, username: str):
        return self.registered_model_regex_repo.grant(regex, priority, permission, username)

    def get_registered_model_regex_permission(self, id: int, username: str) -> RegisteredModelRegexPermission:
        return self.registered_model_regex_repo.get(id, username)

    def list_registered_model_regex_permissions(self, username: str) -> List[RegisteredModelRegexPermission]:
        return self.registered_model_regex_repo.list_regex_for_user(username)

    def update_registered_model_regex_permission(self, id: int, regex: str, priority: int, permission: str, username: str) -> RegisteredModelRegexPermission:
        return self.registered_model_regex_repo.update(id, regex, priority, permission, username)

    def delete_registered_model_regex_permission(self, id: int, username: str) -> None:
        return self.registered_model_regex_repo.revoke(id, username)

    # Registered model regex group CRUD
    def create_group_registered_model_regex_permission(
        self, group_name: str, regex: str, priority: int, permission: str
    ) -> RegisteredModelGroupRegexPermission:
        return self.registered_model_group_regex_repo.grant(group_name=group_name, regex=regex, priority=priority, permission=permission)

    def get_group_registered_model_regex_permission(self, group_name: str, id: int) -> RegisteredModelGroupRegexPermission:
        return self.registered_model_group_regex_repo.get(id=id, group_name=group_name)

    def list_group_registered_model_regex_permissions(self, group_name: str) -> List[RegisteredModelGroupRegexPermission]:
        return self.registered_model_group_regex_repo.list_permissions_for_group(group_name)

    def list_group_registered_model_regex_permissions_for_groups(self, group_names: List[str]) -> List[RegisteredModelGroupRegexPermission]:
        return self.registered_model_group_regex_repo.list_permissions_for_groups(group_names)

    def list_group_registered_model_regex_permissions_for_groups_ids(self, group_ids: List[int]) -> List[RegisteredModelGroupRegexPermission]:
        return self.registered_model_group_regex_repo.list_permissions_for_groups_ids(group_ids)

    def update_group_registered_model_regex_permission(
        self, id: int, group_name: str, regex: str, priority: int, permission: str
    ) -> RegisteredModelGroupRegexPermission:
        return self.registered_model_group_regex_repo.update(
            id=id,
            group_name=group_name,
            regex=regex,
            priority=priority,
            permission=permission,
        )

    def delete_group_registered_model_regex_permission(self, group_name: str, id: int) -> None:
        return self.registered_model_group_regex_repo.revoke(group_name=group_name, id=id)

    # Prompt regex CRUD
    def create_prompt_regex_permission(
        self,
        regex: str,
        priority: int,
        permission: str,
        username: str,
        prompt: bool = True,
    ):
        return self.prompt_regex_repo.grant(
            regex=regex,
            priority=priority,
            permission=permission,
            username=username,
            prompt=prompt,
        )

    def get_prompt_regex_permission(self, id: int, username: str, prompt: bool = True) -> RegisteredModelRegexPermission:
        return self.prompt_regex_repo.get(id=id, username=username, prompt=prompt)

    def list_prompt_regex_permissions(self, username: str, prompt: bool = True) -> List[RegisteredModelRegexPermission]:
        return self.prompt_regex_repo.list_regex_for_user(username=username, prompt=prompt)

    def update_prompt_regex_permission(
        self,
        id: int,
        regex: str,
        priority: int,
        permission: str,
        username: str,
        prompt: bool = True,
    ) -> RegisteredModelRegexPermission:
        return self.prompt_regex_repo.update(
            id=id,
            regex=regex,
            priority=priority,
            permission=permission,
            username=username,
            prompt=prompt,
        )

    def delete_prompt_regex_permission(self, id: int, username: str) -> None:
        return self.prompt_regex_repo.revoke(id=id, username=username, prompt=True)

    # Prompt regex group CRUD
    def create_group_prompt_regex_permission(
        self,
        regex: str,
        priority: int,
        permission: str,
        group_name: str,
        prompt: bool = True,
    ):
        return self.prompt_group_regex_repo.grant(
            regex=regex,
            priority=priority,
            permission=permission,
            group_name=group_name,
            prompt=prompt,
        )

    def get_group_prompt_regex_permission(self, id: int, group_name: str, prompt: bool = True) -> RegisteredModelGroupRegexPermission:
        return self.prompt_group_regex_repo.get(id=id, group_name=group_name, prompt=prompt)

    def list_group_prompt_regex_permissions(self, group_name: str, prompt: bool = True) -> List[RegisteredModelGroupRegexPermission]:
        return self.prompt_group_regex_repo.list_permissions_for_group(group_name=group_name, prompt=prompt)

    def list_group_prompt_regex_permissions_for_groups(self, group_names: List[str], prompt: bool = True) -> List[RegisteredModelGroupRegexPermission]:
        return self.prompt_group_regex_repo.list_permissions_for_groups(group_names=group_names, prompt=prompt)

    def list_group_prompt_regex_permissions_for_groups_ids(self, group_ids: List[int], prompt: bool = True) -> List[RegisteredModelGroupRegexPermission]:
        return self.prompt_group_regex_repo.list_permissions_for_groups_ids(group_ids=group_ids, prompt=prompt)

    def update_group_prompt_regex_permission(
        self,
        id: int,
        regex: str,
        priority: int,
        permission: str,
        group_name: str,
        prompt: bool = True,
    ) -> RegisteredModelGroupRegexPermission:
        return self.prompt_group_regex_repo.update(
            id=id,
            regex=regex,
            priority=priority,
            permission=permission,
            group_name=group_name,
            prompt=prompt,
        )

    def delete_group_prompt_regex_permission(self, id: int, group_name: str) -> None:
        return self.prompt_group_regex_repo.revoke(id=id, group_name=group_name, prompt=True)

    # gateway_secret_repo
    def create_gateway_secret_permission(self, gateway_name: str, username: str, permission: str):
        return self.gateway_secret_repo.grant_permission(gateway_name, username, permission)

    def get_gateway_secret_permission(self, gateway_name: str, username: str):
        return self.gateway_secret_repo.get_permission(gateway_name, username)

    def list_gateway_secret_permissions(self, username: str):
        return self.gateway_secret_repo.list_permissions_for_user(username)

    def update_gateway_secret_permission(self, gateway_name: str, username: str, permission: str):
        return self.gateway_secret_repo.update_permission(gateway_name, username, permission)

    def delete_gateway_secret_permission(self, gateway_name: str, username: str) -> None:
        return self.gateway_secret_repo.revoke_permission(gateway_name, username)

    def authenticate_user_token(self, username: str, token: str) -> bool:
        return self.user_token_repo.authenticate(username=username, password=token)

    def wipe_gateway_secret_permissions(self, gateway_name: str) -> None:
        """Delete all user and group permissions for a gateway secret."""
        self.gateway_secret_repo.wipe(gateway_name)
        self.gateway_secret_group_repo.wipe(gateway_name)

    # gateway_secret_group_repo
    def create_group_gateway_secret_permission(self, group_name: str, gateway_name: str, permission: str):
        return self.gateway_secret_group_repo.grant_group_permission(group_name, gateway_name, permission)

    def list_group_gateway_secret_permissions(self, group_name: str):
        return self.gateway_secret_group_repo.list_permissions_for_group(group_name)

    def get_user_groups_gateway_secret_permission(self, gateway_name: str, group_name: str):
        return self.gateway_secret_group_repo.get_group_permission_for_user(gateway_name, group_name)

    def update_group_gateway_secret_permission(self, group_name: str, gateway_name: str, permission: str):
        return self.gateway_secret_group_repo.update_group_permission(group_name, gateway_name, permission)

    def delete_group_gateway_secret_permission(self, group_name: str, gateway_name: str):
        return self.gateway_secret_group_repo.revoke_group_permission(group_name, gateway_name)

    # gateway_secret_regex_repo
    def create_gateway_secret_regex_permission(self, regex: str, priority: int, permission: str, username: str):
        return self.gateway_secret_regex_repo.grant(regex, priority, permission, username)

    def get_gateway_secret_regex_permission(self, id: int, username: str):
        return self.gateway_secret_regex_repo.get(id, username)

    def list_gateway_secret_regex_permissions(self, username: str):
        return self.gateway_secret_regex_repo.list_regex_for_user(username)

    def update_gateway_secret_regex_permission(self, id: int, regex: str, priority: int, permission: str, username: str):
        return self.gateway_secret_regex_repo.update(id, regex, priority, permission, username)

    def delete_gateway_secret_regex_permission(self, id: int, username: str):
        return self.gateway_secret_regex_repo.revoke(id, username)

    # gateway_secret_group_regex_repo
    def create_group_gateway_secret_regex_permission(self, group_name: str, regex: str, priority: int, permission: str):
        return self.gateway_secret_group_regex_repo.grant(group_name, regex, priority, permission)

    def get_group_gateway_secret_regex_permission(self, id: int, group_name: str):
        return self.gateway_secret_group_regex_repo.get(id, group_name)

    def list_group_gateway_secret_regex_permissions(self, group_name: str):
        return self.gateway_secret_group_regex_repo.list_permissions_for_group(group_name)

    def list_group_gateway_secret_regex_permissions_for_groups_ids(self, group_ids: List[int]) -> List[GatewaySecretGroupRegexPermission]:
        return self.gateway_secret_group_regex_repo.list_permissions_for_groups_ids(group_ids)

    def update_group_gateway_secret_regex_permission(self, id: int, group_name: str, regex: str, priority: int, permission: str):
        return self.gateway_secret_group_regex_repo.update(id, group_name, regex, priority, permission)

    def delete_group_gateway_secret_regex_permission(self, id: int, group_name: str):
        return self.gateway_secret_group_regex_repo.revoke(id, group_name)

    # gateway_endpoint_repo
    def create_gateway_endpoint_permission(self, gateway_name: str, username: str, permission: str):
        return self.gateway_endpoint_repo.grant_permission(gateway_name, username, permission)

    def get_gateway_endpoint_permission(self, gateway_name: str, username: str):
        return self.gateway_endpoint_repo.get_permission(gateway_name, username)

    def list_gateway_endpoint_permissions(self, username: str):
        return self.gateway_endpoint_repo.list_permissions_for_user(username)

    def update_gateway_endpoint_permission(self, gateway_name: str, username: str, permission: str):
        return self.gateway_endpoint_repo.update_permission(gateway_name, username, permission)

    def delete_gateway_endpoint_permission(self, gateway_name: str, username: str) -> None:
        return self.gateway_endpoint_repo.revoke_permission(gateway_name, username)

    def rename_gateway_endpoint_permissions(self, old_name: str, new_name: str) -> None:
        """Rename all user and group permissions for a gateway endpoint."""
        self.gateway_endpoint_repo.rename(old_name, new_name)
        self.gateway_endpoint_group_repo.rename(old_name, new_name)

    def wipe_gateway_endpoint_permissions(self, gateway_name: str) -> None:
        """Delete all user and group permissions for a gateway endpoint."""
        self.gateway_endpoint_repo.wipe(gateway_name)
        self.gateway_endpoint_group_repo.wipe(gateway_name)

    # gateway_endpoint_group_repo
    def create_group_gateway_endpoint_permission(self, group_name: str, gateway_name: str, permission: str):
        return self.gateway_endpoint_group_repo.grant_group_permission(group_name, gateway_name, permission)

    def list_group_gateway_endpoint_permissions(self, group_name: str):
        return self.gateway_endpoint_group_repo.list_permissions_for_group(group_name)

    def list_group_gateway_endpoint_regex_permissions_for_groups_ids(self, group_ids: List[int]) -> List[GatewayEndpointGroupRegexPermission]:
        return self.gateway_endpoint_group_regex_repo.list_permissions_for_groups_ids(group_ids)

    def get_user_groups_gateway_endpoint_permission(self, gateway_name: str, group_name: str):
        return self.gateway_endpoint_group_repo.get_group_permission_for_user(gateway_name, group_name)

    def update_group_gateway_endpoint_permission(self, group_name: str, gateway_name: str, permission: str):
        return self.gateway_endpoint_group_repo.update_group_permission(group_name, gateway_name, permission)

    def delete_group_gateway_endpoint_permission(self, group_name: str, gateway_name: str):
        return self.gateway_endpoint_group_repo.revoke_group_permission(group_name, gateway_name)

    # gateway_endpoint_regex_repo
    def create_gateway_endpoint_regex_permission(self, regex: str, priority: int, permission: str, username: str):
        return self.gateway_endpoint_regex_repo.grant(regex, priority, permission, username)

    def get_gateway_endpoint_regex_permission(self, id: int, username: str):
        return self.gateway_endpoint_regex_repo.get(id, username)

    def list_gateway_endpoint_regex_permissions(self, username: str):
        return self.gateway_endpoint_regex_repo.list_regex_for_user(username)

    def update_gateway_endpoint_regex_permission(self, id: int, regex: str, priority: int, permission: str, username: str):
        return self.gateway_endpoint_regex_repo.update(id, regex, priority, permission, username)

    def delete_gateway_endpoint_regex_permission(self, id: int, username: str):
        return self.gateway_endpoint_regex_repo.revoke(id, username)

    # gateway_endpoint_group_regex_repo
    def create_group_gateway_endpoint_regex_permission(self, group_name: str, regex: str, priority: int, permission: str):
        return self.gateway_endpoint_group_regex_repo.grant(group_name, regex, priority, permission)

    def get_group_gateway_endpoint_regex_permission(self, id: int, group_name: str):
        return self.gateway_endpoint_group_regex_repo.get(id, group_name)

    def list_group_gateway_endpoint_regex_permissions(self, group_name: str):
        return self.gateway_endpoint_group_regex_repo.list_permissions_for_group(group_name)

    def update_group_gateway_endpoint_regex_permission(self, id: int, group_name: str, regex: str, priority: int, permission: str):
        return self.gateway_endpoint_group_regex_repo.update(id, group_name, regex, priority, permission)

    def delete_group_gateway_endpoint_regex_permission(self, id: int, group_name: str):
        return self.gateway_endpoint_group_regex_repo.revoke(id, group_name)

    # gateway_model_definition_repo
    def create_gateway_model_definition_permission(self, gateway_name: str, username: str, permission: str):
        return self.gateway_model_definition_repo.grant_permission(gateway_name, username, permission)

    def get_gateway_model_definition_permission(self, gateway_name: str, username: str):
        return self.gateway_model_definition_repo.get_permission(gateway_name, username)

    def list_gateway_model_definition_permissions(self, username: str):
        return self.gateway_model_definition_repo.list_permissions_for_user(username)

    def update_gateway_model_definition_permission(self, gateway_name: str, username: str, permission: str):
        return self.gateway_model_definition_repo.update_permission(gateway_name, username, permission)

    def delete_gateway_model_definition_permission(self, gateway_name: str, username: str) -> None:
        return self.gateway_model_definition_repo.revoke_permission(gateway_name, username)

    def wipe_gateway_model_definition_permissions(self, gateway_name: str) -> None:
        """Delete all user and group permissions for a gateway model definition."""
        self.gateway_model_definition_repo.wipe(gateway_name)
        self.gateway_model_definition_group_repo.wipe(gateway_name)

    # gateway_model_definition_group_repo
    def create_group_gateway_model_definition_permission(self, group_name: str, gateway_name: str, permission: str):
        return self.gateway_model_definition_group_repo.grant_group_permission(group_name, gateway_name, permission)

    def list_group_gateway_model_definition_permissions(self, group_name: str):
        return self.gateway_model_definition_group_repo.list_permissions_for_group(group_name)

    def get_user_groups_gateway_model_definition_permission(self, gateway_name: str, group_name: str):
        return self.gateway_model_definition_group_repo.get_group_permission_for_user(gateway_name, group_name)

    def update_group_gateway_model_definition_permission(self, group_name: str, gateway_name: str, permission: str):
        return self.gateway_model_definition_group_repo.update_group_permission(group_name, gateway_name, permission)

    def delete_group_gateway_model_definition_permission(self, group_name: str, gateway_name: str):
        return self.gateway_model_definition_group_repo.revoke_group_permission(group_name, gateway_name)

    # gateway_model_definition_regex_repo
    def create_gateway_model_definition_regex_permission(self, regex: str, priority: int, permission: str, username: str):
        return self.gateway_model_definition_regex_repo.grant(regex, priority, permission, username)

    def get_gateway_model_definition_regex_permission(self, id: int, username: str):
        return self.gateway_model_definition_regex_repo.get(id, username)

    def list_gateway_model_definition_regex_permissions(self, username: str):
        return self.gateway_model_definition_regex_repo.list_regex_for_user(username)

    def update_gateway_model_definition_regex_permission(self, id: int, regex: str, priority: int, permission: str, username: str):
        return self.gateway_model_definition_regex_repo.update(id, regex, priority, permission, username)

    def delete_gateway_model_definition_regex_permission(self, id: int, username: str):
        return self.gateway_model_definition_regex_repo.revoke(id, username)

    # gateway_model_definition_group_regex_repo
    def create_group_gateway_model_definition_regex_permission(self, group_name: str, regex: str, priority: int, permission: str):
        return self.gateway_model_definition_group_regex_repo.grant(group_name, regex, priority, permission)

    def get_group_gateway_model_definition_regex_permission(self, id: int, group_name: str):
        return self.gateway_model_definition_group_regex_repo.get(id, group_name)

    def list_group_gateway_model_definition_regex_permissions(self, group_name: str):
        return self.gateway_model_definition_group_regex_repo.list_permissions_for_group(group_name)

    def list_group_gateway_model_definition_regex_permissions_for_groups_ids(self, group_ids: List[int]) -> List[GatewayModelDefinitionGroupRegexPermission]:
        return self.gateway_model_definition_group_regex_repo.list_permissions_for_groups_ids(group_ids)

    def update_group_gateway_model_definition_regex_permission(self, id: int, group_name: str, regex: str, priority: int, permission: str):
        return self.gateway_model_definition_group_regex_repo.update(id, group_name, regex, priority, permission)

    def delete_group_gateway_model_definition_regex_permission(self, id: int, group_name: str):
        return self.gateway_model_definition_group_regex_repo.revoke(id, group_name)

    # Workspace permission CRUD (user-scoped)
    def get_workspace_permission(self, workspace: str, username: str) -> WorkspacePermission:
        """Get a user's workspace permission by username."""
        from mlflow_oidc_auth.repository.utils import get_user

        with self.ManagedSessionMaker() as session:
            user = get_user(session, username)
            return self.workspace_permission_repo.get(workspace, user.id)

    def create_workspace_permission(self, workspace: str, username: str, permission: str) -> WorkspacePermission:
        """Create a workspace permission for a user by username."""
        from mlflow_oidc_auth.repository.utils import get_user

        with self.ManagedSessionMaker() as session:
            user = get_user(session, username)
            return self.workspace_permission_repo.create(workspace, user.id, permission)

    def update_workspace_permission(self, workspace: str, username: str, permission: str) -> WorkspacePermission:
        """Update a user's workspace permission by username."""
        from mlflow_oidc_auth.repository.utils import get_user

        with self.ManagedSessionMaker() as session:
            user = get_user(session, username)
            return self.workspace_permission_repo.update(workspace, user.id, permission)

    def delete_workspace_permission(self, workspace: str, username: str) -> None:
        """Delete a user's workspace permission by username."""
        from mlflow_oidc_auth.repository.utils import get_user

        with self.ManagedSessionMaker() as session:
            user = get_user(session, username)
            self.workspace_permission_repo.delete(workspace, user.id)

    def list_workspace_permissions(self, workspace: str) -> list[WorkspacePermission]:
        """List all user permissions in a workspace."""
        return self.workspace_permission_repo.list_for_workspace(workspace)

    # Workspace permission (group-scoped, via user lookup)
    def get_user_groups_workspace_permission(self, workspace: str, username: str) -> WorkspaceGroupPermission:
        """Get highest workspace group permission for a user (across all their groups)."""
        from mlflow_oidc_auth.repository.utils import get_user

        with self.ManagedSessionMaker() as session:
            user = get_user(session, username)
            return self.workspace_group_permission_repo.get_highest_for_user(workspace, user.id)

    # Workspace group permission CRUD (group-scoped)
    def get_workspace_group_permission(self, workspace: str, group_name: str) -> WorkspaceGroupPermission:
        """Get a group's workspace permission by group name."""
        from mlflow_oidc_auth.repository.utils import get_group

        with self.ManagedSessionMaker() as session:
            group = get_group(session, group_name)
            return self.workspace_group_permission_repo.get(workspace, group.id)

    def create_workspace_group_permission(self, workspace: str, group_name: str, permission: str) -> WorkspaceGroupPermission:
        """Create a workspace permission for a group by group name."""
        from mlflow_oidc_auth.repository.utils import get_group

        with self.ManagedSessionMaker() as session:
            group = get_group(session, group_name)
            return self.workspace_group_permission_repo.create(workspace, group.id, permission)

    def update_workspace_group_permission(self, workspace: str, group_name: str, permission: str) -> WorkspaceGroupPermission:
        """Update a group's workspace permission by group name."""
        from mlflow_oidc_auth.repository.utils import get_group

        with self.ManagedSessionMaker() as session:
            group = get_group(session, group_name)
            return self.workspace_group_permission_repo.update(workspace, group.id, permission)

    def delete_workspace_group_permission(self, workspace: str, group_name: str) -> None:
        """Delete a group's workspace permission by group name."""
        from mlflow_oidc_auth.repository.utils import get_group

        with self.ManagedSessionMaker() as session:
            group = get_group(session, group_name)
            self.workspace_group_permission_repo.delete(workspace, group.id)

    def list_workspace_group_permissions(self, workspace: str) -> list[WorkspaceGroupPermission]:
        """List all group permissions in a workspace."""
        return self.workspace_group_permission_repo.list_for_workspace(workspace)

    def wipe_workspace_permissions(self, workspace: str) -> int:
        """Delete all user and group permissions for a workspace.

        Used for cascade-delete when a workspace is removed.

        Parameters:
            workspace: The workspace name.

        Returns:
            Total number of permission rows deleted (user + group).
        """
        user_count = self.workspace_permission_repo.delete_all_for_workspace(workspace)
        group_count = self.workspace_group_permission_repo.delete_all_for_workspace(workspace)
        return user_count + group_count

    # -- Workspace regex permissions (user-scoped) --

    def create_workspace_regex_permission(self, regex: str, priority: int, permission: str, username: str) -> WorkspaceRegexPermission:
        """Create a user regex workspace permission."""
        return self.workspace_regex_permission_repo.grant(regex, priority, permission, username)

    def get_workspace_regex_permission(self, username: str, id: int) -> WorkspaceRegexPermission:
        """Get a user regex workspace permission."""
        return self.workspace_regex_permission_repo.get(username, id)

    def list_workspace_regex_permissions(self, username: str) -> list[WorkspaceRegexPermission]:
        """List all regex workspace permissions for a user, ordered by priority."""
        return self.workspace_regex_permission_repo.list_regex_for_user(username)

    def list_all_workspace_regex_permissions(self) -> list[WorkspaceRegexPermission]:
        """List all regex workspace permissions (admin view)."""
        return self.workspace_regex_permission_repo.list()

    def update_workspace_regex_permission(self, regex: str, priority: int, permission: str, username: str, id: int) -> WorkspaceRegexPermission:
        """Update a user regex workspace permission."""
        return self.workspace_regex_permission_repo.update(regex, priority, permission, username, id)

    def delete_workspace_regex_permission(self, username: str, id: int) -> None:
        """Delete a user regex workspace permission."""
        self.workspace_regex_permission_repo.revoke(username, id)

    # -- Workspace group regex permissions (group-scoped) --

    def create_workspace_group_regex_permission(self, group_name: str, regex: str, priority: int, permission: str) -> WorkspaceGroupRegexPermission:
        """Create a group regex workspace permission."""
        return self.workspace_group_regex_permission_repo.grant(group_name, regex, priority, permission)

    def get_workspace_group_regex_permission(self, group_name: str, id: int) -> WorkspaceGroupRegexPermission:
        """Get a group regex workspace permission."""
        return self.workspace_group_regex_permission_repo.get(group_name, id)

    def list_workspace_group_regex_permissions(self, group_name: str) -> list[WorkspaceGroupRegexPermission]:
        """List all regex workspace permissions for a group."""
        return self.workspace_group_regex_permission_repo.list_permissions_for_group(group_name)

    def list_workspace_group_regex_permissions_for_groups_ids(self, group_ids: list[int]) -> list[WorkspaceGroupRegexPermission]:
        """List all regex workspace permissions for a list of group IDs."""
        return self.workspace_group_regex_permission_repo.list_permissions_for_groups_ids(group_ids)

    def list_all_workspace_group_regex_permissions(
        self,
    ) -> list[WorkspaceGroupRegexPermission]:
        """List all group regex workspace permissions (admin view)."""
        with self.ManagedSessionMaker() as session:
            from mlflow_oidc_auth.db.models.workspace import (
                SqlWorkspaceGroupRegexPermission,
            )

            rows = session.query(SqlWorkspaceGroupRegexPermission).all()
            return [r.to_mlflow_entity() for r in rows]

    def update_workspace_group_regex_permission(self, id: int, group_name: str, regex: str, priority: int, permission: str) -> WorkspaceGroupRegexPermission:
        """Update a group regex workspace permission."""
        return self.workspace_group_regex_permission_repo.update(id, group_name, regex, priority, permission)

    def delete_workspace_group_regex_permission(self, group_name: str, id: int) -> None:
        """Delete a group regex workspace permission."""
        self.workspace_group_regex_permission_repo.revoke(group_name, id)


# ---------------------------------------------------------------------------
# Permission cache invalidation wiring
# ---------------------------------------------------------------------------
# Every permission CUD (create/update/delete/rename/wipe) method listed below
# will flush the permission resolution cache after successful execution.
# This ensures callers (routers, hooks, after_request handlers) never serve
# stale cached permissions.
# Workspace permission methods are excluded — they have their own dedicated
# cache (workspace_cache) with invalidation already handled in the router layer.
# User management methods (create_user, update_user, delete_user) are excluded
# because they don't directly change permission resolution results.
# set_user_groups IS included because group membership changes affect
# group-scoped permission resolution.

_PERMISSION_CUD_METHODS = [
    # Experiment permissions (user-scoped)
    "create_experiment_permission",
    "update_experiment_permission",
    "delete_experiment_permission",
    # Experiment permissions (group-scoped)
    "create_group_experiment_permission",
    "update_group_experiment_permission",
    "delete_group_experiment_permission",
    # Experiment regex permissions (user-scoped)
    "create_experiment_regex_permission",
    "update_experiment_regex_permission",
    "delete_experiment_regex_permission",
    # Experiment regex permissions (group-scoped)
    "create_group_experiment_regex_permission",
    "update_group_experiment_regex_permission",
    "delete_group_experiment_regex_permission",
    # Registered model permissions (user-scoped)
    "create_registered_model_permission",
    "update_registered_model_permission",
    "delete_registered_model_permission",
    "rename_registered_model_permissions",
    "wipe_registered_model_permissions",
    # Registered model permissions (group-scoped)
    "create_group_model_permission",
    "update_group_model_permission",
    "delete_group_model_permission",
    "rename_group_model_permissions",
    "wipe_group_model_permissions",
    # Registered model regex permissions (user-scoped)
    "create_registered_model_regex_permission",
    "update_registered_model_regex_permission",
    "delete_registered_model_regex_permission",
    # Registered model regex permissions (group-scoped)
    "create_group_registered_model_regex_permission",
    "update_group_registered_model_regex_permission",
    "delete_group_registered_model_regex_permission",
    # Prompt permissions (group-scoped)
    "create_group_prompt_permission",
    "update_group_prompt_permission",
    "delete_group_prompt_permission",
    # Prompt regex permissions (user-scoped)
    "create_prompt_regex_permission",
    "update_prompt_regex_permission",
    "delete_prompt_regex_permission",
    # Prompt regex permissions (group-scoped)
    "create_group_prompt_regex_permission",
    "update_group_prompt_regex_permission",
    "delete_group_prompt_regex_permission",
    # Scorer permissions (user-scoped)
    "create_scorer_permission",
    "update_scorer_permission",
    "delete_scorer_permission",
    "delete_scorer_permissions_for_scorer",
    # Scorer permissions (group-scoped)
    "create_group_scorer_permission",
    "update_group_scorer_permission",
    "delete_group_scorer_permission",
    # Scorer regex permissions (user-scoped)
    "create_scorer_regex_permission",
    "update_scorer_regex_permission",
    "delete_scorer_regex_permission",
    # Scorer regex permissions (group-scoped)
    "create_group_scorer_regex_permission",
    "update_group_scorer_regex_permission",
    "delete_group_scorer_regex_permission",
    # Gateway endpoint permissions (user-scoped)
    "create_gateway_endpoint_permission",
    "update_gateway_endpoint_permission",
    "delete_gateway_endpoint_permission",
    "rename_gateway_endpoint_permissions",
    "wipe_gateway_endpoint_permissions",
    # Gateway endpoint permissions (group-scoped)
    "create_group_gateway_endpoint_permission",
    "update_group_gateway_endpoint_permission",
    "delete_group_gateway_endpoint_permission",
    # Gateway endpoint regex permissions (user-scoped)
    "create_gateway_endpoint_regex_permission",
    "update_gateway_endpoint_regex_permission",
    "delete_gateway_endpoint_regex_permission",
    # Gateway endpoint regex permissions (group-scoped)
    "create_group_gateway_endpoint_regex_permission",
    "update_group_gateway_endpoint_regex_permission",
    "delete_group_gateway_endpoint_regex_permission",
    # Gateway secret permissions (user-scoped)
    "create_gateway_secret_permission",
    "update_gateway_secret_permission",
    "delete_gateway_secret_permission",
    "wipe_gateway_secret_permissions",
    # Gateway secret permissions (group-scoped)
    "create_group_gateway_secret_permission",
    "update_group_gateway_secret_permission",
    "delete_group_gateway_secret_permission",
    # Gateway secret regex permissions (user-scoped)
    "create_gateway_secret_regex_permission",
    "update_gateway_secret_regex_permission",
    "delete_gateway_secret_regex_permission",
    # Gateway secret regex permissions (group-scoped)
    "create_group_gateway_secret_regex_permission",
    "update_group_gateway_secret_regex_permission",
    "delete_group_gateway_secret_regex_permission",
    # Gateway model definition permissions (user-scoped)
    "create_gateway_model_definition_permission",
    "update_gateway_model_definition_permission",
    "delete_gateway_model_definition_permission",
    "wipe_gateway_model_definition_permissions",
    # Gateway model definition permissions (group-scoped)
    "create_group_gateway_model_definition_permission",
    "update_group_gateway_model_definition_permission",
    "delete_group_gateway_model_definition_permission",
    # Gateway model definition regex permissions (user-scoped)
    "create_gateway_model_definition_regex_permission",
    "update_gateway_model_definition_regex_permission",
    "delete_gateway_model_definition_regex_permission",
    # Gateway model definition regex permissions (group-scoped)
    "create_group_gateway_model_definition_regex_permission",
    "update_group_gateway_model_definition_regex_permission",
    "delete_group_gateway_model_definition_regex_permission",
    # Group membership (affects group-scoped permission resolution)
    "set_user_groups",
    "add_user_to_group",
    "remove_user_from_group",
]


def _wrap_with_cache_flush(method):
    """Wrap a store method to flush the permission cache after successful execution."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        result = method(self, *args, **kwargs)
        # Lazy import to avoid circular dependency at module load time
        from mlflow_oidc_auth.utils.permissions import flush_permission_cache

        flush_permission_cache()
        return result

    return wrapper


for _method_name in _PERMISSION_CUD_METHODS:
    _original = getattr(SqlAlchemyStore, _method_name)
    setattr(SqlAlchemyStore, _method_name, _wrap_with_cache_flush(_original))
