from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from mlflow.exceptions import MlflowException
from sqlalchemy.exc import IntegrityError, NoResultFound, MultipleResultsFound

from mlflow_oidc_auth.db.models import SqlRegisteredModelGroupPermission, SqlRegisteredModelPermission
from mlflow_oidc_auth.entities import ExperimentPermission, RegisteredModelPermission
from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore


@pytest.fixture
@patch("mlflow_oidc_auth.sqlalchemy_store.dbutils.migrate_if_needed")
def store(_mock_migrate_if_needed):
    store = SqlAlchemyStore()
    store.init_db("sqlite:///:memory:")
    return store


class TestSqlAlchemyStore:
    @patch(
        "mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_user", return_value=MagicMock(password_hash="hashed_password")
    )
    @patch("mlflow_oidc_auth.sqlalchemy_store.check_password_hash", return_value=True)
    def test_authenticate_user(self, mock_check_password_hash, mock_get_user, store: SqlAlchemyStore):
        auth_result = store.authenticate_user("test_user", "password")
        mock_check_password_hash.assert_called_once()
        mock_get_user.assert_called_once()
        assert mock_get_user.call_args[0][1] == "test_user"
        assert auth_result is True

    @patch(
        "mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_user", return_value=MagicMock(password_hash="hashed_password")
    )
    @patch("mlflow_oidc_auth.sqlalchemy_store.check_password_hash", return_value=False)
    def test_authenticate_user_failure(self, mock_check_password_hash, mock_get_user, store: SqlAlchemyStore):
        auth_result = store.authenticate_user("test_user", "password")
        mock_get_user.assert_called_once()
        mock_check_password_hash.assert_called_once()
        assert mock_get_user.call_args[0][1] == "test_user"
        assert auth_result is False

    def test_authenticate_user_mlflow_exception(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        store._get_user = MagicMock(side_effect=MlflowException("User not found"))
        result = store.authenticate_user("missing_user", "password")
        assert result is False

    @patch("mlflow_oidc_auth.sqlalchemy_store.generate_password_hash", return_value="hashed_password")
    def test_create_user(self, generate_password_hash, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock(flush=MagicMock(), add=MagicMock())
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        user = store.create_user("test_user", "password", "Test User")

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        generate_password_hash.assert_called_once_with("password")

        assert mock_session.add.call_args[0][0].username == "test_user"
        assert mock_session.add.call_args[0][0].password_hash == "hashed_password"
        assert mock_session.add.call_args[0][0].display_name == "Test User"
        assert mock_session.add.call_args[0][0].is_admin is False

        assert user.username == "test_user"
        assert user.display_name == "Test User"
        assert user.is_admin is False

    @patch("mlflow_oidc_auth.sqlalchemy_store.generate_password_hash", return_value="hashed_password")
    def test_create_admin_user(self, _generate_password_hash, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock(flush=MagicMock(), add=MagicMock())
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        admin_user = store.create_user("admin_user", "password", "Admin User", is_admin=True)

        assert mock_session.add.call_args[0][0].username == "admin_user"
        assert mock_session.add.call_args[0][0].password_hash == "hashed_password"
        assert mock_session.add.call_args[0][0].display_name == "Admin User"
        assert mock_session.add.call_args[0][0].is_admin is True
        assert admin_user.is_admin is True

    def test_create_user_existing(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock(flush=MagicMock(), add=MagicMock(side_effect=IntegrityError("", {}, Exception())))
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        with pytest.raises(MlflowException):
            store.create_user("test_user", "password", "Test User")

    def test_get_user_not_found(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock(query=MagicMock(side_effect=NoResultFound("", {}, Exception)))
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        with pytest.raises(MlflowException):
            store.get_user("non_existent_user")

    def test_get_user_multiple_results_found(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        # Simulate MultipleResultsFound when querying for user
        mock_session.query.return_value.filter.return_value.one.side_effect = MultipleResultsFound()
        with pytest.raises(MlflowException) as exc_info:
            store._get_user(mock_session, "duplicate_user")
        assert "Found multiple users with username=duplicate_user" in str(exc_info.value)

    @patch("mlflow_oidc_auth.sqlalchemy_store.generate_password_hash", return_value="hashed_password")
    def test_update_user(self, _generate_password_hash, store: SqlAlchemyStore):
        retrieved_user = MagicMock(is_admin=PropertyMock(), password_hash=PropertyMock())
        store._get_user = MagicMock(return_value=retrieved_user)
        store.update_user("test_user", password="new_password", is_admin=True)
        assert retrieved_user.is_admin == True
        assert retrieved_user.password_hash == "hashed_password"

    def test_delete_user(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock(flush=MagicMock(), delete=MagicMock())
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        store._get_user = MagicMock(return_value=MagicMock())

        store.delete_user("test_user")
        mock_session.delete.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_create_experiment_permission_validates_permission(self, store: SqlAlchemyStore):
        with pytest.raises(MlflowException):
            store.create_experiment_permission("1", "test_user", "INVALID_PERMISSION")

    @patch("mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_user")
    def test_create_experiment_permission(self, mock_get_user, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock(flush=MagicMock(), add=MagicMock())
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_user = MagicMock(id=1)
        store._get_user.return_value = mock_user
        mock_get_user.return_value = mock_user

        permission = store.create_experiment_permission("1", "test_user", "READ")
        assert permission.experiment_id == "1"
        assert permission.permission == "READ"
        assert permission.user_id == 1

    @patch("mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_user")
    def test_list_group_experiment_permissions(self, mock_get_user, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group
        mock_perms = [
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm1")),
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm2")),
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_perms

        permissions = store.list_group_experiment_permissions("group_name")
        assert permissions == ["perm1", "perm2"]
        mock_session.query.assert_called()
        mock_session.query.return_value.filter.assert_called()

    @patch("mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_user")
    def test_list_experiment_permissions(self, mock_get_user, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_user = MagicMock(id=1)
        mock_get_user.return_value = mock_user
        mock_perms = [
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm1")),
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm2")),
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_perms

        permissions = store.list_experiment_permissions("test_user")
        assert permissions == ["perm1", "perm2"]
        mock_session.query.assert_called()
        mock_session.query.return_value.filter.assert_called()

    @patch("mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_user")
    def test_list_group_id_experiment_permissions(self, mock_get_user, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_perms = [
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm1")),
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm2")),
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_perms

        permissions = store.list_group_id_experiment_permissions(1)
        assert permissions == ["perm1", "perm2"]
        mock_session.query.assert_called()
        mock_session.query.return_value.filter.assert_called()

    @patch("mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_user")
    def test_list_user_groups_experiment_permissions(self, mock_get_user, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_user = MagicMock(id=1)
        mock_get_user.return_value = mock_user
        mock_user_groups = [MagicMock(group_id=1), MagicMock(group_id=2)]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_user_groups
        mock_perms = [
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm1")),
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm2")),
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_perms

        permissions = store.list_user_groups_experiment_permissions("test_user")
        assert permissions == ["perm1", "perm2"]
        mock_session.query.assert_called()
        mock_session.query.return_value.filter.assert_called()

    @patch("mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_experiment_permission")
    def test_update_experiment_permission(self, mock_get_experiment_permission, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_perm = MagicMock(to_mlflow_entity=MagicMock(return_value="updated_perm"))
        mock_get_experiment_permission.return_value = mock_perm

        permission = store.update_experiment_permission("1", "test_user", "READ")
        assert permission == "updated_perm"
        mock_get_experiment_permission.assert_called_once_with(mock_session, "1", "test_user")
        assert mock_perm.permission == "READ"

    @patch("mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_experiment_permission")
    def test_delete_experiment_permission(self, mock_get_experiment_permission, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock(flush=MagicMock(), delete=MagicMock())
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_perm = MagicMock()
        mock_get_experiment_permission.return_value = mock_perm

        store.delete_experiment_permission("1", "test_user")
        mock_get_experiment_permission.assert_called_once_with(mock_session, "1", "test_user")
        mock_session.delete.assert_called_once_with(mock_perm)
        mock_session.flush.assert_called_once()

    @patch("mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_user")
    def test_get_registered_model_permission(self, mock_get_user, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_user = MagicMock(id=1)
        mock_get_user.return_value = mock_user
        mock_perm = MagicMock(to_mlflow_entity=MagicMock(return_value="perm"))
        mock_session.query.return_value.filter.return_value.one.return_value = mock_perm

        permission = store.get_registered_model_permission("model", "test_user")
        assert permission == "perm"
        mock_get_user.assert_called_once_with(mock_session, username="test_user")
        mock_session.query.assert_called()
        mock_session.query.return_value.filter.assert_called()

    @patch("mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore.get_groups_for_user", return_value=["group1", "group2"])
    @patch(
        "mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_registered_model_group_permission",
        side_effect=[
            MagicMock(to_mlflow_entity=MagicMock(return_value="READ")),
            MagicMock(to_mlflow_entity=MagicMock(return_value="EDIT")),
        ],
    )
    def test_get_user_groups_registered_model_permission(
        self, mock_get_registered_model_group_permission, mock_get_groups_for_user, store: SqlAlchemyStore
    ):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        mock_get_registered_model_group_permission.side_effect = [
            MagicMock(permission="READ", to_mlflow_entity=MagicMock(return_value="READ")),
            MagicMock(permission="EDIT", to_mlflow_entity=MagicMock(return_value="EDIT")),
        ]
        permission = store.get_user_groups_registered_model_permission("model", "test_user")
        assert permission == "EDIT"
        mock_get_groups_for_user.assert_called_once_with("test_user")
        mock_get_registered_model_group_permission.assert_called()

    @patch("mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_user")
    def test_list_registered_model_permissions(self, mock_get_user, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_user = MagicMock(id=1)
        mock_get_user.return_value = mock_user
        mock_perms = [
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm1")),
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm2")),
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_perms

        permissions = store.list_registered_model_permissions("test_user")
        assert permissions == ["perm1", "perm2"]
        mock_session.query.assert_called()
        mock_session.query.return_value.filter.assert_called()

    @patch("mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_user")
    def test_list_user_groups_registered_model_permissions(self, mock_get_user, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_user = MagicMock(id=1)
        mock_get_user.return_value = mock_user
        mock_user_groups = [MagicMock(group_id=1), MagicMock(group_id=2)]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_user_groups
        mock_perms = [
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm1")),
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm2")),
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_perms

        permissions = store.list_user_groups_registered_model_permissions("test_user")
        assert permissions == ["perm1", "perm2"]
        mock_session.query.assert_called()
        mock_session.query.return_value.filter.assert_called()

    def test_list_experiment_permissions_for_experiment(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_perms = [
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm1")),
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm2")),
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_perms

        permissions = store.list_experiment_permissions_for_experiment("1")
        assert permissions == ["perm1", "perm2"]
        mock_session.query.assert_called()
        mock_session.query.return_value.filter.assert_called()

    def test_get_groups(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_groups = [MagicMock(group_name="group1"), MagicMock(group_name="group2")]
        mock_session.query.return_value.all.return_value = mock_groups

        groups = store.get_groups()
        assert groups == ["group1", "group2"]
        mock_session.query.assert_called()

    def test_get_group_users(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group
        mock_user_groups = [MagicMock(user_id=1), MagicMock(user_id=2)]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_user_groups
        mock_users = [MagicMock(username="user1"), MagicMock(username="user2")]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_users

        users = store.get_group_users("group_name")
        assert users == ["user1", "user2"]
        mock_session.query.assert_called()
        mock_session.query.return_value.filter.assert_called()

    def test_add_user_to_group(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_user = MagicMock(id=1)
        store._get_user = MagicMock(return_value=mock_user)
        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group

        store.add_user_to_group("test_user", "group_name")
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_remove_user_from_group(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_user = MagicMock(id=1)
        store._get_user = MagicMock(return_value=mock_user)
        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group
        mock_user_group = MagicMock()
        mock_session.query.return_value.filter.return_value.one.return_value = mock_user_group

        store.remove_user_from_group("test_user", "group_name")
        mock_session.delete.assert_called_once_with(mock_user_group)
        mock_session.flush.assert_called_once()

    def test_get_groups_for_user(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_user = MagicMock(id=1)
        store._get_user = MagicMock(return_value=mock_user)
        mock_user_groups = [MagicMock(group_id=1), MagicMock(group_id=2)]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_user_groups
        mock_groups = [MagicMock(group_name="group1"), MagicMock(group_name="group2")]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_groups

        groups = store.get_groups_for_user("test_user")
        assert groups == ["group1", "group2"]
        mock_session.query.assert_called()
        mock_session.query.return_value.filter.assert_called()

    def test_get_groups_ids_for_user(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_user = MagicMock(id=1)
        store._get_user = MagicMock(return_value=mock_user)
        mock_user_groups = [MagicMock(group_id=1), MagicMock(group_id=2)]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_user_groups

        group_ids = store.get_groups_ids_for_user("test_user")
        assert group_ids == [1, 2]
        mock_session.query.assert_called()
        mock_session.query.return_value.filter.assert_called()

    def test_set_user_groups(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_user = MagicMock(id=1)
        store._get_user = MagicMock(return_value=mock_user)
        mock_user_groups = [MagicMock()]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_user_groups
        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group

        store.set_user_groups("test_user", ["group_name"])
        mock_session.delete.assert_called_once_with(mock_user_groups[0])
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_get_group_experiments(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group
        mock_perms = [
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm1")),
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm2")),
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_perms

        permissions = store.get_group_experiments("group_name")
        assert permissions == ["perm1", "perm2"]
        mock_session.query.assert_called()
        mock_session.query.return_value.filter.assert_called()

    def test_create_group_experiment_permission(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group
        expected_perm = ExperimentPermission(experiment_id="1", group_id=1, permission="READ")
        mock_perm = MagicMock(to_mlflow_entity=MagicMock(return_value=expected_perm))
        mock_session.add.return_value = mock_perm
        permission = store.create_group_experiment_permission("group_name", "1", "READ")
        assert permission.experiment_id == expected_perm.experiment_id
        assert permission.group_id == expected_perm.group_id
        assert permission.permission == expected_perm.permission

    def test_delete_group_experiment_permission(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group
        mock_perm = MagicMock()
        mock_session.query.return_value.filter.return_value.one.return_value = mock_perm

        store.delete_group_experiment_permission("group_name", "1")
        mock_session.delete.assert_called_once_with(mock_perm)
        mock_session.flush.assert_called_once()

    def test_update_group_experiment_permission(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group
        mock_perm = MagicMock(to_mlflow_entity=MagicMock(return_value="updated_perm"))
        mock_session.query.return_value.filter.return_value.one.return_value = mock_perm

        permission = store.update_group_experiment_permission("group_name", "1", "READ")
        assert permission == "updated_perm"
        assert mock_perm.permission == "READ"
        mock_session.flush.assert_called_once()

    def test_get_group_models(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group
        mock_perms = [
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm1")),
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm2")),
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_perms

        permissions = store.get_group_models("group_name")
        assert permissions == ["perm1", "perm2"]
        mock_session.query.assert_called()
        mock_session.query.return_value.filter.assert_called()

    def test_create_group_model_permission(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group
        expected_perm = RegisteredModelPermission(name="model", permission="READ")
        mock_perm = MagicMock(to_mlflow_entity=MagicMock(return_value=expected_perm))
        mock_session.add.return_value = mock_perm
        permission = store.create_group_model_permission("group_name", "model", "READ")
        assert permission.name == expected_perm.name
        assert permission.permission == expected_perm.permission

    def test_wipe_group_model_permissions(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        store.wipe_group_model_permissions("model_name")
        actual_filter = mock_session.query.return_value.filter.call_args[0][0]
        expected_filter = SqlRegisteredModelGroupPermission.name == "model_name"
        assert str(expected_filter.compile(compile_kwargs={"literal_binds": True})) == str(
            actual_filter.compile(compile_kwargs={"literal_binds": True})
        )
        mock_session.flush.assert_called_once()

    def test_wipe_registered_model_permissions(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        store.wipe_registered_model_permissions("model_name")
        actual_filter = mock_session.query.return_value.filter.call_args[0][0]
        expected_filter = SqlRegisteredModelPermission.name == "model_name"
        assert str(expected_filter.compile(compile_kwargs={"literal_binds": True})) == str(
            actual_filter.compile(compile_kwargs={"literal_binds": True})
        )
        mock_session.flush.assert_called_once()

    def test_populate_groups_is_idempotent(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock(add=MagicMock())
        mock_session.query.return_value.filter.return_value.first.return_value = None
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        store.populate_groups(["Group 1"])
        mock_session.add.assert_called()

        mock_session.add.reset_mock()
        mock_session.query.return_value.filter.return_value.first.return_value = "Group 1"
        store.populate_groups(["Group 1"])
        assert mock_session.add.call_count == 0

    @patch("mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore.get_groups_for_user", return_value=["group1", "group2"])
    @patch(
        "mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_experiment_group_permission",
        side_effect=[MagicMock(), MagicMock()],
    )
    @patch("mlflow_oidc_auth.sqlalchemy_store.compare_permissions", side_effect=AttributeError)
    def test_get_user_groups_experiment_permission_compare_permissions_error(
        self, mock_compare_permissions, mock_get_experiment_group_permission, mock_get_groups_for_user, store
    ):
        result = store.get_user_groups_experiment_permission("1", "test_user")
        assert result is not None
        mock_get_experiment_group_permission.assert_called()
        mock_get_groups_for_user.assert_called_once_with("test_user")
        mock_compare_permissions.assert_called()

    @patch("mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore.get_groups_for_user", return_value=["group1", "group2"])
    @patch(
        "mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_experiment_group_permission",
        side_effect=[MagicMock(permission="READ"), MagicMock(permission="WRITE")],
    )
    @patch("mlflow_oidc_auth.sqlalchemy_store.compare_permissions", return_value=True)
    def test_get_user_groups_experiment_permission_compare_permissions(
        self, mock_compare_permissions, mock_get_experiment_group_permission, mock_get_groups_for_user, store
    ):
        result = store.get_user_groups_experiment_permission("1", "test_user")
        assert result is not None
        mock_get_experiment_group_permission.assert_called()
        mock_get_groups_for_user.assert_called_once_with("test_user")
        mock_compare_permissions.assert_called()

    def test_update_registered_model_permission(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        mock_perm = MagicMock(to_mlflow_entity=MagicMock(return_value="updated_perm"))
        store._get_registered_model_permission = MagicMock(return_value=mock_perm)
        permission = store.update_registered_model_permission("model", "test_user", "EDIT")
        assert permission == "updated_perm"
        assert mock_perm.permission == "EDIT"

    def test_delete_registered_model_permission(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock(flush=MagicMock(), delete=MagicMock())
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        mock_perm = MagicMock()
        store._get_registered_model_permission = MagicMock(return_value=mock_perm)
        store.delete_registered_model_permission("model", "test_user")
        store._get_registered_model_permission.assert_called_once_with(mock_session, "model", "test_user")
        mock_session.delete.assert_called_once_with(mock_perm)
        mock_session.flush.assert_called_once()

    def test_delete_group_model_permission(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group
        mock_perm = MagicMock()
        mock_session.query.return_value.filter.return_value.one.return_value = mock_perm
        store.delete_group_model_permission("group_name", "model")
        mock_session.delete.assert_called_once_with(mock_perm)
        mock_session.flush.assert_called_once()

    def test_update_group_model_permission(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group
        mock_perm = MagicMock(to_mlflow_entity=MagicMock(return_value="updated_perm"))
        mock_session.query.return_value.filter.return_value.one.return_value = mock_perm
        permission = store.update_group_model_permission("group_name", "model", "EDIT")
        assert permission == "updated_perm"
        assert mock_perm.permission == "EDIT"
        mock_session.flush.assert_called_once()

    def test_get_group_prompts(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group
        mock_perms = [
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm1")),
            MagicMock(to_mlflow_entity=MagicMock(return_value="perm2")),
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_perms
        permissions = store.get_group_prompts("group_name")
        assert permissions == ["perm1", "perm2"]
        mock_session.query.assert_called()
        mock_session.query.return_value.filter.assert_called()

    def test_create_group_prompt_permission(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group
        expected_perm = RegisteredModelPermission(name="model", permission="READ")
        mock_perm = MagicMock(to_mlflow_entity=MagicMock(return_value=expected_perm))
        mock_session.add.return_value = mock_perm
        permission = store.create_group_prompt_permission("group_name", "model", "READ")
        assert permission.name == expected_perm.name
        assert permission.permission == expected_perm.permission

    def test_delete_group_prompt_permission(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group
        mock_perm = MagicMock()
        mock_session.query.return_value.filter.return_value.one.return_value = mock_perm
        store.delete_group_prompt_permission("group_name", "model")
        mock_session.delete.assert_called_once_with(mock_perm)
        mock_session.flush.assert_called_once()

    def test_update_group_prompt_permission(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        mock_group = MagicMock(id=1)
        mock_session.query.return_value.filter.return_value.one.return_value = mock_group
        mock_perm = MagicMock(to_mlflow_entity=MagicMock(return_value="updated_perm"))
        mock_session.query.return_value.filter.return_value.one.return_value = mock_perm
        permission = store.update_group_prompt_permission("group_name", "model", "EDIT")
        assert permission == "updated_perm"
        assert mock_perm.permission == "EDIT"
        mock_session.flush.assert_called_once()

    def test_has_user(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        # Simulate user exists
        mock_session.query.return_value.filter.return_value.first.return_value = MagicMock()
        assert store.has_user("existing_user") is True
        # Simulate user does not exist
        mock_session.query.return_value.filter.return_value.first.return_value = None
        assert store.has_user("missing_user") is False

    def test_list_users(self, store: SqlAlchemyStore):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        # Mock user entities
        mock_user1 = MagicMock()
        mock_user2 = MagicMock()
        mock_user1.to_mlflow_entity.return_value = "user1"
        mock_user2.to_mlflow_entity.return_value = "user2"
        # all=True branch
        mock_session.query.return_value.all.return_value = [mock_user1, mock_user2]
        users = store.list_users(all=True)
        assert users == ["user1", "user2"]
        # all=False branch
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_user1]
        users = store.list_users(is_service_account=True, all=False)
        assert users == ["user1"]
