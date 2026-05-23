import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import IntegrityError
from mlflow_oidc_auth.repository.user import UserRepository
from mlflow.exceptions import MlflowException


@pytest.fixture
def session():
    s = MagicMock()
    s.__enter__.return_value = s
    s.__exit__.return_value = None
    return s


@pytest.fixture
def session_maker(session):
    return MagicMock(return_value=session)


@pytest.fixture
def repo(session_maker):
    return UserRepository(session_maker)


def test_create_success(repo, session):
    """Test successful create"""
    user = MagicMock()
    user.to_mlflow_entity.return_value = "entity"
    session.add = MagicMock()
    session.flush = MagicMock()

    with (
        patch("mlflow_oidc_auth.db.models.SqlUser", return_value=user),
        patch("mlflow_oidc_auth.repository.user._validate_username"),
    ):
        result = repo.create("user", "disp")
        assert result is not None
        session.add.assert_called_once()
        session.flush.assert_called_once()


def test_create_integrity_error(repo, session):
    session.add = MagicMock()
    session.flush = MagicMock(side_effect=IntegrityError("statement", "params", "orig"))
    with (
        patch("mlflow_oidc_auth.db.models.SqlUser", return_value=MagicMock()),
        patch("mlflow_oidc_auth.repository.user._validate_username"),
    ):
        with pytest.raises(MlflowException) as exc:
            repo.create("user", "disp")
        assert "User 'user' already exists" in str(exc.value)
        assert exc.value.error_code == "RESOURCE_ALREADY_EXISTS"


def test_get_found(repo, session):
    user = MagicMock()
    user.to_mlflow_entity.return_value = "entity"
    session.query().filter().one_or_none.return_value = user
    assert repo.get("user") == "entity"


def test_get_not_found(repo, session):
    session.query().filter().one_or_none.return_value = None
    with pytest.raises(MlflowException):
        repo.get("user")


def test_exist_true(repo, session):
    session.query().filter().first.return_value = True
    assert repo.exist("user") is True


def test_exist_false(repo, session):
    session.query().filter().first.return_value = None
    assert repo.exist("user") is False


def test_list_all_false(repo, session):
    user = MagicMock()
    user.to_mlflow_entity.return_value = "entity"
    session.query().filter().all.return_value = [user]
    assert repo.list(is_service_account=False, all=False) == ["entity"]


def test_list_all_true(repo, session):
    user = MagicMock()
    user.to_mlflow_entity.return_value = "entity"
    session.query().all.return_value = [user]
    assert repo.list(is_service_account=False, all=True) == ["entity"]


def test_update_partial_fields(repo, session):
    user = MagicMock()
    user.to_mlflow_entity.return_value = "entity"
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.user.get_user", return_value=user):
        result = repo.update("user", is_admin=None, is_service_account=None)
        assert result == "entity"
        session.flush.assert_called_once()


def test_update_all_fields(repo, session):
    user = MagicMock()
    user.to_mlflow_entity.return_value = "entity"
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.user.get_user", return_value=user):
        result = repo.update("user", is_admin=True, is_service_account=True)
        assert result == "entity"
        session.flush.assert_called_once()


def test_delete(repo, session):
    user = MagicMock()
    session.delete = MagicMock()
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.user.get_user", return_value=user):
        repo.delete("user")
        session.delete.assert_called_once_with(user)
        session.flush.assert_called_once()


def test_delete_non_existent_user(repo, session):
    session.delete = MagicMock()
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.user.get_user", return_value=None):
        with pytest.raises(MlflowException):
            repo.delete("non_existent_user")
        session.delete.assert_not_called()
        session.flush.assert_not_called()
