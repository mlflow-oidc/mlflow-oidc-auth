"""Tests for entities/_base.py — RegexPermissionBase and PermissionBase."""

import unittest

from mlflow_oidc_auth.entities._base import PermissionBase, RegexPermissionBase


class TestRegexPermissionBase(unittest.TestCase):
    """Tests for RegexPermissionBase dataclass."""

    def test_basic_properties(self) -> None:
        """Should expose id, regex, priority, permission, user_id, group_id."""
        perm = RegexPermissionBase(id=1, regex="^test-.*", priority=5, permission="READ", user_id=10)

        self.assertEqual(perm.id, 1)
        self.assertEqual(perm.regex, "^test-.*")
        self.assertEqual(perm.priority, 5)
        self.assertEqual(perm.permission, "READ")
        self.assertEqual(perm.user_id, 10)
        self.assertIsNone(perm.group_id)

    def test_to_json_omits_none_values(self) -> None:
        """Should omit None values from JSON output."""
        perm = RegexPermissionBase(id=1, regex=".*", priority=0, permission="READ", user_id=5)
        data = perm.to_json()

        self.assertIn("id", data)
        self.assertIn("user_id", data)
        self.assertNotIn("group_id", data)

    def test_to_json_includes_all_set_values(self) -> None:
        """Should include all non-None values."""
        perm = RegexPermissionBase(id=2, regex="^a-.*", priority=3, permission="MANAGE", user_id=1, group_id=2)
        data = perm.to_json()

        self.assertEqual(data, {"id": 2, "regex": "^a-.*", "priority": 3, "permission": "MANAGE", "user_id": 1, "group_id": 2})

    def test_from_json_all_fields(self) -> None:
        """Should construct from a dict with all fields."""
        data = {"id": 10, "regex": "prod-.*", "priority": 1, "permission": "EDIT", "user_id": 5, "group_id": 3}
        perm = RegexPermissionBase.from_json(data)

        self.assertEqual(perm.id, 10)
        self.assertEqual(perm.regex, "prod-.*")
        self.assertEqual(perm.priority, 1)
        self.assertEqual(perm.permission, "EDIT")
        self.assertEqual(perm.user_id, 5)
        self.assertEqual(perm.group_id, 3)

    def test_from_json_missing_required_field_raises(self) -> None:
        """Should raise ValueError when required field is missing."""
        with self.assertRaises(ValueError):
            RegexPermissionBase.from_json({"regex": ".*", "priority": 0, "permission": "READ"})  # missing id

    def test_from_json_casts_string_ids(self) -> None:
        """Should cast string user_id and group_id to integers."""
        data = {"id": 1, "regex": ".*", "priority": 0, "permission": "READ", "user_id": "42", "group_id": "7"}
        perm = RegexPermissionBase.from_json(data)

        self.assertEqual(perm.user_id, 42)
        self.assertEqual(perm.group_id, 7)

    def test_from_json_invalid_user_id_raises(self) -> None:
        """Should raise ValueError for non-integer user_id."""
        data = {"id": 1, "regex": ".*", "priority": 0, "permission": "READ", "user_id": "abc"}
        with self.assertRaises(ValueError):
            RegexPermissionBase.from_json(data)

    def test_from_json_invalid_group_id_raises(self) -> None:
        """Should raise ValueError for non-integer group_id."""
        data = {"id": 1, "regex": ".*", "priority": 0, "permission": "READ", "group_id": "xyz"}
        with self.assertRaises(ValueError):
            RegexPermissionBase.from_json(data)

    def test_from_json_optional_ids_default_to_none(self) -> None:
        """Should default user_id and group_id to None when absent."""
        data = {"id": 1, "regex": ".*", "priority": 0, "permission": "READ"}
        perm = RegexPermissionBase.from_json(data)

        self.assertIsNone(perm.user_id)
        self.assertIsNone(perm.group_id)

    def test_roundtrip(self) -> None:
        """Should roundtrip through to_json/from_json."""
        original = RegexPermissionBase(id=99, regex="^round-.*", priority=7, permission="MANAGE", user_id=3)
        data = original.to_json()
        restored = RegexPermissionBase.from_json(data)

        self.assertEqual(restored.id, original.id)
        self.assertEqual(restored.regex, original.regex)
        self.assertEqual(restored.priority, original.priority)
        self.assertEqual(restored.permission, original.permission)
        self.assertEqual(restored.user_id, original.user_id)
        self.assertIsNone(restored.group_id)


class TestPermissionBase(unittest.TestCase):
    """Tests for PermissionBase dataclass."""

    def test_basic_properties(self) -> None:
        """Should expose instance, permission, user_id, group_id."""
        perm = PermissionBase(instance="my-resource", permission="READ", user_id=1)

        self.assertEqual(perm.instance, "my-resource")
        self.assertEqual(perm.permission, "READ")
        self.assertEqual(perm.user_id, 1)
        self.assertIsNone(perm.group_id)

    def test_to_json_includes_none_values(self) -> None:
        """Should include explicit None for user_id/group_id (backward compat)."""
        perm = PermissionBase(instance="res-1", permission="MANAGE")
        data = perm.to_json()

        self.assertEqual(data["instance"], "res-1")
        self.assertEqual(data["permission"], "MANAGE")
        self.assertIn("user_id", data)
        self.assertIsNone(data["user_id"])
        self.assertIn("group_id", data)
        self.assertIsNone(data["group_id"])

    def test_to_json_with_ids(self) -> None:
        """Should include user_id and group_id when set."""
        perm = PermissionBase(instance="res-2", permission="EDIT", user_id=5, group_id=10)
        data = perm.to_json()

        self.assertEqual(data["user_id"], 5)
        self.assertEqual(data["group_id"], 10)

    def test_default_optional_fields(self) -> None:
        """Should default user_id and group_id to None."""
        perm = PermissionBase(instance="x", permission="READ")

        self.assertIsNone(perm.user_id)
        self.assertIsNone(perm.group_id)
