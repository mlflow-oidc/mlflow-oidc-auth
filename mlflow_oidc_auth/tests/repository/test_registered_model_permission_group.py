import pytest
from unittest.mock import MagicMock, patch
from mlflow_oidc_auth.repository.registered_model_permission_group import RegisteredModelPermissionGroupRepository
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
    return RegisteredModelPermissionGroupRepository(session_maker)


def test_get(repo, session):
    group = MagicMock(id=2)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().all.return_value = [perm]
    with patch("mlflow_oidc_auth.repository.registered_model_permission_group.get_group", return_value=group):
        result = repo.get("g")
        assert result == ["entity"]


def test_get_for_user_found(repo, session):
    repo._group_repo.list_groups_for_user = MagicMock(return_value=["g"])
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    with patch.object(repo, "_get_registered_model_group_permission", side_effect=[perm]):
        result = repo.get_for_user("name", "user")
        assert result == "entity"


def test_get_for_user_not_found(repo, session):
    repo._group_repo.list_groups_for_user = MagicMock(return_value=["g"])
    with patch.object(repo, "_get_registered_model_group_permission", side_effect=[None]):
        with pytest.raises(MlflowException):
            repo.get_for_user("name", "user")


def test_get_for_user_attribute_error(repo, session):
    repo._group_repo.list_groups_for_user = MagicMock(return_value=["g"])
    perm = MagicMock()
    del perm.to_mlflow_entity
    with patch.object(repo, "_get_registered_model_group_permission", side_effect=[perm]):
        with pytest.raises(MlflowException):
            repo.get_for_user("name", "user")


def test_list_for_user(repo, session):
    user = MagicMock()
    ug = MagicMock(id=1)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().all.return_value = [perm]
    with patch("mlflow_oidc_auth.repository.registered_model_permission_group.get_user", return_value=user), patch(
        "mlflow_oidc_auth.repository.registered_model_permission_group.list_user_groups", return_value=[ug]
    ):
        result = repo.list_for_user("user")
        assert result == ["entity"]


def test_update(repo, session):
    group = MagicMock(id=3)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().one.return_value = perm
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.registered_model_permission_group.get_group", return_value=group):
        result = repo.update("g", "name", "EDIT")
        assert result == "entity"
        assert perm.permission == "EDIT"
        session.flush.assert_called_once()


def test_delete(repo, session):
    group = MagicMock(id=4)
    perm = MagicMock()
    session.query().filter().one.return_value = perm
    session.delete = MagicMock()
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.registered_model_permission_group.get_group", return_value=group):
        repo.delete("g", "name")
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


def test_rename_success(repo, session):
    """Test rename method when permissions are found"""
    perm1 = MagicMock()
    perm2 = MagicMock()
    session.query().filter().all.return_value = [perm1, perm2]
    session.flush = MagicMock()

    repo.rename("old_model", "new_model")

    assert perm1.name == "new_model"
    assert perm2.name == "new_model"
    session.flush.assert_called_once()


def test_rename_no_permissions_found(repo, session):
    """Test rename method when no permissions are found"""
    session.query().filter().all.return_value = []

    with pytest.raises(MlflowException) as exc:
        repo.rename("nonexistent_model", "new_model")

    assert "No registered model group permissions found for name: nonexistent_model" in str(exc.value)
    assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"
