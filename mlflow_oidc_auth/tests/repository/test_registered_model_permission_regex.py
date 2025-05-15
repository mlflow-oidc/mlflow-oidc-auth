import pytest
from unittest.mock import MagicMock, patch
from mlflow_oidc_auth.repository.registered_model_permission_regex import RegisteredModelPermissionRegexRepository
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
    return RegisteredModelPermissionRegexRepository(session_maker)


def test_grant_integrity_error(repo, session):
    user = MagicMock(id=2)
    session.add = MagicMock()
    session.flush = MagicMock(side_effect=Exception("IntegrityError"))
    with patch("mlflow_oidc_auth.repository.registered_model_permission_regex.get_user", return_value=user), patch(
        "mlflow_oidc_auth.db.models.SqlRegisteredModelRegexPermission", return_value=MagicMock()
    ), patch("mlflow_oidc_auth.repository.registered_model_permission_regex.IntegrityError", Exception):
        with pytest.raises(MlflowException):
            repo.grant("r", 1, "READ", "user", prompt=True)


def test_get(repo, session):
    user = MagicMock(id=3)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    with patch("mlflow_oidc_auth.repository.registered_model_permission_regex.get_user", return_value=user), patch(
        "mlflow_oidc_auth.repository.registered_model_permission_regex.get_one_or_raise", return_value=perm
    ):
        result = repo.get("r", "user", prompt=True)
        assert result == "entity"


def test_list_permissions_for_user(repo, session):
    user = MagicMock(id=4)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    with patch("mlflow_oidc_auth.repository.registered_model_permission_regex.get_user", return_value=user), patch(
        "mlflow_oidc_auth.repository.registered_model_permission_regex.get_all", return_value=[perm]
    ):
        result = repo.list_permissions_for_user("user", prompt=True)
        assert result == ["entity"]


def test_update(repo, session):
    user = MagicMock(id=5)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.commit = MagicMock()
    with patch("mlflow_oidc_auth.repository.registered_model_permission_regex.get_user", return_value=user), patch(
        "mlflow_oidc_auth.repository.registered_model_permission_regex.get_one_or_raise", return_value=perm
    ):
        result = repo.update("r", 2, "EDIT", "user", prompt=True)
        assert result == "entity"
        assert perm.priority == 2
        assert perm.permission == "EDIT"
        session.commit.assert_called_once()


def test_revoke(repo, session):
    user = MagicMock(id=6)
    perm = MagicMock()
    session.delete = MagicMock()
    session.commit = MagicMock()
    with patch("mlflow_oidc_auth.repository.registered_model_permission_regex.get_user", return_value=user), patch(
        "mlflow_oidc_auth.repository.registered_model_permission_regex.get_one_or_raise", return_value=perm
    ):
        repo.revoke("r", "user", prompt=True)
        session.delete.assert_called_once_with(perm)
        session.commit.assert_called_once()
