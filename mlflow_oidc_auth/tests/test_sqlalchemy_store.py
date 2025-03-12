import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from mlflow.exceptions import MlflowException
from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore
from sqlalchemy.exc import IntegrityError, NoResultFound
from mlflow_oidc_auth.db.models import SqlRegisteredModelPermission
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST


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
    def test_authenticate_user(self, mock_check_password_hash, mock_get_user, store):
        auth_result = store.authenticate_user("test_user", "password")
        mock_check_password_hash.assert_called_once()
        mock_get_user.assert_called_once()
        assert mock_get_user.call_args[0][1] == "test_user"
        assert auth_result is True

    @patch(
        "mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_user", return_value=MagicMock(password_hash="hashed_password")
    )
    @patch("mlflow_oidc_auth.sqlalchemy_store.check_password_hash", return_value=False)
    def test_authenticate_user_failure(self, mock_check_password_hash, mock_get_user, store):
        auth_result = store.authenticate_user("test_user", "password")
        mock_get_user.assert_called_once()
        mock_check_password_hash.assert_called_once()
        assert mock_get_user.call_args[0][1] == "test_user"
        assert auth_result is False

    @patch("mlflow_oidc_auth.sqlalchemy_store.generate_password_hash", return_value="hashed_password")
    def test_create_user(self, generate_password_hash, store):
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
    def test_create_admin_user(self, _generate_password_hash, store):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock(flush=MagicMock(), add=MagicMock())
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        admin_user = store.create_user("admin_user", "password", "Admin User", is_admin=True)

        assert mock_session.add.call_args[0][0].username == "admin_user"
        assert mock_session.add.call_args[0][0].password_hash == "hashed_password"
        assert mock_session.add.call_args[0][0].display_name == "Admin User"
        assert mock_session.add.call_args[0][0].is_admin is True
        assert admin_user.is_admin is True

    def test_create_user_existing(self, store):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock(flush=MagicMock(), add=MagicMock(side_effect=IntegrityError("", {}, Exception)))
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        with pytest.raises(MlflowException):
            store.create_user("test_user", "password", "Test User")

    def test_get_user_not_found(self, store):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock(query=MagicMock(side_effect=NoResultFound("", {}, Exception)))
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        with pytest.raises(MlflowException):
            store.get_user("non_existent_user")

    @patch("mlflow_oidc_auth.sqlalchemy_store.generate_password_hash", return_value="hashed_password")
    def test_update_user(self, _generate_password_hash, store):
        retrieved_user = MagicMock(is_admin=PropertyMock(), password_hash=PropertyMock())
        store._get_user = MagicMock(return_value=retrieved_user)
        store.update_user("test_user", password="new_password", is_admin=True)
        assert retrieved_user.is_admin == True
        assert retrieved_user.password_hash == "hashed_password"

    def test_delete_user(self, store):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock(flush=MagicMock(), delete=MagicMock())
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        store._get_user = MagicMock(return_value=MagicMock())

        store.delete_user("test_user")
        mock_session.delete.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_create_experiment_permission_validates_permission(self, store):
        with pytest.raises(MlflowException):
            store.create_experiment_permission("1", "test_user", "INVALID_PERMISSION")

    @patch("mlflow_oidc_auth.sqlalchemy_store.SqlAlchemyStore._get_user")
    def test_create_experiment_permission(self, mock_get_user, store):
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

    def test_create_registered_model_permission_validates_permission(self, store):
        with pytest.raises(MlflowException):
            store.create_registered_model_permission("model", "test_user", "INVALID_PERMISSION")

    def test_create_registered_model_permission_fails_on_duplicate(self, store):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock(flush=MagicMock(), add=MagicMock(side_effect=IntegrityError("", {}, Exception)))
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        with pytest.raises(MlflowException):
            store.create_registered_model_permission("model", "test_user", "READ")

    def test_update_registered_model_permission_validates_permission(self, store):
        with pytest.raises(MlflowException):
            store.update_registered_model_permission("model", "test_user", "INVALID_PERMISSION")

    def test_update_registered_model_permission(self, store):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock()
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session

        store._get_registered_model_permission = MagicMock(
            return_value=SqlRegisteredModelPermission(name="model", user_id=1, permission=PropertyMock(return_value="READ"))
        )

        permission = store.update_registered_model_permission("model", "test_user", "EDIT")
        assert permission.name == "model"
        assert permission.permission == "EDIT"
        assert permission.user_id == 1

    def test_delete_registered_model_permission(self, store):
        store.ManagedSessionMaker = MagicMock()
        mock_session = MagicMock(flush=MagicMock(), delete=MagicMock())
        store.ManagedSessionMaker.return_value.__enter__.return_value = mock_session
        store._get_registered_model_permission = MagicMock(
            return_value=SqlRegisteredModelPermission(name="model", user_id=1, permission="READ")
        )

        store.delete_registered_model_permission("model", "test_user")
        mock_session.delete.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_populate_groups_is_idempotent(self, store):
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
