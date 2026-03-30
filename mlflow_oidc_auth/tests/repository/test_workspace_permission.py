"""Tests for WorkspacePermissionRepository."""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import NoResultFound, IntegrityError
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.repository.workspace_permission import (
    WorkspacePermissionRepository,
)


@pytest.fixture
def session():
    s = MagicMock()
    s.__enter__ = MagicMock(return_value=s)
    s.__exit__ = MagicMock(return_value=None)
    return s


@pytest.fixture
def session_maker(session):
    return MagicMock(return_value=session)


@pytest.fixture
def repo(session_maker):
    return WorkspacePermissionRepository(session_maker)


class TestGet:
    """Test WorkspacePermissionRepository.get()."""

    def test_get_returns_entity_for_existing(self, repo, session):
        """get() returns entity for existing (workspace, user_id)."""
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        session.query().filter().one.return_value = perm
        result = repo.get("ws1", 1)
        assert result == "entity"

    def test_get_raises_for_missing(self, repo, session):
        """get() raises MlflowException for missing permission."""
        session.query().filter().one.side_effect = NoResultFound()
        with pytest.raises(MlflowException) as exc:
            repo.get("ws1", 1)
        assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


class TestCreate:
    """Test WorkspacePermissionRepository.create()."""

    def test_create_inserts_and_returns_entity(self, repo, session):
        """create() inserts row and returns entity."""
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"

        with patch(
            "mlflow_oidc_auth.repository.workspace_permission.SqlWorkspacePermission",
            return_value=perm,
        ):
            result = repo.create("ws1", 1, "MANAGE")
            session.add.assert_called_once_with(perm)
            session.flush.assert_called_once()
            assert result == "entity"

    def test_create_raises_on_duplicate(self, repo, session):
        """create() raises MlflowException on duplicate."""
        session.flush.side_effect = IntegrityError("statement", "params", "orig")

        with patch(
            "mlflow_oidc_auth.repository.workspace_permission.SqlWorkspacePermission",
            return_value=MagicMock(),
        ):
            with pytest.raises(MlflowException) as exc:
                repo.create("ws1", 1, "MANAGE")
            assert exc.value.error_code == "RESOURCE_ALREADY_EXISTS"


class TestUpdate:
    """Test WorkspacePermissionRepository.update()."""

    def test_update_modifies_and_returns_entity(self, repo, session):
        """update() modifies permission and returns updated entity."""
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "updated_entity"
        session.query().filter().one.return_value = perm
        result = repo.update("ws1", 1, "EDIT")
        assert perm.permission == "EDIT"
        session.flush.assert_called_once()
        assert result == "updated_entity"


class TestDelete:
    """Test WorkspacePermissionRepository.delete()."""

    def test_delete_removes_row(self, repo, session):
        """delete() removes the row."""
        perm = MagicMock()
        session.query().filter().one.return_value = perm
        repo.delete("ws1", 1)
        session.delete.assert_called_once_with(perm)
        session.flush.assert_called_once()


class TestListForUser:
    """Test WorkspacePermissionRepository.list_for_user()."""

    def test_list_for_user_returns_all_for_user_id(self, repo, session):
        """list_for_user() returns all workspace permissions for a user_id."""
        p1 = MagicMock()
        p1.to_mlflow_entity.return_value = "e1"
        p2 = MagicMock()
        p2.to_mlflow_entity.return_value = "e2"
        session.query().filter().all.return_value = [p1, p2]
        result = repo.list_for_user(42)
        assert result == ["e1", "e2"]


class TestListForWorkspace:
    """Test WorkspacePermissionRepository.list_for_workspace()."""

    def test_list_for_workspace_returns_all_user_permissions(self, repo, session):
        """list_for_workspace() returns all user permissions in a workspace."""
        p1 = MagicMock()
        p1.to_mlflow_entity.return_value = "e1"
        session.query().filter().all.return_value = [p1]
        result = repo.list_for_workspace("ws1")
        assert result == ["e1"]


class TestDeleteAllForWorkspace:
    """Test WorkspacePermissionRepository.delete_all_for_workspace()."""

    def test_delete_all_returns_count_deleted(self, repo, session):
        """delete_all_for_workspace() deletes all rows and returns count."""
        session.query().filter().delete.return_value = 3
        result = repo.delete_all_for_workspace("ws1")
        assert result == 3
        session.flush.assert_called_once()

    def test_delete_all_returns_zero_when_none_exist(self, repo, session):
        """delete_all_for_workspace() returns 0 when no permissions exist."""
        session.query().filter().delete.return_value = 0
        result = repo.delete_all_for_workspace("empty_ws")
        assert result == 0
