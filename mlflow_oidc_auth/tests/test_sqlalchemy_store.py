from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore


@pytest.fixture
@patch("mlflow_oidc_auth.sqlalchemy_store.dbutils.migrate_if_needed")
def store(_mock_migrate_if_needed):
    store = SqlAlchemyStore()
    store.init_db("sqlite:///:memory:")
    return store


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
