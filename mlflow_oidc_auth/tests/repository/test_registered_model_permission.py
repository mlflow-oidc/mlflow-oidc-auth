import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.repository.registered_model_permission import (
    RegisteredModelPermissionRepository,
)

_BASE = "mlflow_oidc_auth.repository._base"


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


def test_create_success(repo, session):
    """Test successful create to cover line 54"""
    user = MagicMock(id=2)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.add = MagicMock()
    session.flush = MagicMock()

    with (
        patch(f"{_BASE}.get_user", return_value=user),
        patch.object(type(repo), "model_class", return_value=perm),
        patch(f"{_BASE}._validate_permission"),
    ):
        result = repo.create("test_model", "user", "READ")
        assert result is not None
        session.add.assert_called_once()
        session.flush.assert_called_once()


def test_create_integrity_error(repo, session):
    user = MagicMock(id=2)
    session.add = MagicMock()
    session.flush = MagicMock(side_effect=Exception("IntegrityError"))
    with (
        patch(f"{_BASE}.get_user", return_value=user),
        patch.object(type(repo), "model_class", return_value=MagicMock()),
        patch(f"{_BASE}.IntegrityError", Exception),
        patch(f"{_BASE}._validate_permission"),
    ):
        with pytest.raises(MlflowException):
            repo.create("test_model", "user", "READ")


def test_get(repo, session):
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().join().filter().one.return_value = perm
    assert repo.get("name", "user") == "entity"


def test_list_for_user(repo, session):
    user = MagicMock(id=3)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().all.return_value = [perm]
    with patch(f"{_BASE}.get_user", return_value=user):
        assert repo.list_for_user("user") == ["entity"]


def test_update(repo, session):
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().join().filter().one.return_value = perm
    session.flush = MagicMock()
    with patch(f"{_BASE}._validate_permission"):
        result = repo.update("name", "user", "EDIT")
    assert result == "entity"
    assert perm.permission == "EDIT"
    session.flush.assert_called_once()


def test_delete(repo, session):
    perm = MagicMock()
    session.query().join().filter().one.return_value = perm
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

    assert "No registered model permissions found for name: nonexistent_model" in str(
        exc.value
    )
    assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


def test__get_permission_not_found(repo, session):
    """Test _get_permission when no permission is found"""
    session.query().join().filter().one.side_effect = NoResultFound()

    with pytest.raises(MlflowException) as exc:
        repo._get_permission(session, "test_model", "user1")

    assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


def test__get_permission_multiple_found(repo, session):
    """Test _get_permission when multiple permissions are found"""
    session.query().join().filter().one.side_effect = MultipleResultsFound()

    with pytest.raises(MlflowException) as exc:
        repo._get_permission(session, "test_model", "user1")

    assert exc.value.error_code == "INVALID_STATE"


def test__get_permission_database_error(repo, session):
    """Test _get_permission when database error occurs"""
    session.query().join().filter().one.side_effect = Exception(
        "Database connection error"
    )

    with pytest.raises(Exception, match="Database connection error"):
        repo._get_permission(session, "test_model", "user1")
