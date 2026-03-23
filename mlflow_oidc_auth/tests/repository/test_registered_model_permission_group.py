import pytest
from unittest.mock import MagicMock, patch
from mlflow_oidc_auth.repository.registered_model_permission_group import (
    RegisteredModelPermissionGroupRepository,
)
from mlflow.exceptions import MlflowException

_BASE = "mlflow_oidc_auth.repository._base"
_MOD = "mlflow_oidc_auth.repository.registered_model_permission_group"


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


def test_create(repo, session):
    """Test create method to cover lines 33-39"""
    group = MagicMock(id=1)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.add = MagicMock()
    session.flush = MagicMock()

    with (
        patch(f"{_BASE}.get_group", return_value=group),
        patch.object(type(repo), "model_class", return_value=perm),
        patch(f"{_BASE}._validate_permission"),
    ):
        result = repo.create("test_group", "test_model", "READ")
        assert result is not None
        session.add.assert_called_once()
        session.flush.assert_called_once()


def test__get_group_permission_or_none_group_not_found(repo, session):
    """Test _get_group_permission_or_none when group is not found - covers lines 20-22"""
    session.query().filter().one_or_none.return_value = None

    result = repo._get_group_permission_or_none(
        session, "test_model", "nonexistent_group"
    )
    assert result is None


def test__get_group_permission_or_none_found(repo, session):
    """Test _get_group_permission_or_none when permission is found - covers line 23"""
    group = MagicMock(id=1)
    perm = MagicMock()
    session.query().filter().one_or_none.side_effect = [group, perm]

    result = repo._get_group_permission_or_none(session, "test_model", "test_group")
    assert result == perm


def test_get(repo, session):
    group = MagicMock(id=2)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().all.return_value = [perm]
    with patch(f"{_BASE}.get_group", return_value=group):
        result = repo.get("g")
        assert result == ["entity"]


def test_get_for_user_found(repo, session):
    repo._group_repo.list_groups_for_user = MagicMock(return_value=["g"])
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    with patch.object(repo, "_get_group_permission_or_none", side_effect=[perm]):
        result = repo.get_for_user("name", "user")
        assert result == "entity"


def test_get_for_user_compare_permissions_true(repo, session):
    """Test get_for_user when compare_permissions returns True - covers line 60"""
    repo._group_repo.list_groups_for_user = MagicMock(return_value=["g1", "g2"])
    perm1 = MagicMock()
    perm1.permission = "READ"
    perm2 = MagicMock()
    perm2.permission = "WRITE"
    perm2.to_mlflow_entity.return_value = "entity"

    with (
        patch.object(repo, "_get_group_permission_or_none", side_effect=[perm1, perm2]),
        patch(f"{_MOD}.compare_permissions", return_value=True),
    ):
        result = repo.get_for_user("name", "user")
        assert result == "entity"


def test_get_for_user_compare_permissions_attribute_error(repo, session):
    """Test get_for_user when compare_permissions raises AttributeError - covers lines 60-61"""
    repo._group_repo.list_groups_for_user = MagicMock(return_value=["g1", "g2"])
    perm1 = MagicMock()
    perm1.permission = "READ"
    perm2 = MagicMock()
    perm2.permission = "WRITE"
    perm2.to_mlflow_entity.return_value = "entity"

    with (
        patch.object(repo, "_get_group_permission_or_none", side_effect=[perm1, perm2]),
        patch(f"{_MOD}.compare_permissions", side_effect=AttributeError("test error")),
    ):
        result = repo.get_for_user("name", "user")
        assert result == "entity"


def test_get_for_user_not_found(repo, session):
    repo._group_repo.list_groups_for_user = MagicMock(return_value=["g"])
    with patch.object(repo, "_get_group_permission_or_none", side_effect=[None]):
        with pytest.raises(MlflowException):
            repo.get_for_user("name", "user")


def test_get_for_user_attribute_error(repo, session):
    repo._group_repo.list_groups_for_user = MagicMock(return_value=["g"])
    perm = MagicMock()
    del perm.to_mlflow_entity
    with patch.object(repo, "_get_group_permission_or_none", side_effect=[perm]):
        with pytest.raises(MlflowException):
            repo.get_for_user("name", "user")


def test_list_for_user(repo, session):
    user = MagicMock()
    ug = MagicMock(id=1)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().all.return_value = [perm]
    with (
        patch(f"{_MOD}.get_user", return_value=user),
        patch(f"{_MOD}.list_user_groups", return_value=[ug]),
    ):
        result = repo.list_for_user("user")
        assert result == ["entity"]


def test_update(repo, session):
    group = MagicMock(id=3)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().one.return_value = perm
    session.flush = MagicMock()
    with (
        patch(f"{_BASE}.get_group", return_value=group),
        patch(f"{_BASE}._validate_permission"),
    ):
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
    with patch(f"{_BASE}.get_group", return_value=group):
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

    assert (
        "No registered model group permissions found for name: nonexistent_model"
        in str(exc.value)
    )
    assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"
