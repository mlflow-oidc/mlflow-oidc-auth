import pytest
from unittest.mock import MagicMock, patch
from mlflow_oidc_auth.repository.registered_model_permission_regex_group import RegisteredModelGroupRegexPermissionRepository
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
    return RegisteredModelGroupRegexPermissionRepository(session_maker)


def test_get_found(repo, session):
    group = MagicMock(id=2)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    with patch("mlflow_oidc_auth.repository.registered_model_permission_regex_group.get_group", return_value=group), patch(
        "mlflow_oidc_auth.repository.registered_model_permission_regex_group.get_one_optional", return_value=perm
    ):
        assert repo.get("r", "g", True) == "entity"


def test_get_not_found(repo, session):
    group = MagicMock(id=3)
    with patch("mlflow_oidc_auth.repository.registered_model_permission_regex_group.get_group", return_value=group), patch(
        "mlflow_oidc_auth.repository.registered_model_permission_regex_group.get_one_optional", return_value=None
    ):
        with pytest.raises(MlflowException):
            repo.get("r", "g", True)


def test_list_permissions_for_group(repo, session):
    group = MagicMock(id=4)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    with patch("mlflow_oidc_auth.repository.registered_model_permission_regex_group.get_group", return_value=group), patch(
        "mlflow_oidc_auth.repository.registered_model_permission_regex_group.get_all", return_value=[perm]
    ):
        result = repo.list_permissions_for_group("g", True)
        assert result == ["entity"]


def test_update_found(repo, session):
    group = MagicMock(id=5)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.registered_model_permission_regex_group.get_group", return_value=group), patch(
        "mlflow_oidc_auth.repository.registered_model_permission_regex_group.get_one_optional", return_value=perm
    ):
        result = repo.update("r", "g", "EDIT", 7, True)
        assert result == "entity"
        assert perm.permission == "EDIT"
        assert perm.priority == 7
        assert perm.prompt is True
        session.flush.assert_called_once()


def test_update_not_found(repo, session):
    group = MagicMock(id=6)
    with patch("mlflow_oidc_auth.repository.registered_model_permission_regex_group.get_group", return_value=group), patch(
        "mlflow_oidc_auth.repository.registered_model_permission_regex_group.get_one_optional", return_value=None
    ):
        with pytest.raises(MlflowException):
            repo.update("r", "g", "EDIT", 7, True)


def test_revoke_found(repo, session):
    group = MagicMock(id=7)
    perm = MagicMock()
    session.delete = MagicMock()
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.registered_model_permission_regex_group.get_group", return_value=group), patch(
        "mlflow_oidc_auth.repository.registered_model_permission_regex_group.get_one_optional", return_value=perm
    ):
        repo.revoke("r", "g", True)
        session.delete.assert_called_once_with(perm)
        session.flush.assert_called_once()


def test_revoke_not_found(repo, session):
    group = MagicMock(id=8)
    with patch("mlflow_oidc_auth.repository.registered_model_permission_regex_group.get_group", return_value=group), patch(
        "mlflow_oidc_auth.repository.registered_model_permission_regex_group.get_one_optional", return_value=None
    ):
        with pytest.raises(MlflowException):
            repo.revoke("r", "g", True)
