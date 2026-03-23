"""Tests for workspace permission entity classes."""

import pytest

from mlflow_oidc_auth.entities.workspace import (
    WorkspacePermission,
    WorkspaceGroupPermission,
)


class TestWorkspacePermission:
    """Tests for WorkspacePermission entity."""

    def test_construction_with_all_fields(self):
        """WorkspacePermission stores workspace, user_id, permission, username."""
        perm = WorkspacePermission(
            workspace="ws1", user_id=42, permission="MANAGE", username="alice"
        )
        assert perm.workspace == "ws1"
        assert perm.user_id == 42
        assert perm.permission == "MANAGE"
        assert perm.username == "alice"

    def test_construction_username_default_none(self):
        """WorkspacePermission username defaults to None."""
        perm = WorkspacePermission(workspace="ws1", user_id=1, permission="READ")
        assert perm.username is None

    def test_to_json(self):
        """to_json() returns dict with workspace, user_id, permission, username keys."""
        perm = WorkspacePermission(
            workspace="ws1", user_id=42, permission="MANAGE", username="alice"
        )
        result = perm.to_json()
        assert result == {
            "workspace": "ws1",
            "user_id": 42,
            "permission": "MANAGE",
            "username": "alice",
        }

    def test_to_json_without_username(self):
        """to_json() includes None username."""
        perm = WorkspacePermission(workspace="ws1", user_id=1, permission="READ")
        result = perm.to_json()
        assert result["username"] is None


class TestWorkspaceGroupPermission:
    """Tests for WorkspaceGroupPermission entity."""

    def test_construction_with_all_fields(self):
        """WorkspaceGroupPermission stores workspace, group_id, permission, group_name."""
        perm = WorkspaceGroupPermission(
            workspace="ws1", group_id=10, permission="EDIT", group_name="ml-team"
        )
        assert perm.workspace == "ws1"
        assert perm.group_id == 10
        assert perm.permission == "EDIT"
        assert perm.group_name == "ml-team"

    def test_construction_group_name_default_none(self):
        """WorkspaceGroupPermission group_name defaults to None."""
        perm = WorkspaceGroupPermission(workspace="ws1", group_id=1, permission="READ")
        assert perm.group_name is None

    def test_to_json(self):
        """to_json() returns dict with workspace, group_id, permission, group_name keys."""
        perm = WorkspaceGroupPermission(
            workspace="ws1", group_id=10, permission="EDIT", group_name="ml-team"
        )
        result = perm.to_json()
        assert result == {
            "workspace": "ws1",
            "group_id": 10,
            "permission": "EDIT",
            "group_name": "ml-team",
        }

    def test_to_json_without_group_name(self):
        """to_json() includes None group_name."""
        perm = WorkspaceGroupPermission(workspace="ws1", group_id=1, permission="READ")
        result = perm.to_json()
        assert result["group_name"] is None
