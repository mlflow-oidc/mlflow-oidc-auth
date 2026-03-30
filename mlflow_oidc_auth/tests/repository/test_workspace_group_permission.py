"""Tests for WorkspaceGroupPermissionRepository."""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import NoResultFound, IntegrityError
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.repository.workspace_group_permission import (
    WorkspaceGroupPermissionRepository,
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
    return WorkspaceGroupPermissionRepository(session_maker)


class TestGet:
    """Test WorkspaceGroupPermissionRepository.get()."""

    def test_get_returns_entity(self, repo, session):
        """get() returns entity for existing (workspace, group_id)."""
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        session.query().filter().one.return_value = perm
        result = repo.get("ws1", 10)
        assert result == "entity"

    def test_get_raises_for_missing(self, repo, session):
        """get() raises MlflowException for missing permission."""
        session.query().filter().one.side_effect = NoResultFound()
        with pytest.raises(MlflowException) as exc:
            repo.get("ws1", 10)
        assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


class TestCreate:
    """Test WorkspaceGroupPermissionRepository.create()."""

    def test_create_inserts_and_returns_entity(self, repo, session):
        """create() inserts row and returns entity."""
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"

        with patch(
            "mlflow_oidc_auth.repository.workspace_group_permission.SqlWorkspaceGroupPermission",
            return_value=perm,
        ):
            result = repo.create("ws1", 10, "MANAGE")
            session.add.assert_called_once_with(perm)
            session.flush.assert_called_once()
            assert result == "entity"

    def test_create_raises_on_duplicate(self, repo, session):
        """create() raises MlflowException on duplicate."""
        session.flush.side_effect = IntegrityError("statement", "params", "orig")

        with patch(
            "mlflow_oidc_auth.repository.workspace_group_permission.SqlWorkspaceGroupPermission",
            return_value=MagicMock(),
        ):
            with pytest.raises(MlflowException) as exc:
                repo.create("ws1", 10, "MANAGE")
            assert exc.value.error_code == "RESOURCE_ALREADY_EXISTS"


class TestUpdate:
    """Test WorkspaceGroupPermissionRepository.update()."""

    def test_update_modifies_and_returns_entity(self, repo, session):
        """update() modifies permission and returns updated entity."""
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "updated_entity"
        session.query().filter().one.return_value = perm
        result = repo.update("ws1", 10, "EDIT")
        assert perm.permission == "EDIT"
        session.flush.assert_called_once()
        assert result == "updated_entity"


class TestDelete:
    """Test WorkspaceGroupPermissionRepository.delete()."""

    def test_delete_removes_row(self, repo, session):
        """delete() removes the row."""
        perm = MagicMock()
        session.query().filter().one.return_value = perm
        repo.delete("ws1", 10)
        session.delete.assert_called_once_with(perm)
        session.flush.assert_called_once()


class TestListForGroup:
    """Test WorkspaceGroupPermissionRepository.list_for_group()."""

    def test_list_for_group_returns_all_for_group_id(self, repo, session):
        """list_for_group() returns all workspace permissions for a group_id."""
        p1 = MagicMock()
        p1.to_mlflow_entity.return_value = "e1"
        session.query().filter().all.return_value = [p1]
        result = repo.list_for_group(10)
        assert result == ["e1"]


class TestListForWorkspace:
    """Test WorkspaceGroupPermissionRepository.list_for_workspace()."""

    def test_list_for_workspace_returns_all_group_permissions(self, repo, session):
        """list_for_workspace() returns all group permissions in a workspace."""
        p1 = MagicMock()
        p1.to_mlflow_entity.return_value = "e1"
        session.query().filter().all.return_value = [p1]
        result = repo.list_for_workspace("ws1")
        assert result == ["e1"]


class TestGetHighestForUser:
    """Test WorkspaceGroupPermissionRepository.get_highest_for_user()."""

    def test_returns_highest_priority_permission(self, repo, session):
        """get_highest_for_user() returns highest-priority permission across user's groups."""
        # Mock the joins — the query chain: session.query().join().filter().all()
        p_read = MagicMock()
        p_read.permission = "READ"
        p_read.to_mlflow_entity.return_value = "read_entity"
        p_manage = MagicMock()
        p_manage.permission = "MANAGE"
        p_manage.to_mlflow_entity.return_value = "manage_entity"
        session.query().join().filter().all.return_value = [p_read, p_manage]

        with patch(
            "mlflow_oidc_auth.repository.workspace_group_permission.compare_permissions",
            return_value=True,
        ):
            result = repo.get_highest_for_user("ws1", 42)
            assert result == "manage_entity"

    def test_raises_when_no_group_permission(self, repo, session):
        """get_highest_for_user() raises MlflowException when no permission found."""
        session.query().join().filter().all.return_value = []

        with pytest.raises(MlflowException) as exc:
            repo.get_highest_for_user("ws1", 42)
        assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


class TestDeleteAllForWorkspace:
    """Test WorkspaceGroupPermissionRepository.delete_all_for_workspace()."""

    def test_delete_all_returns_count_deleted(self, repo, session):
        """delete_all_for_workspace() deletes all rows and returns count."""
        session.query().filter().delete.return_value = 2
        result = repo.delete_all_for_workspace("ws1")
        assert result == 2
        session.flush.assert_called_once()

    def test_delete_all_returns_zero_when_none_exist(self, repo, session):
        """delete_all_for_workspace() returns 0 when no permissions exist."""
        session.query().filter().delete.return_value = 0
        result = repo.delete_all_for_workspace("empty_ws")
        assert result == 0
