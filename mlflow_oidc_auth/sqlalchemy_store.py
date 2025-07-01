from datetime import datetime
from typing import List, Optional

from mlflow.store.db.utils import _get_managed_session_maker, create_sqlalchemy_engine_with_retry
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
    User,
)
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
    UserRepository,
)


class SqlAlchemyStore:
    def init_db(self, db_uri):
        self.db_uri = db_uri
        self.db_type = extract_db_type_from_uri(db_uri)
        self.engine = create_sqlalchemy_engine_with_retry(db_uri)
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

    def authenticate_user(self, username: str, password: str) -> bool:
        return self.user_repo.authenticate(username, password)

    def create_user(self, username: str, password: str, display_name: str, is_admin: bool = False, is_service_account=False):
        return self.user_repo.create(username, password, display_name, is_admin, is_service_account)

    def has_user(self, username: str) -> bool:
        return self.user_repo.exist(username)

    def get_user(self, username: str) -> User:
        return self.user_repo.get(username)

    def list_users(self, is_service_account: bool = False, all: bool = False) -> List[User]:
        return self.user_repo.list(is_service_account, all)

    def update_user(
        self,
        username: str,
        password: Optional[str] = None,
        password_expiration: Optional[datetime] = None,
        is_admin: Optional[bool] = None,
        is_service_account: Optional[bool] = None,
    ) -> User:
        return self.user_repo.update(
            username=username,
            password=password,
            password_expiration=password_expiration,
            is_admin=is_admin,
            is_service_account=is_service_account,
        )

    def delete_user(self, username: str):
        return self.user_repo.delete(username)

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
        return self.experiment_regex_repo.update(regex=regex, priority=priority, permission=permission, username=username, id=id)

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
        return self.registered_model_group_regex_repo.update(id=id, group_name=group_name, regex=regex, priority=priority, permission=permission)

    def delete_group_registered_model_regex_permission(self, group_name: str, id: int) -> None:
        return self.registered_model_group_regex_repo.revoke(group_name=group_name, id=id)

    # Prompt regex CRUD
    def create_prompt_regex_permission(self, regex: str, priority: int, permission: str, username: str, prompt: bool = True):
        return self.prompt_regex_repo.grant(regex=regex, priority=priority, permission=permission, username=username, prompt=prompt)

    def get_prompt_regex_permission(self, id: int, username: str, prompt: bool = True) -> RegisteredModelRegexPermission:
        return self.prompt_regex_repo.get(id=id, username=username, prompt=prompt)

    def list_prompt_regex_permissions(self, username: str, prompt: bool = True) -> List[RegisteredModelRegexPermission]:
        return self.prompt_regex_repo.list_regex_for_user(username=username, prompt=prompt)

    def update_prompt_regex_permission(
        self, id: int, regex: str, priority: int, permission: str, username: str, prompt: bool = True
    ) -> RegisteredModelRegexPermission:
        return self.prompt_regex_repo.update(id=id, regex=regex, priority=priority, permission=permission, username=username, prompt=prompt)

    def delete_prompt_regex_permission(self, id: int, username: str) -> None:
        return self.prompt_regex_repo.revoke(id=id, username=username, prompt=True)

    # Prompt regex group CRUD
    def create_group_prompt_regex_permission(self, regex: str, priority: int, permission: str, group_name: str, prompt: bool = True):
        return self.prompt_group_regex_repo.grant(regex=regex, priority=priority, permission=permission, group_name=group_name, prompt=prompt)

    def get_group_prompt_regex_permission(self, id: int, group_name: str, prompt: bool = True) -> RegisteredModelGroupRegexPermission:
        return self.prompt_group_regex_repo.get(id=id, group_name=group_name, prompt=prompt)

    def list_group_prompt_regex_permissions(self, group_name: str, prompt: bool = True) -> List[RegisteredModelGroupRegexPermission]:
        return self.prompt_group_regex_repo.list_permissions_for_group(group_name=group_name, prompt=prompt)

    def list_group_prompt_regex_permissions_for_groups(self, group_names: List[str], prompt: bool = True) -> List[RegisteredModelGroupRegexPermission]:
        return self.prompt_group_regex_repo.list_permissions_for_groups(group_names=group_names, prompt=prompt)

    def list_group_prompt_regex_permissions_for_groups_ids(self, group_ids: List[int], prompt: bool = True) -> List[RegisteredModelGroupRegexPermission]:
        return self.prompt_group_regex_repo.list_permissions_for_groups_ids(group_ids=group_ids, prompt=prompt)

    def update_group_prompt_regex_permission(
        self, id: int, regex: str, priority: int, permission: str, group_name: str, prompt: bool = True
    ) -> RegisteredModelGroupRegexPermission:
        return self.prompt_group_regex_repo.update(id=id, regex=regex, priority=priority, permission=permission, group_name=group_name, prompt=prompt)

    def delete_group_prompt_regex_permission(self, id: int, group_name: str) -> None:
        return self.prompt_group_regex_repo.revoke(id=id, group_name=group_name, prompt=True)
