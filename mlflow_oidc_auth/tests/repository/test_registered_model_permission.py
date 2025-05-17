import pytest
from unittest.mock import MagicMock, patch
from mlflow_oidc_auth.repository.registered_model_permission import RegisteredModelPermissionRepository
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
    return RegisteredModelPermissionRepository(session_maker)


def test_create_integrity_error(repo, session):
    user = MagicMock(id=2)
    session.add = MagicMock()
    session.flush = MagicMock(side_effect=Exception("IntegrityError"))
    with patch("mlflow_oidc_auth.repository.registered_model_permission.get_user", return_value=user), patch(
        "mlflow_oidc_auth.db.models.SqlRegisteredModelPermission", return_value=MagicMock()
    ), patch("mlflow_oidc_auth.repository.registered_model_permission.IntegrityError", Exception):
        with pytest.raises(MlflowException):
            repo.create("name", "user", "READ")


def test_get(repo, session):
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    with patch("mlflow_oidc_auth.repository.registered_model_permission.get_one_or_raise", return_value=perm):
        assert repo.get("name", "user") == "entity"


def test_list_for_user(repo, session):
    user = MagicMock(id=3)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().all.return_value = [perm]
    with patch("mlflow_oidc_auth.repository.registered_model_permission.get_user", return_value=user):
        assert repo.list_for_user("user") == ["entity"]


def test_update(repo, session):
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    with patch("mlflow_oidc_auth.repository.registered_model_permission.get_one_or_raise", return_value=perm):
        session.flush = MagicMock()
        result = repo.update("name", "user", "EDIT")
        assert result == "entity"
        assert perm.permission == "EDIT"
        session.flush.assert_called_once()


def test_delete(repo, session):
    perm = MagicMock()
    with patch("mlflow_oidc_auth.repository.registered_model_permission.get_one_or_raise", return_value=perm):
        session.delete = MagicMock()
        session.flush = MagicMock()
        repo.delete("name", "user")
        session.delete.assert_called_once_with(perm)
        session.flush.assert_called_once()


def test_wipe(repo, session):
    perm1 = MagicMock()
    perm2 = MagicMock()
    session.query().filter().all.return_value = [perm1, perm2]
    session.delete = MagicMock()
    session.flush = MagicMock()
    repo.wipe("name")
    assert session.delete.call_count == 2
    session.flush.assert_called_once()
