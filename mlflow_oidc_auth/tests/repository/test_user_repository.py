import pytest
from unittest.mock import MagicMock, patch
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


def test_create_integrity_error(repo, session):
    session.add = MagicMock()
    session.flush = MagicMock(side_effect=Exception("IntegrityError"))
    with patch("mlflow_oidc_auth.db.models.SqlUser", return_value=MagicMock()), patch(
        "mlflow_oidc_auth.repository.user.generate_password_hash", return_value="hashed"
    ), patch("mlflow_oidc_auth.repository.user.IntegrityError", Exception):
        with pytest.raises(MlflowException):
            repo.create("user", "pw", "disp")


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
    with patch("mlflow_oidc_auth.repository.user.get_user", return_value=user), patch(
        "mlflow_oidc_auth.repository.user.generate_password_hash", return_value="hashed"
    ):
        result = repo.update("user", password=None, is_admin=None, is_service_account=None)
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


def test_authenticate_success(repo, session):
    user = MagicMock()
    user.password_hash = "hashed"
    with patch("mlflow_oidc_auth.repository.user.get_user", return_value=user), patch(
        "mlflow_oidc_auth.repository.user.check_password_hash", return_value=True
    ):
        assert repo.authenticate("user", "pw") is True


def test_authenticate_fail(repo, session):
    with patch("mlflow_oidc_auth.repository.user.get_user", side_effect=MlflowException("fail")):
        assert repo.authenticate("user", "pw") is False
