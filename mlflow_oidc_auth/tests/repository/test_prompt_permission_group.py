import pytest
from unittest.mock import MagicMock, patch
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
