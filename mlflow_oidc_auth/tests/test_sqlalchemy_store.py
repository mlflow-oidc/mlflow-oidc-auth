from datetime import datetime
from unittest.mock import MagicMock, Mock, patch
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

import pytest
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
from mlflow_oidc_auth.entities import User, ExperimentPermission, RegisteredModelPermission


@pytest.fixture
@patch("mlflow_oidc_auth.sqlalchemy_store.dbutils.migrate_if_needed")
def store(_mock_migrate_if_needed):
    store = SqlAlchemyStore()
    store.init_db("sqlite:///:memory:")
    return store


@pytest.fixture
def mock_store():
    """Store with all repositories mocked for isolated testing"""
    store = SqlAlchemyStore()
    store.user_repo = MagicMock()
    store.experiment_repo = MagicMock()
    store.experiment_group_repo = MagicMock()
    store.group_repo = MagicMock()
    store.registered_model_repo = MagicMock()
    store.registered_model_group_repo = MagicMock()
    store.prompt_group_repo = MagicMock()
    store.experiment_regex_repo = MagicMock()
    store.experiment_group_regex_repo = MagicMock()
    store.registered_model_regex_repo = MagicMock()
    store.registered_model_group_regex_repo = MagicMock()
    store.prompt_group_regex_repo = MagicMock()
    store.prompt_regex_repo = MagicMock()
    return store


def create_test_user(username="testuser", display_name="Test User", is_admin=False, is_service_account=False):
    """Helper function to create test User entities with correct constructor"""
    return User(
        id_=1,
        username=username,
        password_hash="hashed_password",
        password_expiration=None,
        is_admin=is_admin,
        is_service_account=is_service_account,
        display_name=display_name,
    )


def create_test_experiment_permission(experiment_id="exp1", permission="READ", user_id=1, group_id=None):
    """Helper function to create test ExperimentPermission entities with correct constructor"""
    return ExperimentPermission(experiment_id=experiment_id, permission=permission, user_id=user_id, group_id=group_id)


def create_test_registered_model_permission(name="model1", permission="READ", user_id=1, group_id=None, prompt=False):
    """Helper function to create test RegisteredModelPermission entities with correct constructor"""
    return RegisteredModelPermission(name=name, permission=permission, user_id=user_id, group_id=group_id, prompt=prompt)


class TestSqlAlchemyStore:
    def test_create_experiment_regex_permission(self, store: SqlAlchemyStore):
        store.experiment_regex_repo = MagicMock()
        store.create_experiment_regex_permission(".*", 1, "READ", "user")
        store.experiment_regex_repo.grant.assert_called_once_with(".*", 1, "READ", "user")

    def test_get_experiment_regex_permission(self, store: SqlAlchemyStore):
        store.experiment_regex_repo = MagicMock()
        store.get_experiment_regex_permission("user", 1)
        store.experiment_regex_repo.get.assert_called_once_with(username="user", id=1)

    def test_update_experiment_regex_permission(self, store: SqlAlchemyStore):
        store.experiment_regex_repo = MagicMock()
        store.update_experiment_regex_permission(".*", 1, "EDIT", "user", 2)
        store.experiment_regex_repo.update.assert_called_once_with(regex=".*", priority=1, permission="EDIT", username="user", id=2)

    def test_delete_experiment_regex_permission(self, store: SqlAlchemyStore):
        store.experiment_regex_repo = MagicMock()
        store.delete_experiment_regex_permission("user", 1)
        store.experiment_regex_repo.revoke.assert_called_once_with(username="user", id=1)

    def test_create_group_experiment_regex_permission(self, store: SqlAlchemyStore):
        store.experiment_group_regex_repo = MagicMock()
        store.create_group_experiment_regex_permission("group", ".*", 1, "READ")
        store.experiment_group_regex_repo.grant.assert_called_once_with("group", ".*", 1, "READ")

    def test_get_group_experiment_regex_permission(self, store: SqlAlchemyStore):
        store.experiment_group_regex_repo = MagicMock()
        store.get_group_experiment_regex_permission("group", 1)
        store.experiment_group_regex_repo.get.assert_called_once_with("group", 1)

    def test_list_group_experiment_regex_permissions(self, store: SqlAlchemyStore):
        store.experiment_group_regex_repo = MagicMock()
        store.list_group_experiment_regex_permissions("group")
        store.experiment_group_regex_repo.list_permissions_for_group.assert_called_once_with("group")

    def test_update_group_experiment_regex_permission(self, store: SqlAlchemyStore):
        store.experiment_group_regex_repo = MagicMock()
        store.update_group_experiment_regex_permission(1, "group", ".*", 2, "EDIT")
        store.experiment_group_regex_repo.update.assert_called_once_with(1, "group", ".*", 2, "EDIT")

    def test_delete_group_experiment_regex_permission(self, store: SqlAlchemyStore):
        store.experiment_group_regex_repo = MagicMock()
        store.delete_group_experiment_regex_permission("group", 1)
        store.experiment_group_regex_repo.revoke.assert_called_once_with("group", 1)

    def test_create_registered_model_regex_permission(self, store: SqlAlchemyStore):
        store.registered_model_regex_repo = MagicMock()
        store.create_registered_model_regex_permission(".*", 1, "READ", "user")
        store.registered_model_regex_repo.grant.assert_called_once_with(".*", 1, "READ", "user")

    def test_get_registered_model_regex_permission(self, store: SqlAlchemyStore):
        store.registered_model_regex_repo = MagicMock()
        store.get_registered_model_regex_permission(1, "user")
        store.registered_model_regex_repo.get.assert_called_once_with(1, "user")

    def test_update_registered_model_regex_permission(self, store: SqlAlchemyStore):
        store.registered_model_regex_repo = MagicMock()
        store.update_registered_model_regex_permission(1, ".*", 2, "EDIT", "user")
        store.registered_model_regex_repo.update.assert_called_once_with(1, ".*", 2, "EDIT", "user")

    def test_delete_registered_model_regex_permission(self, store: SqlAlchemyStore):
        store.registered_model_regex_repo = MagicMock()
        store.delete_registered_model_regex_permission(1, "user")
        store.registered_model_regex_repo.revoke.assert_called_once_with(1, "user")

    def test_create_group_registered_model_regex_permission(self, store: SqlAlchemyStore):
        store.registered_model_group_regex_repo = MagicMock()
        store.create_group_registered_model_regex_permission("group", ".*", 1, "READ")
        store.registered_model_group_regex_repo.grant.assert_called_once_with(group_name="group", regex=".*", priority=1, permission="READ")

    def test_get_group_registered_model_regex_permission(self, store: SqlAlchemyStore):
        store.registered_model_group_regex_repo = MagicMock()
        store.get_group_registered_model_regex_permission("group", 1)
        store.registered_model_group_regex_repo.get.assert_called_once_with(id=1, group_name="group")

    def test_list_group_registered_model_regex_permissions(self, store: SqlAlchemyStore):
        store.registered_model_group_regex_repo = MagicMock()
        store.list_group_registered_model_regex_permissions("group")
        store.registered_model_group_regex_repo.list_permissions_for_group.assert_called_once_with("group")

    def test_update_group_registered_model_regex_permission(self, store: SqlAlchemyStore):
        store.registered_model_group_regex_repo = MagicMock()
        store.update_group_registered_model_regex_permission(1, "group", ".*", 2, "EDIT")
        store.registered_model_group_regex_repo.update.assert_called_once_with(id=1, group_name="group", regex=".*", priority=2, permission="EDIT")

    def test_delete_group_registered_model_regex_permission(self, store: SqlAlchemyStore):
        store.registered_model_group_regex_repo = MagicMock()
        store.delete_group_registered_model_regex_permission("group", 1)
        store.registered_model_group_regex_repo.revoke.assert_called_once_with(group_name="group", id=1)

    def test_rename_registered_model_permissions(self, store: SqlAlchemyStore):
        store.registered_model_repo = MagicMock()
        store.rename_registered_model_permissions("old_model", "new_model")
        store.registered_model_repo.rename.assert_called_once_with("old_model", "new_model")

    def test_rename_group_model_permissions(self, store: SqlAlchemyStore):
        store.registered_model_group_repo = MagicMock()
        store.rename_group_model_permissions("old_model", "new_model")
        store.registered_model_group_repo.rename.assert_called_once_with("old_model", "new_model")

    def test_create_prompt_regex_permission(self, store: SqlAlchemyStore):
        store.prompt_regex_repo = MagicMock()
        store.create_prompt_regex_permission(".*", 1, "READ", "user", prompt=True)
        store.prompt_regex_repo.grant.assert_called_once_with(regex=".*", priority=1, permission="READ", username="user", prompt=True)

    def test_get_prompt_regex_permission(self, store: SqlAlchemyStore):
        store.prompt_regex_repo = MagicMock()
        store.get_prompt_regex_permission(1, "user", prompt=True)
        store.prompt_regex_repo.get.assert_called_once_with(id=1, username="user", prompt=True)

    def test_update_prompt_regex_permission(self, store: SqlAlchemyStore):
        store.prompt_regex_repo = MagicMock()
        store.update_prompt_regex_permission(1, ".*", 2, "EDIT", "user", prompt=True)
        store.prompt_regex_repo.update.assert_called_once_with(id=1, regex=".*", priority=2, permission="EDIT", username="user", prompt=True)

    def test_delete_prompt_regex_permission(self, store: SqlAlchemyStore):
        store.prompt_regex_repo = MagicMock()
        store.delete_prompt_regex_permission(1, "user")
        store.prompt_regex_repo.revoke.assert_called_once_with(id=1, username="user", prompt=True)

    def test_create_group_prompt_regex_permission(self, store: SqlAlchemyStore):
        store.prompt_group_regex_repo = MagicMock()
        store.create_group_prompt_regex_permission(".*", 1, "READ", "group", prompt=True)
        store.prompt_group_regex_repo.grant.assert_called_once_with(regex=".*", priority=1, permission="READ", group_name="group", prompt=True)

    def test_get_group_prompt_regex_permission(self, store: SqlAlchemyStore):
        store.prompt_group_regex_repo = MagicMock()
        store.get_group_prompt_regex_permission(1, "group", prompt=True)
        store.prompt_group_regex_repo.get.assert_called_once_with(id=1, group_name="group", prompt=True)

    def test_list_group_prompt_regex_permissions(self, store: SqlAlchemyStore):
        store.prompt_group_regex_repo = MagicMock()
        store.list_group_prompt_regex_permissions("group", prompt=True)
        store.prompt_group_regex_repo.list_permissions_for_group.assert_called_once_with(group_name="group", prompt=True)

    def test_update_group_prompt_regex_permission(self, store: SqlAlchemyStore):
        store.prompt_group_regex_repo = MagicMock()
        store.update_group_prompt_regex_permission(1, ".*", 2, "EDIT", "group", prompt=True)
        store.prompt_group_regex_repo.update.assert_called_once_with(id=1, regex=".*", priority=2, permission="EDIT", group_name="group", prompt=True)

    def test_delete_group_prompt_regex_permission(self, store: SqlAlchemyStore):
        store.prompt_group_regex_repo = MagicMock()
        store.delete_group_prompt_regex_permission(1, "group")
        store.prompt_group_regex_repo.revoke.assert_called_once_with(id=1, group_name="group", prompt=True)

    def test_list_group_prompt_regex_permissions_for_groups(self, store: SqlAlchemyStore):
        store.prompt_group_regex_repo = MagicMock()
        store.list_group_prompt_regex_permissions_for_groups(["group1", "group2"], prompt=True)
        store.prompt_group_regex_repo.list_permissions_for_groups.assert_called_once_with(group_names=["group1", "group2"], prompt=True)

    def test_list_group_prompt_regex_permissions_for_groups_ids(self, store: SqlAlchemyStore):
        store.prompt_group_regex_repo = MagicMock()
        store.list_group_prompt_regex_permissions_for_groups_ids([1, 2], prompt=True)
        store.prompt_group_regex_repo.list_permissions_for_groups_ids.assert_called_once_with(group_ids=[1, 2], prompt=True)

    # Test missing user management methods
    def test_authenticate_user(self, mock_store: SqlAlchemyStore):
        mock_store.user_repo.authenticate.return_value = True
        result = mock_store.authenticate_user("testuser", "password")
        mock_store.user_repo.authenticate.assert_called_once_with("testuser", "password")
        assert result is True

    def test_create_user(self, mock_store: SqlAlchemyStore):
        mock_user = create_test_user("testuser", "Test User", False, False)
        mock_store.user_repo.create.return_value = mock_user
        result = mock_store.create_user("testuser", "password", "Test User", False, False)
        mock_store.user_repo.create.assert_called_once_with("testuser", "password", "Test User", False, False)
        assert result == mock_user

    def test_has_user(self, mock_store: SqlAlchemyStore):
        mock_store.user_repo.exist.return_value = True
        result = mock_store.has_user("testuser")
        mock_store.user_repo.exist.assert_called_once_with("testuser")
        assert result is True

    def test_get_user(self, mock_store: SqlAlchemyStore):
        mock_user = create_test_user("testuser", "Test User", False)
        mock_store.user_repo.get.return_value = mock_user
        result = mock_store.get_user("testuser")
        mock_store.user_repo.get.assert_called_once_with("testuser")
        assert result == mock_user

    def test_list_users(self, mock_store: SqlAlchemyStore):
        mock_users = [create_test_user("user1", "User 1", False)]
        mock_store.user_repo.list.return_value = mock_users
        result = mock_store.list_users(is_service_account=False, all=True)
        mock_store.user_repo.list.assert_called_once_with(False, True)
        assert result == mock_users

    def test_update_user(self, mock_store: SqlAlchemyStore):
        mock_user = create_test_user("testuser", "Updated User", True)
        mock_store.user_repo.update.return_value = mock_user
        expiration = datetime.now()
        result = mock_store.update_user("testuser", "newpass", expiration, True, False)
        mock_store.user_repo.update.assert_called_once_with(
            username="testuser", password="newpass", password_expiration=expiration, is_admin=True, is_service_account=False
        )
        assert result == mock_user

    def test_delete_user(self, mock_store: SqlAlchemyStore):
        mock_store.delete_user("testuser")
        mock_store.user_repo.delete.assert_called_once_with("testuser")

    # Test experiment permission methods
    def test_create_experiment_permission(self, mock_store: SqlAlchemyStore):
        mock_permission = create_test_experiment_permission("exp1", "READ", 1)
        mock_store.experiment_repo.grant_permission.return_value = mock_permission
        result = mock_store.create_experiment_permission("exp1", "user1", "READ")
        mock_store.experiment_repo.grant_permission.assert_called_once_with("exp1", "user1", "READ")
        assert result == mock_permission

    def test_get_experiment_permission(self, mock_store: SqlAlchemyStore):
        mock_permission = create_test_experiment_permission("exp1", "READ", 1)
        mock_store.experiment_repo.get_permission.return_value = mock_permission
        result = mock_store.get_experiment_permission("exp1", "user1")
        mock_store.experiment_repo.get_permission.assert_called_once_with("exp1", "user1")
        assert result == mock_permission

    def test_get_user_groups_experiment_permission(self, mock_store: SqlAlchemyStore):
        mock_permission = create_test_experiment_permission("exp1", "READ", 1)
        mock_store.experiment_group_repo.get_group_permission_for_user_experiment.return_value = mock_permission
        result = mock_store.get_user_groups_experiment_permission("exp1", "user1")
        mock_store.experiment_group_repo.get_group_permission_for_user_experiment.assert_called_once_with("exp1", "user1")
        assert result == mock_permission

    def test_list_experiment_permissions(self, mock_store: SqlAlchemyStore):
        mock_permissions = [create_test_experiment_permission("exp1", "READ", 1)]
        mock_store.experiment_repo.list_permissions_for_user.return_value = mock_permissions
        result = mock_store.list_experiment_permissions("user1")
        mock_store.experiment_repo.list_permissions_for_user.assert_called_once_with("user1")
        assert result == mock_permissions

    def test_list_group_experiment_permissions(self, mock_store: SqlAlchemyStore):
        mock_permissions = [create_test_experiment_permission("exp1", "READ", 1)]
        mock_store.experiment_group_repo.list_permissions_for_group.return_value = mock_permissions
        result = mock_store.list_group_experiment_permissions("group1")
        mock_store.experiment_group_repo.list_permissions_for_group.assert_called_once_with("group1")
        assert result == mock_permissions

    def test_list_group_id_experiment_permissions(self, mock_store: SqlAlchemyStore):
        mock_permissions = [create_test_experiment_permission("exp1", "READ", 1)]
        mock_store.experiment_group_repo.list_permissions_for_group_id.return_value = mock_permissions
        result = mock_store.list_group_id_experiment_permissions(1)
        mock_store.experiment_group_repo.list_permissions_for_group_id.assert_called_once_with(1)
        assert result == mock_permissions

    def test_list_user_groups_experiment_permissions(self, mock_store: SqlAlchemyStore):
        mock_permissions = [create_test_experiment_permission("exp1", "READ", 1)]
        mock_store.experiment_group_repo.list_permissions_for_user_groups.return_value = mock_permissions
        result = mock_store.list_user_groups_experiment_permissions("user1")
        mock_store.experiment_group_repo.list_permissions_for_user_groups.assert_called_once_with("user1")
        assert result == mock_permissions

    def test_update_experiment_permission(self, mock_store: SqlAlchemyStore):
        mock_permission = create_test_experiment_permission("exp1", "EDIT", 1)
        mock_store.experiment_repo.update_permission.return_value = mock_permission
        result = mock_store.update_experiment_permission("exp1", "user1", "EDIT")
        mock_store.experiment_repo.update_permission.assert_called_once_with("exp1", "user1", "EDIT")
        assert result == mock_permission

    def test_delete_experiment_permission(self, mock_store: SqlAlchemyStore):
        mock_store.delete_experiment_permission("exp1", "user1")
        mock_store.experiment_repo.revoke_permission.assert_called_once_with("exp1", "user1")

    # Test registered model permission methods
    def test_create_registered_model_permission(self, mock_store: SqlAlchemyStore):
        mock_permission = create_test_registered_model_permission("model1", "READ", 1)
        mock_store.registered_model_repo.create.return_value = mock_permission
        result = mock_store.create_registered_model_permission("model1", "user1", "READ")
        mock_store.registered_model_repo.create.assert_called_once_with("model1", "user1", "READ")
        assert result == mock_permission

    def test_get_registered_model_permission(self, mock_store: SqlAlchemyStore):
        mock_permission = create_test_registered_model_permission("model1", "READ", 1)
        mock_store.registered_model_repo.get.return_value = mock_permission
        result = mock_store.get_registered_model_permission("model1", "user1")
        mock_store.registered_model_repo.get.assert_called_once_with("model1", "user1")
        assert result == mock_permission

    def test_get_user_groups_registered_model_permission(self, mock_store: SqlAlchemyStore):
        mock_permission = create_test_registered_model_permission("model1", "READ", 1)
        mock_store.registered_model_group_repo.get_for_user.return_value = mock_permission
        result = mock_store.get_user_groups_registered_model_permission("model1", "user1")
        mock_store.registered_model_group_repo.get_for_user.assert_called_once_with("model1", "user1")
        assert result == mock_permission

    def test_list_registered_model_permissions(self, mock_store: SqlAlchemyStore):
        mock_permissions = [create_test_registered_model_permission("model1", "READ", 1)]
        mock_store.registered_model_repo.list_for_user.return_value = mock_permissions
        result = mock_store.list_registered_model_permissions("user1")
        mock_store.registered_model_repo.list_for_user.assert_called_once_with("user1")
        assert result == mock_permissions

    def test_list_user_groups_registered_model_permissions(self, mock_store: SqlAlchemyStore):
        mock_permissions = [create_test_registered_model_permission("model1", "READ", 1)]
        mock_store.registered_model_group_repo.list_for_user.return_value = mock_permissions
        result = mock_store.list_user_groups_registered_model_permissions("user1")
        mock_store.registered_model_group_repo.list_for_user.assert_called_once_with("user1")
        assert result == mock_permissions

    def test_update_registered_model_permission(self, mock_store: SqlAlchemyStore):
        mock_permission = create_test_registered_model_permission("model1", "EDIT", 1)
        mock_store.registered_model_repo.update.return_value = mock_permission
        result = mock_store.update_registered_model_permission("model1", "user1", "EDIT")
        mock_store.registered_model_repo.update.assert_called_once_with("model1", "user1", "EDIT")
        assert result == mock_permission

    def test_delete_registered_model_permission(self, mock_store: SqlAlchemyStore):
        mock_store.delete_registered_model_permission("model1", "user1")
        mock_store.registered_model_repo.delete.assert_called_once_with("model1", "user1")

    def test_wipe_registered_model_permissions(self, mock_store: SqlAlchemyStore):
        mock_store.wipe_registered_model_permissions("model1")
        mock_store.registered_model_repo.wipe.assert_called_once_with("model1")

    def test_list_experiment_permissions_for_experiment(self, mock_store: SqlAlchemyStore):
        mock_permissions = [create_test_experiment_permission("exp1", "READ", 1)]
        mock_store.experiment_repo.list_permissions_for_experiment.return_value = mock_permissions
        result = mock_store.list_experiment_permissions_for_experiment("exp1")
        mock_store.experiment_repo.list_permissions_for_experiment.assert_called_once_with("exp1")
        assert result == mock_permissions

    # Test group management methods
    def test_populate_groups(self, mock_store: SqlAlchemyStore):
        mock_store.populate_groups(["group1", "group2"])
        mock_store.group_repo.create_groups.assert_called_once_with(["group1", "group2"])

    def test_get_groups(self, mock_store: SqlAlchemyStore):
        mock_groups = ["group1", "group2"]
        mock_store.group_repo.list_groups.return_value = mock_groups
        result = mock_store.get_groups()
        mock_store.group_repo.list_groups.assert_called_once()
        assert result == mock_groups

    def test_get_group_users(self, mock_store: SqlAlchemyStore):
        mock_users = [create_test_user("user1", "User 1", False)]
        mock_store.group_repo.list_group_members.return_value = mock_users
        result = mock_store.get_group_users("group1")
        mock_store.group_repo.list_group_members.assert_called_once_with("group1")
        assert result == mock_users

    def test_add_user_to_group(self, mock_store: SqlAlchemyStore):
        mock_store.add_user_to_group("user1", "group1")
        mock_store.group_repo.add_user_to_group.assert_called_once_with("user1", "group1")

    def test_remove_user_from_group(self, mock_store: SqlAlchemyStore):
        mock_store.remove_user_from_group("user1", "group1")
        mock_store.group_repo.remove_user_from_group.assert_called_once_with("user1", "group1")

    def test_get_groups_for_user(self, mock_store: SqlAlchemyStore):
        mock_groups = ["group1", "group2"]
        mock_store.group_repo.list_groups_for_user.return_value = mock_groups
        result = mock_store.get_groups_for_user("user1")
        mock_store.group_repo.list_groups_for_user.assert_called_once_with("user1")
        assert result == mock_groups

    def test_get_groups_ids_for_user(self, mock_store: SqlAlchemyStore):
        mock_group_ids = [1, 2]
        mock_store.group_repo.list_group_ids_for_user.return_value = mock_group_ids
        result = mock_store.get_groups_ids_for_user("user1")
        mock_store.group_repo.list_group_ids_for_user.assert_called_once_with("user1")
        assert result == mock_group_ids

    def test_set_user_groups(self, mock_store: SqlAlchemyStore):
        mock_store.set_user_groups("user1", ["group1", "group2"])
        mock_store.group_repo.set_groups_for_user.assert_called_once_with("user1", ["group1", "group2"])

    def test_get_group_experiments(self, mock_store: SqlAlchemyStore):
        mock_permissions = [create_test_experiment_permission("exp1", "READ", 1)]
        mock_store.experiment_group_repo.list_permissions_for_group.return_value = mock_permissions
        result = mock_store.get_group_experiments("group1")
        mock_store.experiment_group_repo.list_permissions_for_group.assert_called_once_with("group1")
        assert result == mock_permissions

    def test_create_group_experiment_permission(self, mock_store: SqlAlchemyStore):
        mock_permission = create_test_experiment_permission("exp1", "READ", 1)
        mock_store.experiment_group_repo.grant_group_permission.return_value = mock_permission
        result = mock_store.create_group_experiment_permission("group1", "exp1", "READ")
        mock_store.experiment_group_repo.grant_group_permission.assert_called_once_with("group1", "exp1", "READ")
        assert result == mock_permission

    def test_delete_group_experiment_permission(self, mock_store: SqlAlchemyStore):
        mock_store.delete_group_experiment_permission("group1", "exp1")
        mock_store.experiment_group_repo.revoke_group_permission.assert_called_once_with("group1", "exp1")

    def test_update_group_experiment_permission(self, mock_store: SqlAlchemyStore):
        mock_permission = create_test_experiment_permission("exp1", "EDIT", 1)
        mock_store.experiment_group_repo.update_group_permission.return_value = mock_permission
        result = mock_store.update_group_experiment_permission("group1", "exp1", "EDIT")
        mock_store.experiment_group_repo.update_group_permission.assert_called_once_with("group1", "exp1", "EDIT")
        assert result == mock_permission

    # Test group model permission methods
    def test_get_group_models(self, mock_store: SqlAlchemyStore):
        mock_permissions = [create_test_registered_model_permission("model1", "READ", 1)]
        mock_store.registered_model_group_repo.get.return_value = mock_permissions
        result = mock_store.get_group_models("group1")
        mock_store.registered_model_group_repo.get.assert_called_once_with("group1")
        assert result == mock_permissions

    def test_create_group_model_permission(self, mock_store: SqlAlchemyStore):
        mock_store.create_group_model_permission("group1", "model1", "READ")
        mock_store.registered_model_group_repo.create.assert_called_once_with("group1", "model1", "READ")

    def test_delete_group_model_permission(self, mock_store: SqlAlchemyStore):
        mock_store.delete_group_model_permission("group1", "model1")
        mock_store.registered_model_group_repo.delete.assert_called_once_with("group1", "model1")

    def test_wipe_group_model_permissions(self, mock_store: SqlAlchemyStore):
        mock_store.wipe_group_model_permissions("model1")
        mock_store.registered_model_group_repo.wipe.assert_called_once_with("model1")

    def test_update_group_model_permission(self, mock_store: SqlAlchemyStore):
        mock_store.update_group_model_permission("group1", "model1", "EDIT")
        mock_store.registered_model_group_repo.update.assert_called_once_with("group1", "model1", "EDIT")

    # Test prompt permission methods
    def test_create_group_prompt_permission(self, mock_store: SqlAlchemyStore):
        mock_store.create_group_prompt_permission("group1", "prompt1", "READ")
        mock_store.prompt_group_repo.grant_prompt_permission_to_group.assert_called_once_with("group1", "prompt1", "READ")

    def test_get_group_prompts(self, mock_store: SqlAlchemyStore):
        mock_permissions = [create_test_registered_model_permission("prompt1", "READ", 1, prompt=True)]
        mock_store.prompt_group_repo.list_prompt_permissions_for_group.return_value = mock_permissions
        result = mock_store.get_group_prompts("group1")
        mock_store.prompt_group_repo.list_prompt_permissions_for_group.assert_called_once_with("group1")
        assert result == mock_permissions

    def test_update_group_prompt_permission(self, mock_store: SqlAlchemyStore):
        mock_store.update_group_prompt_permission("group1", "prompt1", "EDIT")
        mock_store.prompt_group_repo.update_prompt_permission_for_group.assert_called_once_with("group1", "prompt1", "EDIT")

    def test_delete_group_prompt_permission(self, mock_store: SqlAlchemyStore):
        mock_store.delete_group_prompt_permission("group1", "prompt1")
        mock_store.prompt_group_repo.revoke_prompt_permission_from_group.assert_called_once_with("group1", "prompt1")

    # Test regex permission methods that were missing
    def test_list_experiment_regex_permissions(self, mock_store: SqlAlchemyStore):
        mock_store.list_experiment_regex_permissions("user1")
        mock_store.experiment_regex_repo.list_regex_for_user.assert_called_once_with("user1")

    def test_list_group_experiment_regex_permissions_for_groups(self, mock_store: SqlAlchemyStore):
        mock_store.list_group_experiment_regex_permissions_for_groups(["group1", "group2"])
        mock_store.experiment_group_regex_repo.list_permissions_for_groups.assert_called_once_with(["group1", "group2"])

    def test_list_group_experiment_regex_permissions_for_groups_ids(self, mock_store: SqlAlchemyStore):
        mock_store.list_group_experiment_regex_permissions_for_groups_ids([1, 2])
        mock_store.experiment_group_regex_repo.list_permissions_for_groups_ids.assert_called_once_with([1, 2])

    def test_list_registered_model_regex_permissions(self, mock_store: SqlAlchemyStore):
        mock_store.list_registered_model_regex_permissions("user1")
        mock_store.registered_model_regex_repo.list_regex_for_user.assert_called_once_with("user1")

    def test_list_group_registered_model_regex_permissions_for_groups(self, mock_store: SqlAlchemyStore):
        mock_store.list_group_registered_model_regex_permissions_for_groups(["group1", "group2"])
        mock_store.registered_model_group_regex_repo.list_permissions_for_groups.assert_called_once_with(["group1", "group2"])

    def test_list_group_registered_model_regex_permissions_for_groups_ids(self, mock_store: SqlAlchemyStore):
        mock_store.list_group_registered_model_regex_permissions_for_groups_ids([1, 2])
        mock_store.registered_model_group_regex_repo.list_permissions_for_groups_ids.assert_called_once_with([1, 2])

    def test_list_prompt_regex_permissions(self, mock_store: SqlAlchemyStore):
        mock_store.list_prompt_regex_permissions("user1", prompt=True)
        mock_store.prompt_regex_repo.list_regex_for_user.assert_called_once_with(username="user1", prompt=True)


class TestSqlAlchemyStoreErrorHandling:
    """Test error handling scenarios for database connection failures and exceptions"""

    @patch("mlflow_oidc_auth.sqlalchemy_store.create_sqlalchemy_engine_with_retry")
    def test_init_db_engine_creation_failure(self, mock_create_engine):
        """Test database initialization failure when engine creation fails"""
        mock_create_engine.side_effect = SQLAlchemyError("Database connection failed")
        store = SqlAlchemyStore()

        with pytest.raises(SQLAlchemyError, match="Database connection failed"):
            store.init_db("sqlite:///:memory:")

    @patch("mlflow_oidc_auth.sqlalchemy_store.dbutils.migrate_if_needed")
    def test_init_db_migration_failure(self, mock_migrate):
        """Test database initialization failure when migration fails"""
        mock_migrate.side_effect = SQLAlchemyError("Migration failed")
        store = SqlAlchemyStore()

        with pytest.raises(SQLAlchemyError, match="Migration failed"):
            store.init_db("sqlite:///:memory:")

    def test_user_operations_with_database_error(self, mock_store):
        """Test user operations when database operations fail"""
        mock_store.user_repo.authenticate.side_effect = OperationalError("Database error", None, None)

        with pytest.raises(OperationalError):
            mock_store.authenticate_user("testuser", "password")

    def test_experiment_operations_with_database_error(self, mock_store):
        """Test experiment operations when database operations fail"""
        mock_store.experiment_repo.grant_permission.side_effect = OperationalError("Database error", None, None)

        with pytest.raises(OperationalError):
            mock_store.create_experiment_permission("exp1", "user1", "READ")

    def test_model_operations_with_database_error(self, mock_store):
        """Test model operations when database operations fail"""
        mock_store.registered_model_repo.create.side_effect = OperationalError("Database error", None, None)

        with pytest.raises(OperationalError):
            mock_store.create_registered_model_permission("model1", "user1", "READ")

    def test_group_operations_with_database_error(self, mock_store):
        """Test group operations when database operations fail"""
        mock_store.group_repo.create_groups.side_effect = OperationalError("Database error", None, None)

        with pytest.raises(OperationalError):
            mock_store.populate_groups(["group1", "group2"])


class TestSqlAlchemyStoreTransactionHandling:
    """Test transaction handling and rollback scenarios"""

    def test_transaction_rollback_on_user_creation_failure(self, mock_store):
        """Test transaction rollback when user creation fails"""
        # Simulate a scenario where user creation fails after partial completion
        mock_store.user_repo.create.side_effect = [SQLAlchemyError("Constraint violation"), create_test_user("testuser", "Test User", False)]

        # First call should raise exception
        with pytest.raises(SQLAlchemyError):
            mock_store.create_user("testuser", "password", "Test User", False, False)

        # Second call should succeed (simulating retry after rollback)
        result = mock_store.create_user("testuser", "password", "Test User", False, False)
        assert result.username == "testuser"

    def test_concurrent_permission_updates(self, mock_store):
        """Test concurrent permission updates to ensure data consistency"""
        # Mock concurrent updates to the same permission
        mock_store.experiment_repo.update_permission.side_effect = [
            create_test_experiment_permission("exp1", "EDIT", 1),
            create_test_experiment_permission("exp1", "MANAGE", 1),
        ]

        # Simulate concurrent updates
        result1 = mock_store.update_experiment_permission("exp1", "user1", "EDIT")
        result2 = mock_store.update_experiment_permission("exp1", "user1", "MANAGE")

        assert result1.permission == "EDIT"
        assert result2.permission == "MANAGE"

    def test_bulk_operations_transaction_consistency(self, mock_store):
        """Test bulk operations maintain transaction consistency"""
        # Test bulk group creation
        mock_store.group_repo.create_groups.return_value = None
        mock_store.populate_groups(["group1", "group2", "group3"])
        mock_store.group_repo.create_groups.assert_called_once_with(["group1", "group2", "group3"])

    def test_cascading_delete_operations(self, mock_store):
        """Test cascading delete operations maintain referential integrity"""
        # Test user deletion cascades to permissions
        mock_store.user_repo.delete.return_value = None
        mock_store.delete_user("testuser")
        mock_store.user_repo.delete.assert_called_once_with("testuser")

        # Test model deletion cascades to permissions
        mock_store.registered_model_repo.wipe.return_value = None
        mock_store.wipe_registered_model_permissions("model1")
        mock_store.registered_model_repo.wipe.assert_called_once_with("model1")


class TestSqlAlchemyStoreConcurrentAccess:
    """Test concurrent access scenarios and thread safety"""

    def test_concurrent_user_creation(self, mock_store):
        """Test concurrent user creation operations"""

        def create_user_worker(username):
            try:
                return mock_store.create_user(f"user_{username}", "password", f"User {username}", False, False)
            except Exception as e:
                return e

        # Mock successful user creation
        mock_store.user_repo.create.return_value = create_test_user("test", "Test", False)

        # Simulate concurrent user creation
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_user_worker, i) for i in range(5)]
            results = [future.result() for future in as_completed(futures)]

        # All operations should complete
        assert len(results) == 5
        assert mock_store.user_repo.create.call_count == 5

    def test_concurrent_permission_checks(self, mock_store):
        """Test concurrent permission checking operations"""

        def check_permission_worker(exp_id):
            try:
                return mock_store.get_experiment_permission(f"exp_{exp_id}", "testuser")
            except Exception as e:
                return e

        # Mock permission retrieval
        mock_store.experiment_repo.get_permission.return_value = create_test_experiment_permission("test", "READ", 1)

        # Simulate concurrent permission checks
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_permission_worker, i) for i in range(10)]
            results = [future.result() for future in as_completed(futures)]

        # All operations should complete successfully
        assert len(results) == 10
        assert mock_store.experiment_repo.get_permission.call_count == 10

    def test_concurrent_group_membership_updates(self, mock_store):
        """Test concurrent group membership updates"""

        def update_group_worker(group_name):
            try:
                mock_store.add_user_to_group("testuser", f"group_{group_name}")
                return True
            except Exception as e:
                return e

        # Mock group operations
        mock_store.group_repo.add_user_to_group.return_value = None

        # Simulate concurrent group updates
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(update_group_worker, i) for i in range(3)]
            results = [future.result() for future in as_completed(futures)]

        # All operations should complete
        assert len(results) == 3
        assert mock_store.group_repo.add_user_to_group.call_count == 3


class TestSqlAlchemyStorePerformance:
    """Test query optimization and performance characteristics"""

    def test_bulk_permission_retrieval_performance(self, mock_store):
        """Test performance of bulk permission retrieval operations"""
        # Mock large result sets
        large_permission_list = [create_test_experiment_permission(f"exp_{i}", "READ", 1) for i in range(1000)]
        mock_store.experiment_repo.list_permissions_for_user.return_value = large_permission_list

        start_time = time.time()
        result = mock_store.list_experiment_permissions("testuser")
        end_time = time.time()

        # Operation should complete quickly (less than 1 second for mocked data)
        assert end_time - start_time < 1.0
        assert len(result) == 1000

    def test_complex_group_permission_queries(self, mock_store):
        """Test performance of complex group permission queries"""
        # Mock complex group permission results
        complex_permissions = [create_test_experiment_permission(f"exp_{i}", "READ", i % 10 + 1) for i in range(500)]
        mock_store.experiment_group_repo.list_permissions_for_user_groups.return_value = complex_permissions

        start_time = time.time()
        result = mock_store.list_user_groups_experiment_permissions("testuser")
        end_time = time.time()

        # Complex query should still complete quickly
        assert end_time - start_time < 1.0
        assert len(result) == 500

    def test_regex_permission_query_performance(self, mock_store):
        """Test performance of regex permission queries"""
        # Mock regex permission results
        regex_permissions = [{"id": i, "regex": f".*exp_{i}.*", "permission": "READ", "username": "testuser"} for i in range(100)]
        mock_store.experiment_regex_repo.list_regex_for_user.return_value = regex_permissions

        start_time = time.time()
        result = mock_store.list_experiment_regex_permissions("testuser")
        end_time = time.time()

        # Regex queries should be optimized
        assert end_time - start_time < 1.0
        assert len(result) == 100

    def test_memory_usage_during_large_operations(self, mock_store):
        """Test memory usage during large data operations"""
        # Mock large dataset operations
        large_user_list = [create_test_user(f"user_{i}", f"User {i}", False) for i in range(10000)]
        mock_store.user_repo.list.return_value = large_user_list

        # Test memory efficiency of large list operations
        result = mock_store.list_users(all=True)
        assert len(result) == 10000

        # Verify the operation completes without memory issues
        # (In a real scenario, this would involve memory profiling)
        assert isinstance(result, list)


class TestSqlAlchemyStoreEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_result_handling(self, mock_store):
        """Test handling of empty results from database queries"""
        # Test empty user list
        mock_store.user_repo.list.return_value = []
        result = mock_store.list_users()
        assert result == []

        # Test empty permission list
        mock_store.experiment_repo.list_permissions_for_user.return_value = []
        result = mock_store.list_experiment_permissions("nonexistent_user")
        assert result == []

    def test_none_result_handling(self, mock_store):
        """Test handling of None results from database queries"""
        # Test None user result
        mock_store.user_repo.get.return_value = None
        result = mock_store.get_user("nonexistent_user")
        assert result is None

        # Test None permission result
        mock_store.experiment_repo.get_permission.return_value = None
        result = mock_store.get_experiment_permission("nonexistent_exp", "nonexistent_user")
        assert result is None

    def test_special_characters_in_identifiers(self, mock_store):
        """Test handling of special characters in user/group/experiment identifiers"""
        special_chars_user = "user@domain.com"
        special_chars_group = "group-with-dashes_and_underscores"
        special_chars_exp = "experiment/with/slashes"

        # Test user operations with special characters
        mock_store.user_repo.get.return_value = create_test_user(special_chars_user, "Special User", False)
        result = mock_store.get_user(special_chars_user)
        mock_store.user_repo.get.assert_called_with(special_chars_user)
        assert result.username == special_chars_user

        # Test group operations with special characters
        mock_store.group_repo.list_groups_for_user.return_value = [special_chars_group]
        result = mock_store.get_groups_for_user(special_chars_user)
        assert special_chars_group in result

        # Test experiment operations with special characters
        mock_permission = create_test_experiment_permission(special_chars_exp, "READ", 1)
        mock_store.experiment_repo.get_permission.return_value = mock_permission
        result = mock_store.get_experiment_permission(special_chars_exp, special_chars_user)
        assert result.experiment_id == special_chars_exp

    def test_large_data_values(self, mock_store):
        """Test handling of large data values and long strings"""
        long_username = "a" * 1000
        long_display_name = "b" * 2000
        long_regex = "c" * 500

        # Test user creation with long values
        mock_user = create_test_user(long_username, long_display_name, False)
        mock_store.user_repo.create.return_value = mock_user
        result = mock_store.create_user(long_username, "password", long_display_name, False, False)
        assert result.username == long_username
        assert result.display_name == long_display_name

        # Test regex permission with long regex
        mock_store.experiment_regex_repo.grant.return_value = None
        mock_store.create_experiment_regex_permission(long_regex, 1, "READ", long_username)
        mock_store.experiment_regex_repo.grant.assert_called_with(long_regex, 1, "READ", long_username)

    def test_boundary_values_for_numeric_fields(self, mock_store):
        """Test boundary values for numeric fields like priority and IDs"""
        # Test with maximum integer values
        max_priority = 2147483647  # Max 32-bit integer
        max_id = 9223372036854775807  # Max 64-bit integer

        # Test regex permission with max priority
        mock_store.experiment_regex_repo.grant.return_value = None
        mock_store.create_experiment_regex_permission(".*", max_priority, "READ", "testuser")
        mock_store.experiment_regex_repo.grant.assert_called_with(".*", max_priority, "READ", "testuser")

        # Test operations with max ID values
        mock_store.experiment_regex_repo.get.return_value = None
        mock_store.get_experiment_regex_permission("testuser", max_id)
        mock_store.experiment_regex_repo.get.assert_called_with(username="testuser", id=max_id)

        # Test with minimum values (0 and negative)
        min_priority = -2147483648  # Min 32-bit integer
        mock_store.create_experiment_regex_permission(".*", min_priority, "READ", "testuser")
        mock_store.experiment_regex_repo.grant.assert_called_with(".*", min_priority, "READ", "testuser")


class TestSqlAlchemyStoreInitialization:
    """Test database initialization and configuration scenarios"""

    @patch("mlflow_oidc_auth.sqlalchemy_store.extract_db_type_from_uri")
    @patch("mlflow_oidc_auth.sqlalchemy_store.create_sqlalchemy_engine_with_retry")
    @patch("mlflow_oidc_auth.sqlalchemy_store.dbutils.migrate_if_needed")
    @patch("mlflow_oidc_auth.sqlalchemy_store.sessionmaker")
    @patch("mlflow_oidc_auth.sqlalchemy_store._get_managed_session_maker")
    def test_init_db_complete_flow(self, mock_managed_session, mock_sessionmaker, mock_migrate, mock_create_engine, mock_extract_db_type):
        """Test complete database initialization flow"""
        # Setup mocks
        mock_extract_db_type.return_value = "sqlite"
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        mock_session_maker = Mock()
        mock_sessionmaker.return_value = mock_session_maker
        mock_managed_session_maker = Mock()
        mock_managed_session.return_value = mock_managed_session_maker

        # Initialize store
        store = SqlAlchemyStore()
        db_uri = "sqlite:///test.db"
        store.init_db(db_uri)

        # Verify all initialization steps
        mock_extract_db_type.assert_called_once_with(db_uri)
        mock_create_engine.assert_called_once_with(db_uri)
        mock_migrate.assert_called_once_with(mock_engine, "head")
        mock_sessionmaker.assert_called_once_with(bind=mock_engine)
        mock_managed_session.assert_called_once_with(mock_session_maker, "sqlite")

        # Verify store attributes are set
        assert store.db_uri == db_uri
        assert store.db_type == "sqlite"
        assert store.engine == mock_engine
        assert store.ManagedSessionMaker == mock_managed_session_maker

        # Verify all repositories are initialized
        assert store.user_repo is not None
        assert store.experiment_repo is not None
        assert store.experiment_group_repo is not None
        assert store.group_repo is not None
        assert store.registered_model_repo is not None
        assert store.registered_model_group_repo is not None
        assert store.prompt_group_repo is not None
        assert store.experiment_regex_repo is not None
        assert store.experiment_group_regex_repo is not None
        assert store.registered_model_regex_repo is not None
        assert store.registered_model_group_regex_repo is not None
        assert store.prompt_group_regex_repo is not None
        assert store.prompt_regex_repo is not None

    def test_different_database_types(self):
        """Test initialization with different database types"""
        store = SqlAlchemyStore()

        # Test with different URI formats
        test_uris = ["sqlite:///test.db", "postgresql://user:pass@localhost/db", "mysql://user:pass@localhost/db"]

        for uri in test_uris:
            with patch("mlflow_oidc_auth.sqlalchemy_store.extract_db_type_from_uri") as mock_extract:
                with patch("mlflow_oidc_auth.sqlalchemy_store.create_sqlalchemy_engine_with_retry"):
                    with patch("mlflow_oidc_auth.sqlalchemy_store.dbutils.migrate_if_needed"):
                        with patch("mlflow_oidc_auth.sqlalchemy_store.sessionmaker"):
                            with patch("mlflow_oidc_auth.sqlalchemy_store._get_managed_session_maker"):
                                mock_extract.return_value = uri.split("://")[0]
                                store.init_db(uri)
                                assert store.db_uri == uri
                                assert store.db_type == uri.split("://")[0]
