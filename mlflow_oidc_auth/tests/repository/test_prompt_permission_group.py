import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, INVALID_STATE

from mlflow_oidc_auth.repository.prompt_permission_group import PromptPermissionGroupRepository


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
    return PromptPermissionGroupRepository(session_maker)


def test_list_prompt_permissions_for_group(repo, session):
    group = MagicMock(id=2)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().all.return_value = [perm]
    with patch("mlflow_oidc_auth.repository.prompt_permission_group.get_group", return_value=group):
        result = repo.list_prompt_permissions_for_group("g")
        assert result == ["entity"]


def test_update_prompt_permission_for_group(repo, session):
    group = MagicMock(id=3)
    perm = MagicMock()
    perm.to_mlflow_entity.return_value = "entity"
    session.query().filter().one.return_value = perm
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.prompt_permission_group.get_group", return_value=group):
        result = repo.update_prompt_permission_for_group("g", "prompt", "EDIT")
        assert result == "entity"
        assert perm.permission == "EDIT"
        session.flush.assert_called_once()


def test_revoke_prompt_permission_from_group(repo, session):
    group = MagicMock(id=4)
    perm = MagicMock()
    session.query().filter().one.return_value = perm
    session.delete = MagicMock()
    session.flush = MagicMock()
    with patch("mlflow_oidc_auth.repository.prompt_permission_group.get_group", return_value=group):
        repo.revoke_prompt_permission_from_group("g", "prompt")
        session.delete.assert_called_once_with(perm)
        session.flush.assert_called_once()


def test__get_prompt_group_permission_not_found(repo, session):
    """Test _get_prompt_group_permission when no permission is found"""
    session.query().filter().one.side_effect = NoResultFound()

    with pytest.raises(MlflowException) as exc:
        repo._get_prompt_group_permission(session, "test_prompt", 1)

    assert "No permission for prompt=test_prompt, group=1" in str(exc.value)
    assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


def test__get_prompt_group_permission_multiple_found(repo, session):
    """Test _get_prompt_group_permission when multiple permissions are found"""
    session.query().filter().one.side_effect = MultipleResultsFound()

    with pytest.raises(MlflowException) as exc:
        repo._get_prompt_group_permission(session, "test_prompt", 1)

    assert "Multiple perms for prompt=test_prompt, group=1" in str(exc.value)
    assert exc.value.error_code == "INVALID_STATE"


def test__get_prompt_group_permission_database_error(repo, session):
    """Test _get_prompt_group_permission when database error occurs"""
    session.query().filter().one.side_effect = Exception("Database connection error")

    with pytest.raises(Exception, match="Database connection error"):
        repo._get_prompt_group_permission(session, "test_prompt", 1)
