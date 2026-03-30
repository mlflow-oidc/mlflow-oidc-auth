"""Tests for workspace permission entity classes."""

import pytest

from mlflow_oidc_auth.entities.workspace import (
    WorkspacePermission,
    WorkspaceGroupPermission,
    WorkspaceRegexPermission,
    WorkspaceGroupRegexPermission,
)


class TestWorkspacePermission:
    """Tests for WorkspacePermission entity."""

    def test_construction_with_all_fields(self):
        """WorkspacePermission stores workspace, user_id, permission, username."""
        perm = WorkspacePermission(workspace="ws1", user_id=42, permission="MANAGE", username="alice")
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
        perm = WorkspacePermission(workspace="ws1", user_id=42, permission="MANAGE", username="alice")
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
        perm = WorkspaceGroupPermission(workspace="ws1", group_id=10, permission="EDIT", group_name="ml-team")
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
        perm = WorkspaceGroupPermission(workspace="ws1", group_id=10, permission="EDIT", group_name="ml-team")
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


class TestWorkspaceRegexPermission:
    """Tests for WorkspaceRegexPermission entity."""

    def test_construction(self):
        """WorkspaceRegexPermission stores id, regex, priority, user_id, permission."""
        perm = WorkspaceRegexPermission(id_=1, regex="^ws-.*", priority=10, user_id=42, permission="READ")
        assert perm.id == 1
        assert perm.regex == "^ws-.*"
        assert perm.priority == 10
        assert perm.user_id == 42
        assert perm.permission == "READ"

    def test_to_json(self):
        """to_json() returns dict with id, regex, priority, user_id, permission."""
        perm = WorkspaceRegexPermission(id_=1, regex="^ws-.*", priority=10, user_id=42, permission="READ")
        result = perm.to_json()
        assert result == {
            "id": 1,
            "regex": "^ws-.*",
            "priority": 10,
            "user_id": 42,
            "permission": "READ",
        }

    def test_from_json_roundtrip(self):
        """from_json(to_json()) roundtrips correctly."""
        perm = WorkspaceRegexPermission(id_=1, regex="^ws-.*", priority=10, user_id=42, permission="READ")
        restored = WorkspaceRegexPermission.from_json(perm.to_json())
        assert restored.id == perm.id
        assert restored.regex == perm.regex
        assert restored.priority == perm.priority
        assert restored.user_id == perm.user_id
        assert restored.permission == perm.permission

    def test_from_json_with_string_user_id(self):
        """from_json() converts string user_id to int."""
        data = {
            "id": 1,
            "regex": "^ws-.*",
            "priority": 10,
            "user_id": "42",
            "permission": "READ",
        }
        perm = WorkspaceRegexPermission.from_json(data)
        assert perm.user_id == 42
        assert isinstance(perm.user_id, int)


class TestWorkspaceGroupRegexPermission:
    """Tests for WorkspaceGroupRegexPermission entity."""

    def test_construction(self):
        """WorkspaceGroupRegexPermission stores id, regex, priority, group_id, permission."""
        perm = WorkspaceGroupRegexPermission(id_=1, regex="^ws-.*", priority=5, group_id=10, permission="EDIT")
        assert perm.id == 1
        assert perm.regex == "^ws-.*"
        assert perm.priority == 5
        assert perm.group_id == 10
        assert perm.permission == "EDIT"

    def test_to_json(self):
        """to_json() returns dict with id, regex, priority, group_id, permission."""
        perm = WorkspaceGroupRegexPermission(id_=1, regex="^ws-.*", priority=5, group_id=10, permission="EDIT")
        result = perm.to_json()
        assert result == {
            "id": 1,
            "regex": "^ws-.*",
            "priority": 5,
            "group_id": 10,
            "permission": "EDIT",
        }

    def test_from_json_roundtrip(self):
        """from_json(to_json()) roundtrips correctly."""
        perm = WorkspaceGroupRegexPermission(id_=1, regex="^ws-.*", priority=5, group_id=10, permission="EDIT")
        restored = WorkspaceGroupRegexPermission.from_json(perm.to_json())
        assert restored.id == perm.id
        assert restored.regex == perm.regex
        assert restored.priority == perm.priority
        assert restored.group_id == perm.group_id
        assert restored.permission == perm.permission

    def test_from_json_with_string_group_id(self):
        """from_json() converts string group_id to int."""
        data = {
            "id": 1,
            "regex": "^ws-.*",
            "priority": 5,
            "group_id": "10",
            "permission": "EDIT",
        }
        perm = WorkspaceGroupRegexPermission.from_json(data)
        assert perm.group_id == 10
        assert isinstance(perm.group_id, int)
